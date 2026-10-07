"""
Apagar/corrigir um registro lançado errado (ex: digitou "glicemia 6" em vez
de "glicemia 116"). Não basta apagar a linha: o registro errado pode ter
disparado alerta, ciclo de confirmação/escalonamento pros cuidadores e
lembrete de remedição — tudo isso precisa ser desfeito junto, senão o bot
continua cobrando/avisando por causa de um valor que nunca existiu.
"""
from datetime import datetime, timezone

from app.services import cuidadores, estoque
from app.services.supabase_client import supabase


async def ultima_glicemia(usuario_id: str) -> dict | None:
    linhas = (
        supabase.table("registros_glicemia")
        .select("*")
        .eq("usuario_id", usuario_id)
        .order("horario", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return linhas[0] if linhas else None


async def ultima_dose(usuario_id: str) -> dict | None:
    linhas = supabase.table("registros_bolus").select("*").eq("usuario_id", usuario_id).execute().data
    aplicadas = [r for r in linhas if r.get("dose_aplicada") is not None]
    if not aplicadas:
        return None
    return max(aplicadas, key=lambda r: r.get("horario_aplicacao") or r["horario"])


async def apagar_glicemia(usuario: dict, registro_id: str) -> dict | None:
    """Apaga a leitura e desfaz os efeitos dela. Retorna a leitura apagada
    (com a chave extra "cuidadores_avisados") ou None se já não existe."""
    achados = supabase.table("registros_glicemia").select("*").eq("id", registro_id).execute().data
    if not achados or achados[0]["usuario_id"] != usuario["id"]:
        return None
    registro = achados[0]
    desde = registro["created_at"]
    uid = usuario["id"]

    # Cuidadores só nunca ouviram falar dessa leitura se ela ficou pendente de
    # confirmação e ainda não escalou — nos outros casos eles já foram avisados.
    cuidadores_avisados = True
    pendentes = (
        supabase.table("confirmacoes_glicemia")
        .select("*")
        .eq("usuario_id", uid)
        .is_("confirmado_em", "null")
        .gte("horario", desde)
        .execute()
        .data
    )
    for p in pendentes:
        if not p["cuidadores_notificados"]:
            cuidadores_avisados = False
        supabase.table("confirmacoes_glicemia").update(
            {"confirmado_em": datetime.now(timezone.utc).isoformat(), "cuidadores_notificados": True}
        ).eq("id", p["id"]).execute()

    supabase.table("alertas_enviados").delete().eq("usuario_id", uid).eq(
        "valor_glicemia", int(registro["valor"])
    ).gte("horario_envio", desde).execute()
    supabase.table("lembretes_remedicao").delete().eq("usuario_id", uid).eq("enviado", False).gte(
        "created_at", desde
    ).execute()
    supabase.table("registros_glicemia").delete().eq("id", registro_id).execute()

    if cuidadores_avisados:
        nome = usuario.get("nome") or "Ele(a)"
        await cuidadores.notificar_cuidadores(
            uid,
            f"ℹ️ *Correção:* a leitura de *{registro['valor']} mg/dL* de {nome} foi lançada por "
            "engano e foi apagada. Podem ignorar aquele aviso.",
        )
    registro["cuidadores_avisados"] = cuidadores_avisados
    return registro


async def apagar_dose(usuario: dict, registro_id: str) -> dict | None:
    achados = supabase.table("registros_bolus").select("*").eq("id", registro_id).execute().data
    if not achados or achados[0]["usuario_id"] != usuario["id"] or achados[0]["dose_aplicada"] is None:
        return None
    registro = achados[0]
    dose = float(registro["dose_aplicada"])

    if registro.get("glicemia_referencia") is None:
        # dose avulsa (criada pelo próprio "apliquei") — some por inteiro
        supabase.table("registros_bolus").delete().eq("id", registro_id).execute()
    else:
        # veio de um cálculo do bot — volta pra "calculada, ainda não aplicada"
        supabase.table("registros_bolus").update(
            {"dose_aplicada": None, "horario_aplicacao": None}
        ).eq("id", registro_id).execute()

    await estoque.devolver(usuario["id"], "insulina", dose)
    nome = usuario.get("nome") or "Ele(a)"
    await cuidadores.notificar_cuidadores(
        usuario["id"],
        f"ℹ️ *Correção:* a dose de *{dose:.1f}U* de {nome} foi lançada por engano e foi apagada.",
    )
    return registro
