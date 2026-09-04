"""Resumo periódico (semanal/mensal) de glicemia e insulina."""
import logging
from datetime import datetime, timedelta, timezone

from app.services import cuidadores
from app.services.supabase_client import supabase
from app.services.whatsapp_sender import enviar_mensagem
from app.utils import agora_usuario

logger = logging.getLogger("glicia.relatorios")

DIAS_POR_PERIODO = {"semana": 7, "mes": 30}
LABEL_PERIODO = {"semana": "da semana", "mes": "do mês"}

# Quando cada relatório é checado/mandado (hora local do paciente) e o
# intervalo mínimo entre dois envios, pra não duplicar se o job rodar várias
# vezes dentro da mesma janela de hora.
HORARIO_SEMANAL = (6, 20)  # domingo (weekday do Python: segunda=0..domingo=6), 20h
HORARIO_MENSAL_DIA = 1
HORARIO_MENSAL_HORA = 9
DIAS_MINIMOS_ENTRE_ENVIOS = {"semana": 6, "mes": 27}


def _formatar_relatorio(
    periodo: str,
    data_inicio: datetime,
    data_fim: datetime,
    perfil: dict,
    glicemias: list[dict],
    doses_aplicadas: list[float],
    eventos_criticos: int,
) -> str:
    label = LABEL_PERIODO[periodo]
    linhas = [f"📅 *Resumo {label}* ({data_inicio.strftime('%d/%m')} – {data_fim.strftime('%d/%m')})", ""]

    if not glicemias:
        linhas.append("🩸 Sem registros de glicemia no período.")
    else:
        valores = [g["valor"] for g in glicemias]
        media = sum(valores) / len(valores)
        limite_baixo = perfil["limite_baixo"]
        limite_alto = perfil["limite_alto"]
        na_faixa = sum(1 for v in valores if limite_baixo <= v <= limite_alto)
        hipos = sum(1 for v in valores if v < limite_baixo)
        hipers = sum(1 for v in valores if v > limite_alto)
        pct_faixa = round(100 * na_faixa / len(valores))

        linhas.append("🩸 *Glicemia*")
        linhas.append(f"• *{len(valores)} medições*")
        linhas.append(f"• Média: *{media:.0f} mg/dL*")
        linhas.append(f"• Na faixa ({limite_baixo}–{limite_alto}): *{pct_faixa}%*")
        linhas.append(f"• *Hipoglicemias: {hipos}*")
        linhas.append(f"• *Hiperglicemias: {hipers}*")

    linhas.append("")
    if not doses_aplicadas:
        linhas.append("💉 Nenhuma dose de insulina registrada no período.")
    else:
        total = sum(doses_aplicadas)
        dias_periodo = max(1, (data_fim - data_inicio).days)
        media_dia = total / dias_periodo
        linhas.append("💉 *Insulina*")
        linhas.append(f"• *{len(doses_aplicadas)} doses aplicadas*")
        linhas.append(f"• Total: *{total:.1f}U* ({media_dia:.1f}U/dia em média)")

    if eventos_criticos > 0:
        linhas.append("")
        linhas.append(f"🚨 *Eventos críticos* (glicemia fora da faixa segura): *{eventos_criticos}*")

    return "\n".join(linhas)


async def buscar_dados_relatorio(usuario_id: str, periodo: str) -> dict | None:
    """
    Busca os dados brutos do relatório periódico (perfil, glicemias, doses
    aplicadas, eventos críticos) — usado tanto pelo texto automático do
    WhatsApp (gerar_relatorio) quanto pela API JSON do site de
    acompanhamento (web_api.py), pra não duplicar as mesmas consultas.
    """
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data
    if not perfis:
        return None
    perfil = perfis[0]

    dias = DIAS_POR_PERIODO[periodo]
    data_fim = datetime.now(timezone.utc)
    data_inicio = data_fim - timedelta(days=dias)
    inicio_iso = data_inicio.isoformat()

    glicemias = (
        supabase.table("registros_glicemia")
        .select("*")
        .eq("usuario_id", usuario_id)
        .gte("horario", inicio_iso)
        .execute()
        .data
    )

    bolus = (
        supabase.table("registros_bolus")
        .select("*")
        .eq("usuario_id", usuario_id)
        .gte("horario", inicio_iso)
        .execute()
        .data
    )
    doses_aplicadas = [float(b["dose_aplicada"]) for b in bolus if b["dose_aplicada"] is not None]

    eventos = (
        supabase.table("confirmacoes_glicemia")
        .select("id")
        .eq("usuario_id", usuario_id)
        .gte("horario", inicio_iso)
        .execute()
        .data
    )

    return {
        "perfil": perfil,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "glicemias": glicemias,
        "doses_aplicadas": doses_aplicadas,
        "eventos_criticos": len(eventos),
    }


async def gerar_relatorio(usuario_id: str, periodo: str) -> str | None:
    """periodo: 'semana' ou 'mes'. Retorna None se o perfil não estiver completo."""
    dados = await buscar_dados_relatorio(usuario_id, periodo)
    if dados is None:
        return None

    return _formatar_relatorio(
        periodo,
        dados["data_inicio"],
        dados["data_fim"],
        dados["perfil"],
        dados["glicemias"],
        dados["doses_aplicadas"],
        dados["eventos_criticos"],
    )


def _pode_enviar(ultimo_envio_iso: str | None, agora_utc: datetime, dias_minimos: int) -> bool:
    if not ultimo_envio_iso:
        return True
    ultimo = datetime.fromisoformat(ultimo_envio_iso)
    return (agora_utc - ultimo) >= timedelta(days=dias_minimos)


async def _enviar_relatorio_automatico(usuario: dict, periodo: str, campo_controle: str, agora_utc: datetime) -> None:
    relatorio = await gerar_relatorio(usuario["id"], periodo)
    if relatorio is None:
        return
    try:
        await enviar_mensagem(usuario["telefone"], relatorio)
        await cuidadores.notificar_cuidadores(usuario["id"], relatorio)
        supabase.table("usuarios").update({campo_controle: agora_utc.isoformat()}).eq("id", usuario["id"]).execute()
    except Exception:
        logger.exception("Falha ao mandar relatório de %s pro usuário %s", periodo, usuario["id"])


async def verificar_relatorios_periodicos() -> None:
    """
    Roda no scheduler a cada 10 min: checa, no horário local de cada
    paciente, se é hora do relatório semanal (domingo à noite) ou mensal
    (dia 1 de manhã), e dispara se ainda não foi mandado nessa janela.
    """
    usuarios = supabase.table("usuarios").select("*").eq("status_cadastro", "completo").execute().data
    if not usuarios:
        return

    agora_utc = datetime.now(timezone.utc)

    for usuario in usuarios:
        agora_local = agora_usuario(usuario.get("timezone") or "America/Sao_Paulo")

        dia_semanal, hora_semanal = HORARIO_SEMANAL
        if agora_local.weekday() == dia_semanal and agora_local.hour == hora_semanal:
            if _pode_enviar(
                usuario.get("relatorio_semanal_enviado_em"), agora_utc, DIAS_MINIMOS_ENTRE_ENVIOS["semana"]
            ):
                await _enviar_relatorio_automatico(usuario, "semana", "relatorio_semanal_enviado_em", agora_utc)

        if agora_local.day == HORARIO_MENSAL_DIA and agora_local.hour == HORARIO_MENSAL_HORA:
            if _pode_enviar(usuario.get("relatorio_mensal_enviado_em"), agora_utc, DIAS_MINIMOS_ENTRE_ENVIOS["mes"]):
                await _enviar_relatorio_automatico(usuario, "mes", "relatorio_mensal_enviado_em", agora_utc)
