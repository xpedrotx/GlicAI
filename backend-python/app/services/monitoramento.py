"""
Monitoramento de uso do banco de dados — avisa por email quando o projeto
GlicAI estiver perto do limite gratuito do Supabase (500 MB), pra dar tempo
de decidir sobre um upgrade de plano com folga, em vez de descobrir o
problema só quando o banco já estiver cheio.
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.services.supabase_client import supabase

logger = logging.getLogger("glicai.monitoramento")

LIMITE_BYTES_PLANO_GRATUITO = 500 * 1024 * 1024  # teto do plano gratuito do Supabase
LIMIAR_ALERTA = 0.8  # avisa a partir de 80% do limite
DIAS_ENTRE_ALERTAS = 7  # não repete o email todo dia enquanto seguir acima do limiar

EMAIL_DESTINO = "contato@pedrotx.com.br"
EMAIL_REMETENTE = "GlicAI <alertas@pedrotx.com.br>"
CHAVE_ESTADO = "uso_banco"


async def _tamanho_banco_bytes() -> int | None:
    try:
        resultado = supabase.rpc("tamanho_banco_bytes", {}).execute()
        return int(resultado.data)
    except Exception:
        logger.exception("Falha ao consultar o tamanho do banco de dados")
        return None


def _buscar_estado() -> dict | None:
    linhas = supabase.table("monitoramento_estado").select("*").eq("chave", CHAVE_ESTADO).execute().data
    return linhas[0] if linhas else None


def _pode_alertar(estado: dict | None) -> bool:
    if not estado:
        return True
    ultimo = (estado.get("valor") or {}).get("ultimo_alerta_em")
    if not ultimo:
        return True
    try:
        ultimo_dt = datetime.fromisoformat(ultimo)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - ultimo_dt >= timedelta(days=DIAS_ENTRE_ALERTAS)


def _salvar_ultimo_alerta(estado: dict | None, agora_iso: str) -> None:
    valor = {"ultimo_alerta_em": agora_iso}
    if estado:
        supabase.table("monitoramento_estado").update(
            {"valor": valor, "atualizado_em": agora_iso}
        ).eq("chave", CHAVE_ESTADO).execute()
    else:
        supabase.table("monitoramento_estado").insert(
            {"chave": CHAVE_ESTADO, "valor": valor, "atualizado_em": agora_iso}
        ).execute()


async def _enviar_email_alerta(tamanho_bytes: int) -> bool:
    """Manda o alerta via Resend. Retorna True só se realmente enviou —
    quem chama usa isso pra decidir se marca o alerta como despachado."""
    if not settings.resend_api_key:
        logger.warning(
            "RESEND_API_KEY não configurada — não foi possível enviar o alerta de uso do banco"
        )
        return False

    tamanho_mb = tamanho_bytes / (1024 * 1024)
    pct = 100 * tamanho_bytes / LIMITE_BYTES_PLANO_GRATUITO

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resposta = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": EMAIL_REMETENTE,
                    "to": [EMAIL_DESTINO],
                    "subject": f"[GlicAI] Uso do banco em {pct:.0f}% do limite gratuito do Supabase",
                    "text": (
                        f"O projeto GlicAI está usando {tamanho_mb:.0f} MB do banco de dados no "
                        f"Supabase — {pct:.0f}% do limite de 500 MB do plano gratuito.\n\n"
                        "Vale considerar o upgrade pro plano Pro (US$25/mês, 8 GB) antes de "
                        "chegar no limite."
                    ),
                },
            )
            resposta.raise_for_status()
        return True
    except Exception:
        logger.exception("Falha ao enviar email de alerta de uso do banco")
        return False


async def verificar_uso_banco() -> None:
    """Roda periodicamente no scheduler: se o banco estiver acima de
    LIMIAR_ALERTA do limite gratuito do Supabase, manda um email — no
    máximo 1 vez a cada DIAS_ENTRE_ALERTAS dias, pra não virar spam."""
    tamanho = await _tamanho_banco_bytes()
    if tamanho is None or tamanho < LIMITE_BYTES_PLANO_GRATUITO * LIMIAR_ALERTA:
        return

    estado = _buscar_estado()
    if not _pode_alertar(estado):
        return

    enviado = await _enviar_email_alerta(tamanho)
    if enviado:
        _salvar_ultimo_alerta(estado, datetime.now(timezone.utc).isoformat())
