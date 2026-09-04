"""
Ciclo de confirmação/lembrete/escalonamento pra glicemia crítica.

Hiperglicemia: espera confirmação de que a dose de correção foi aplicada
(comando "apliquei"). Hipoglicemia: espera confirmação de que o paciente
tratou (comando "tratei"). Nos dois casos: sem confirmação em 5 min manda um
1º lembrete pro paciente; sem confirmação em 10 min manda um 2º lembrete; sem
confirmação em 15 min avisa os cuidadores — essa é a PRIMEIRA notícia que os
cuidadores têm da leitura (comandos.py deliberadamente não avisa na hora
quando fica pendente de confirmação, só quando confirma ou quando escala).
"""
import logging
from datetime import datetime, timedelta, timezone

from app.services import cuidadores
from app.services.supabase_client import supabase
from app.services.whatsapp_sender import enviar_mensagem

logger = logging.getLogger("glicia.confirmacoes")

MINUTOS_LEMBRETE_1 = 5
MINUTOS_LEMBRETE_2 = 10
MINUTOS_ESCALONAMENTO = 15


async def criar_confirmacao(
    usuario_id: str,
    tipo: str,
    valor_glicemia: float,
    dose_sugerida: float | None = None,
    registro_bolus_id: str | None = None,
) -> dict | None:
    """
    Cria uma pendência de confirmação, exceto se já existir uma do mesmo
    tipo ainda não confirmada pro paciente — evita que leituras repetidas
    abram vários ciclos de escalonamento em paralelo.
    """
    pendente = (
        supabase.table("confirmacoes_glicemia")
        .select("id")
        .eq("usuario_id", usuario_id)
        .eq("tipo", tipo)
        .is_("confirmado_em", "null")
        .limit(1)
        .execute()
        .data
    )
    if pendente:
        return None

    registro = (
        supabase.table("confirmacoes_glicemia")
        .insert(
            {
                "usuario_id": usuario_id,
                "tipo": tipo,
                "valor_glicemia": int(valor_glicemia),
                "dose_sugerida": dose_sugerida,
                "registro_bolus_id": registro_bolus_id,
            }
        )
        .execute()
        .data[0]
    )
    return registro


async def confirmar_por_registro_bolus(registro_bolus_id: str) -> dict | None:
    """Usado pelo comando 'apliquei' — confirma a pendência de hiperglicemia ligada a esse bolus."""
    pendentes = (
        supabase.table("confirmacoes_glicemia")
        .select("*")
        .eq("registro_bolus_id", registro_bolus_id)
        .is_("confirmado_em", "null")
        .limit(1)
        .execute()
        .data
    )
    if not pendentes:
        return None
    return await _marcar_confirmado(pendentes[0])


async def confirmar_hipoglicemia(usuario_id: str) -> dict | None:
    """Usado pelo comando 'tratei' — confirma a pendência de hipoglicemia mais recente."""
    pendentes = (
        supabase.table("confirmacoes_glicemia")
        .select("*")
        .eq("usuario_id", usuario_id)
        .eq("tipo", "hipoglicemia")
        .is_("confirmado_em", "null")
        .order("horario", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not pendentes:
        return None
    return await _marcar_confirmado(pendentes[0])


async def _marcar_confirmado(confirmacao: dict) -> dict:
    agora = datetime.now(timezone.utc).isoformat()
    supabase.table("confirmacoes_glicemia").update({"confirmado_em": agora}).eq("id", confirmacao["id"]).execute()
    return confirmacao


async def marcar_cuidadores_notificados(confirmacao_id: str) -> None:
    supabase.table("confirmacoes_glicemia").update({"cuidadores_notificados": True}).eq("id", confirmacao_id).execute()


def _texto_lembrete(c: dict, numero: int) -> str:
    if c["tipo"] == "hiperglicemia":
        base = (
            f"Você ainda não confirmou a dose de *{c['dose_sugerida']:.0f}U* pra corrigir a "
            f"glicemia de *{c['valor_glicemia']} mg/dL*. Se já aplicou, me conta com "
            f"*apliquei {c['dose_sugerida']:.0f}*."
        )
    else:
        base = (
            f"Sua última glicemia estava em *{c['valor_glicemia']} mg/dL*, abaixo do limite. "
            "Já tratou? Me conta com *tratei*."
        )
    titulo = "⏰ *Lembrete*" if numero == 1 else "⏰⏰ *Segundo aviso*"
    return f"{titulo}\n\n{base}"


def _texto_escalonamento(c: dict, nome: str) -> str:
    if c["tipo"] == "hiperglicemia":
        return (
            f"🚨 *Sem confirmação — {nome}*\n\n"
            f"A glicemia estava em *{c['valor_glicemia']} mg/dL* — a dose de "
            f"*{c['dose_sugerida']:.0f}U* sugerida pra correção não foi confirmada em "
            f"{MINUTOS_ESCALONAMENTO} minutos. {nome} não aplicou a insulina recomendada (ou não avisou)."
        )
    return (
        f"🚨 *Sem confirmação — {nome}*\n\n"
        f"A glicemia estava baixa (*{c['valor_glicemia']} mg/dL*) e não foi confirmada "
        f"em {MINUTOS_ESCALONAMENTO} minutos. {nome} não tratou a hipoglicemia (ou não avisou)."
    )


def _buscar_usuario(usuario_id: str) -> dict | None:
    resultado = supabase.table("usuarios").select("*").eq("id", usuario_id).execute().data
    return resultado[0] if resultado else None


async def verificar_pendentes() -> None:
    """Roda no scheduler a cada minuto: 1º lembrete aos 5min, 2º lembrete aos
    10min, escalonamento pros cuidadores aos 15min sem confirmação."""
    agora = datetime.now(timezone.utc)
    limite_lembrete_1 = (agora - timedelta(minutes=MINUTOS_LEMBRETE_1)).isoformat()
    limite_lembrete_2 = (agora - timedelta(minutes=MINUTOS_LEMBRETE_2)).isoformat()
    limite_escalonamento = (agora - timedelta(minutes=MINUTOS_ESCALONAMENTO)).isoformat()

    pendentes_lembrete_1 = (
        supabase.table("confirmacoes_glicemia")
        .select("*")
        .is_("confirmado_em", "null")
        .eq("lembrete_enviado", False)
        .lte("horario", limite_lembrete_1)
        .execute()
        .data
    )
    for c in pendentes_lembrete_1:
        try:
            usuario = _buscar_usuario(c["usuario_id"])
            if usuario:
                await enviar_mensagem(usuario["telefone"], _texto_lembrete(c, 1))
            supabase.table("confirmacoes_glicemia").update({"lembrete_enviado": True}).eq("id", c["id"]).execute()
        except Exception:
            logger.exception("Falha ao mandar 1º lembrete de confirmação %s", c["id"])

    pendentes_lembrete_2 = (
        supabase.table("confirmacoes_glicemia")
        .select("*")
        .is_("confirmado_em", "null")
        .eq("lembrete2_enviado", False)
        .lte("horario", limite_lembrete_2)
        .execute()
        .data
    )
    for c in pendentes_lembrete_2:
        try:
            usuario = _buscar_usuario(c["usuario_id"])
            if usuario:
                await enviar_mensagem(usuario["telefone"], _texto_lembrete(c, 2))
            supabase.table("confirmacoes_glicemia").update({"lembrete2_enviado": True}).eq("id", c["id"]).execute()
        except Exception:
            logger.exception("Falha ao mandar 2º lembrete de confirmação %s", c["id"])

    pendentes_escalonamento = (
        supabase.table("confirmacoes_glicemia")
        .select("*")
        .is_("confirmado_em", "null")
        .eq("cuidadores_notificados", False)
        .lte("horario", limite_escalonamento)
        .execute()
        .data
    )
    for c in pendentes_escalonamento:
        try:
            usuario = _buscar_usuario(c["usuario_id"])
            nome = (usuario or {}).get("nome") or "Ele(a)"
            await cuidadores.notificar_cuidadores(c["usuario_id"], _texto_escalonamento(c, nome))
            supabase.table("confirmacoes_glicemia").update({"cuidadores_notificados": True}).eq("id", c["id"]).execute()
        except Exception:
            logger.exception("Falha ao escalar pra cuidadores %s", c["id"])
