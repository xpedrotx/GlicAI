"""Webhook do Stripe — mantém o estado da assinatura em dia (renovação, cancelamento, falha de cobrança)."""
import logging

import stripe
from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.services import pagamentos

logger = logging.getLogger("glicia.stripe")

router = APIRouter(prefix="/api/stripe", tags=["stripe"])


@router.post("/webhook")
async def receber_evento(request: Request):
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook do Stripe não configurado.")

    # Precisa do corpo EXATAMENTE como veio (bytes): a assinatura é calculada em
    # cima dele, qualquer re-serialização invalidaria a conferência.
    corpo = await request.body()
    try:
        evento = stripe.Webhook.construct_event(
            corpo, request.headers.get("stripe-signature"), settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError) as erro:
        raise HTTPException(status_code=400, detail="Assinatura inválida.") from erro

    try:
        await pagamentos.processar_evento(evento)
    except Exception:
        # 500 faz o Stripe tentar de novo mais tarde (até ~3 dias).
        logger.exception("Falha ao processar evento %s do Stripe", evento.get("type"))
        raise HTTPException(status_code=500, detail="Falha ao processar o evento.")

    return {"status": "ok"}
