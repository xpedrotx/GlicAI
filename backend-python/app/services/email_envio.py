"""Envio de e-mail transacional (códigos de confirmação) via Resend."""
import logging

import httpx

from app.config import settings

logger = logging.getLogger("glicia.email")

REMETENTE = "GlicAI <nao-responda@pedrotx.com.br>"


class EmailIndisponivel(Exception):
    """Sem chave do Resend configurada ou o envio falhou."""


async def enviar(para: str, assunto: str, texto: str, html: str) -> None:
    if not settings.resend_api_key:
        raise EmailIndisponivel("RESEND_API_KEY não configurada")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resposta = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={"from": REMETENTE, "to": [para], "subject": assunto, "text": texto, "html": html},
            )
        resposta.raise_for_status()
    except httpx.HTTPError as erro:
        logger.exception("Falha ao enviar e-mail")
        raise EmailIndisponivel(str(erro)) from erro
