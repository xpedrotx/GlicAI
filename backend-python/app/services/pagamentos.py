"""
Cobrança do GlicAI Pro via Stripe.

- O formulário de cartão fica na própria página do site (Stripe Elements):
  os dados do cartão vão direto do navegador pro Stripe e nunca passam pelo
  nosso servidor. O site só nos manda o id do método de pagamento (pm_...)
  que o Stripe gerou, e aqui criamos a assinatura com ele (assinar).
- Se o banco do cliente exigir autenticação (3D Secure), assinar() devolve o
  client_secret pro site concluir no navegador e depois chamar confirmar().
- O estado da assinatura (ativa, cancelada, em atraso...) é gravado na tabela
  usuarios por sincronizar_assinatura(), chamado pelo webhook do Stripe e
  também por assinar()/confirmar(), pra liberar o Pro na hora sem esperar o
  webhook chegar.
- Sempre relê a assinatura direto na API do Stripe em vez de confiar no
  payload do evento: eventos podem chegar fora de ordem.
"""
import logging
from datetime import datetime, timezone

import stripe

from app.config import settings
from app.services.planos import site_url
from app.services.supabase_client import supabase

logger = logging.getLogger("glicia.pagamentos")

PRECO_CENTAVOS = 990
_LOOKUP_KEY_PRECO = "glicai_pro_mensal"
_preco_em_cache: str | None = None


def _dict(obj) -> dict:
    """Objetos do SDK do Stripe (v16+) nao sao dict e nao tem .get(): converte
    pra dict puro (recursivo) antes de ler campos opcionais."""
    return obj.to_dict() if hasattr(obj, "to_dict") else obj


class PagamentosIndisponiveis(Exception):
    """Stripe não configurado (sem chaves no .env) ou fora do ar."""


class CartaoRecusado(Exception):
    """O Stripe/banco recusou o cartão; a mensagem já é amigável pra mostrar ao paciente."""


def disponivel() -> bool:
    return bool(settings.stripe_secret_key and settings.stripe_publishable_key)


def _exigir_configurado() -> None:
    if not disponivel():
        raise PagamentosIndisponiveis()
    stripe.api_key = settings.stripe_secret_key


async def _preco_id() -> str:
    """
    Preço mensal do GlicAI Pro. Com STRIPE_PRICE_ID usa o cadastrado no painel
    do Stripe; sem ele, acha (ou cria uma vez só) um preço de R$ 9,90/mês
    identificado por lookup_key — dá pra testar sem configurar nada.
    """
    global _preco_em_cache
    if settings.stripe_price_id:
        return settings.stripe_price_id
    if _preco_em_cache:
        return _preco_em_cache

    async def _buscar() -> str | None:
        achados = _dict(await stripe.Price.list_async(lookup_keys=[_LOOKUP_KEY_PRECO], active=True, limit=1))
        return achados["data"][0]["id"] if achados.get("data") else None

    preco_id = await _buscar()
    if preco_id is None:
        try:
            criado = await stripe.Price.create_async(
                currency="brl",
                unit_amount=PRECO_CENTAVOS,
                recurring={"interval": "month"},
                lookup_key=_LOOKUP_KEY_PRECO,
                product_data={"name": "GlicAI Pro"},
            )
            preco_id = _dict(criado)["id"]
        except stripe.InvalidRequestError:
            # duas requisições criando ao mesmo tempo: a outra venceu
            preco_id = await _buscar()
            if preco_id is None:
                raise
    _preco_em_cache = preco_id
    return preco_id


def _mensagem_recusa(codigo: str | None) -> str:
    if codigo == "insufficient_funds":
        return "Cartão sem saldo/limite suficiente. Tente outro cartão."
    if codigo in ("incorrect_cvc", "invalid_cvc"):
        return "Código de segurança incorreto. Confira o CVC do cartão."
    if codigo in ("expired_card", "invalid_expiry_year", "invalid_expiry_month"):
        return "Cartão vencido ou com validade inválida."
    return "Cartão recusado. Confira os dados ou tente outro cartão."


async def _iniciar_assinatura(cliente_id: str, metodo_id: str, usuario_id: str) -> dict:
    """
    Só fala com o Stripe: prende o cartão ao cliente e cria a assinatura.
    Devolve {"status": "ok"|"requer_acao", "assinatura_id", ["client_secret"]}
    ou levanta CartaoRecusado.
    """
    try:
        # Tentativas anteriores que ficaram pela metade não podem acumular
        pendentes = _dict(await stripe.Subscription.list_async(customer=cliente_id, status="incomplete", limit=20))
        for antiga in pendentes.get("data", []):
            await stripe.Subscription.cancel_async(antiga["id"])

        # usa o id que o Stripe devolve ao anexar (é o cartão que de fato ficou no cliente)
        metodo_id = _dict(await stripe.PaymentMethod.attach_async(metodo_id, customer=cliente_id))["id"]
        await stripe.Customer.modify_async(cliente_id, invoice_settings={"default_payment_method": metodo_id})

        # allow_incomplete: tenta cobrar na hora; se precisar de 3D Secure ou
        # for recusado, a assinatura fica "incomplete" em vez de dar erro.
        assinatura = _dict(
            await stripe.Subscription.create_async(
                customer=cliente_id,
                items=[{"price": await _preco_id()}],
                default_payment_method=metodo_id,
                payment_behavior="allow_incomplete",
                metadata={"usuario_id": usuario_id},
                expand=["latest_invoice.confirmation_secret"],
            )
        )
    except stripe.CardError as erro:
        raise CartaoRecusado(_mensagem_recusa(erro.decline_code or erro.code)) from erro
    except stripe.StripeError as erro:
        logger.exception("Falha ao criar assinatura do usuário %s", usuario_id)
        raise PagamentosIndisponiveis() from erro

    if assinatura["status"] in ("active", "trialing"):
        return {"status": "ok", "assinatura_id": assinatura["id"]}

    segredo = ((assinatura.get("latest_invoice") or {}).get("confirmation_secret") or {}).get("client_secret")
    erro_pagamento: dict = {}
    if segredo:
        intencao = _dict(await stripe.PaymentIntent.retrieve_async(segredo.split("_secret_")[0]))
        if intencao["status"] == "requires_action":
            return {"status": "requer_acao", "assinatura_id": assinatura["id"], "client_secret": segredo}
        erro_pagamento = intencao.get("last_payment_error") or {}

    await stripe.Subscription.cancel_async(assinatura["id"])
    raise CartaoRecusado(_mensagem_recusa(erro_pagamento.get("decline_code") or erro_pagamento.get("code")))


async def assinar(usuario: dict, metodo_id: str) -> dict:
    """Cria a assinatura com o cartão que o site coletou (pm_...)."""
    from app.services import planos

    _exigir_configurado()
    if not metodo_id.startswith("pm_"):
        raise ValueError("método de pagamento inválido")

    cliente_id = usuario.get("stripe_customer_id")
    if not cliente_id:
        try:
            cliente = _dict(
                await stripe.Customer.create_async(
                    name=usuario.get("nome") or None, metadata={"usuario_id": usuario["id"]}
                )
            )
        except stripe.StripeError as erro:
            raise PagamentosIndisponiveis() from erro
        cliente_id = cliente["id"]
        supabase.table("usuarios").update({"stripe_customer_id": cliente_id}).eq("id", usuario["id"]).execute()
        usuario = {**usuario, "stripe_customer_id": cliente_id}

    resultado = await _iniciar_assinatura(cliente_id, metodo_id, usuario["id"])
    if resultado["status"] == "ok":
        atualizado = await sincronizar_assinatura(resultado["assinatura_id"], usuario_id=usuario["id"])
        return {**planos.resumo(atualizado or usuario), "status": "ok"}
    return resultado


async def confirmar(usuario: dict, assinatura_id: str) -> dict:
    """
    Depois do 3D Secure feito no navegador: relê a assinatura no Stripe e
    sincroniza. PermissionError se ela não for deste usuário.
    """
    from app.services import planos

    _exigir_configurado()
    try:
        assinatura = _dict(await stripe.Subscription.retrieve_async(assinatura_id))
    except stripe.StripeError as erro:
        raise PagamentosIndisponiveis() from erro

    if (assinatura.get("metadata") or {}).get("usuario_id") != usuario["id"]:
        raise PermissionError("assinatura de outro usuário")

    status = "pendente"
    atualizado = await sincronizar_assinatura(assinatura_id, usuario_id=usuario["id"])
    if atualizado and assinatura["status"] in ("active", "trialing"):
        usuario, status = atualizado, "ok"
    return {**planos.resumo(usuario), "status": status}


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
    assinatura = _dict(await stripe.Subscription.retrieve_async(assinatura_id))

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
    evento = _dict(evento)
    tipo = evento["type"]
    objeto = evento["data"]["object"]

    if tipo in _EVENTOS_ASSINATURA:
        await sincronizar_assinatura(objeto["id"])
    elif tipo in ("invoice.payment_failed", "invoice.paid"):
        # Falha/sucesso de cobrança mexe no status (past_due <-> active).
        parent = objeto.get("parent") or {}
        assinatura_id = objeto.get("subscription") or (parent.get("subscription_details") or {}).get("subscription")
        if assinatura_id:
            await sincronizar_assinatura(assinatura_id)
