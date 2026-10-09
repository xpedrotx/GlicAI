"""
Cobrança do GlicAI Pro via Stripe.

- Checkout embutido na própria página (ui_mode embedded_page): o site recebe
  um client_secret e monta o formulário de pagamento do Stripe dentro do
  painel — dados de cartão nunca passam pelo nosso servidor.
- O estado da assinatura (ativa, cancelada, em atraso...) é gravado na tabela
  usuarios por sincronizar_assinatura(), chamado pelo webhook do Stripe e
  também na volta do checkout (confirmar_sessao), pra liberar o Pro na hora
  sem esperar o webhook chegar.
- Sempre relê a assinatura direto na API do Stripe em vez de confiar no
  payload do evento: eventos podem chegar fora de ordem.
"""
import logging
from datetime import datetime, timezone

import stripe

from app.config import settings
from app.services.planos import PRECO_TEXTO, site_url
from app.services.supabase_client import supabase

logger = logging.getLogger("glicia.pagamentos")

PRECO_CENTAVOS = 990


class PagamentosIndisponiveis(Exception):
    """Stripe não configurado (sem chaves no .env) ou fora do ar."""


def disponivel() -> bool:
    return bool(settings.stripe_secret_key and settings.stripe_publishable_key)


def _exigir_configurado() -> None:
    if not disponivel():
        raise PagamentosIndisponiveis()
    stripe.api_key = settings.stripe_secret_key


def _linha_do_plano() -> dict:
    # Com STRIPE_PRICE_ID usa o preço cadastrado no painel do Stripe; sem ele,
    # cria o preço na hora (R$ 9,90/mês) — dá pra testar sem configurar nada.
    if settings.stripe_price_id:
        return {"price": settings.stripe_price_id, "quantity": 1}
    return {
        "quantity": 1,
        "price_data": {
            "currency": "brl",
            "unit_amount": PRECO_CENTAVOS,
            "recurring": {"interval": "month"},
            "product_data": {"name": "GlicAI Pro", "description": f"Uso ilimitado e lembretes — {PRECO_TEXTO}"},
        },
    }


async def criar_checkout(usuario: dict) -> dict:
    """Abre uma sessão de checkout embutido; devolve o que o site precisa pra montá-lo."""
    _exigir_configurado()

    params: dict = {
        "mode": "subscription",
        "ui_mode": "embedded_page",
        "line_items": [_linha_do_plano()],
        "return_url": f"{site_url()}/dashboard/assinatura?sessao={{CHECKOUT_SESSION_ID}}",
        "client_reference_id": usuario["id"],
        "metadata": {"usuario_id": usuario["id"]},
        "subscription_data": {"metadata": {"usuario_id": usuario["id"]}},
        "locale": "pt-BR",
    }
    # Quem já assinou antes (e cancelou) volta pro mesmo cliente do Stripe,
    # mantendo histórico e cartão salvo.
    if usuario.get("stripe_customer_id"):
        params["customer"] = usuario["stripe_customer_id"]

    try:
        sessao = await stripe.checkout.Session.create_async(**params)
    except stripe.StripeError as erro:
        logger.exception("Falha ao criar sessão de checkout do usuário %s", usuario["id"])
        raise PagamentosIndisponiveis() from erro

    return {"client_secret": sessao["client_secret"], "publishable_key": settings.stripe_publishable_key}


async def confirmar_sessao(usuario: dict, sessao_id: str) -> dict:
    """
    Chamado quando o cliente volta do checkout: confere a sessão no Stripe e
    sincroniza a assinatura. PermissionError se a sessão não for deste usuário.
    """
    from app.services import planos

    _exigir_configurado()
    try:
        sessao = await stripe.checkout.Session.retrieve_async(sessao_id)
    except stripe.StripeError as erro:
        raise PagamentosIndisponiveis() from erro

    if (sessao.get("metadata") or {}).get("usuario_id") != usuario["id"]:
        raise PermissionError("sessão de outro usuário")

    status = "pendente"
    if sessao.get("status") == "complete" and sessao.get("subscription"):
        atualizado = await sincronizar_assinatura(sessao["subscription"], usuario_id=usuario["id"])
        if atualizado:
            usuario = atualizado
            status = "ok"
    return {**planos.resumo(usuario), "pagamentos_disponiveis": True, "status": status}


async def criar_portal(usuario: dict) -> str:
    """URL do portal do Stripe pra trocar cartão, ver faturas ou cancelar."""
    _exigir_configurado()
    if not usuario.get("stripe_customer_id"):
        raise ValueError("sem cliente no Stripe")
    try:
        portal = await stripe.billing_portal.Session.create_async(
            customer=usuario["stripe_customer_id"],
            return_url=f"{site_url()}/dashboard/assinatura",
        )
    except stripe.StripeError as erro:
        logger.exception("Falha ao abrir portal do usuário %s", usuario["id"])
        raise PagamentosIndisponiveis() from erro
    return portal["url"]


def _fim_do_periodo(assinatura) -> datetime | None:
    # Nas versões novas da API o fim do período fica nos itens da assinatura;
    # nas antigas, na própria assinatura.
    fim = assinatura.get("current_period_end")
    if fim is None:
        itens = (assinatura.get("items") or {}).get("data") or []
        fim = max((i.get("current_period_end") or 0 for i in itens), default=None) or None
    return datetime.fromtimestamp(fim, tz=timezone.utc) if fim else None


def _buscar_usuario(usuario_id: str | None, cliente_id: str | None) -> dict | None:
    if usuario_id:
        achados = supabase.table("usuarios").select("*").eq("id", usuario_id).execute().data
        if achados:
            return achados[0]
    if cliente_id:
        achados = supabase.table("usuarios").select("*").eq("stripe_customer_id", cliente_id).execute().data
        if achados:
            return achados[0]
    return None


async def sincronizar_assinatura(assinatura_id: str, usuario_id: str | None = None) -> dict | None:
    """Relê a assinatura no Stripe e grava o estado no usuário. Devolve o usuário atualizado."""
    _exigir_configurado()
    assinatura = await stripe.Subscription.retrieve_async(assinatura_id)

    cliente = assinatura.get("customer")
    cliente_id = cliente if isinstance(cliente, str) else (cliente or {}).get("id")
    usuario = _buscar_usuario(usuario_id or (assinatura.get("metadata") or {}).get("usuario_id"), cliente_id)
    if usuario is None:
        logger.warning("Assinatura %s sem usuário correspondente", assinatura_id)
        return None

    fim = _fim_do_periodo(assinatura)
    dados = {
        "stripe_customer_id": cliente_id,
        "stripe_subscription_id": assinatura["id"],
        "assinatura_status": assinatura["status"],
        "assinatura_renova_em": fim.isoformat() if fim else None,
        "assinatura_cancela_no_fim": bool(assinatura.get("cancel_at_period_end") or assinatura.get("cancel_at")),
    }
    supabase.table("usuarios").update(dados).eq("id", usuario["id"]).execute()
    return {**usuario, **dados}


# Eventos do Stripe que mudam o estado da assinatura.
_EVENTOS_ASSINATURA = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.paused",
    "customer.subscription.resumed",
}


async def processar_evento(evento: dict) -> None:
    tipo = evento["type"]
    objeto = evento["data"]["object"]

    if tipo in _EVENTOS_ASSINATURA:
        await sincronizar_assinatura(objeto["id"])
    elif tipo == "checkout.session.completed" and objeto.get("mode") == "subscription" and objeto.get("subscription"):
        await sincronizar_assinatura(objeto["subscription"], usuario_id=(objeto.get("metadata") or {}).get("usuario_id"))
    elif tipo in ("invoice.payment_failed", "invoice.paid"):
        # Falha/sucesso de cobrança mexe no status (past_due <-> active).
        parent = objeto.get("parent") or {}
        assinatura_id = objeto.get("subscription") or (parent.get("subscription_details") or {}).get("subscription")
        if assinatura_id:
            await sincronizar_assinatura(assinatura_id)
