import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import stripe
from fastapi import HTTPException

from app.config import settings
from app.routes import stripe_webhook
from app.services import alertas, bolus, comandos, confirmacoes, estoque, pagamentos, planos, remedicao
from app import scheduler
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def _dias(n):
    return (datetime.now(timezone.utc) + timedelta(days=n)).isoformat()


def _ligar(fake):
    for modulo in (comandos, planos, alertas, bolus, confirmacoes, estoque, remedicao, pagamentos, scheduler):
        modulo.supabase = fake


def _usuario(fake, **extra):
    base = {"telefone": "5545999999999@c.us", "nome": "Pedro", "status_cadastro": "completo", "timezone": "America/Sao_Paulo"}
    return fake.table("usuarios").insert({**base, **extra}).execute().data[0]


def _perfil(fake, usuario):
    fake.table("perfil_glicemico").insert(
        {"usuario_id": usuario["id"], "meta_glicemia": 110, "limite_baixo": 70, "limite_alto": 180, "fator_sensibilidade": 40}
    ).execute()


def _glicemia_hoje(fake, usuario, valor=100):
    fake.table("registros_glicemia").insert(
        {"usuario_id": usuario["id"], "valor": valor, "horario": datetime.now(timezone.utc).isoformat()}
    ).execute()


# --------------------------------------------------------------------------
# plano_efetivo / resumo
# --------------------------------------------------------------------------

def test_teste_gratis_vale_ate_o_fim_do_prazo():
    assert planos.plano_efetivo({"teste_termina_em": _dias(3)}) == "trial"
    assert planos.plano_efetivo({"teste_termina_em": _dias(-1)}) == "free"


def test_sem_data_de_teste_nao_corta_o_acesso():
    assert planos.plano_efetivo({}) == "trial"


@pytest.mark.parametrize("status", ["active", "trialing", "past_due"])
def test_assinatura_com_acesso_vira_pro_mesmo_com_teste_vencido(status):
    assert planos.plano_efetivo({"teste_termina_em": _dias(-10), "assinatura_status": status}) == "pro"


@pytest.mark.parametrize("status", ["canceled", "unpaid", "incomplete_expired", None])
def test_assinatura_encerrada_volta_pro_free(status):
    assert planos.plano_efetivo({"teste_termina_em": _dias(-10), "assinatura_status": status}) == "free"


def test_cortesia_e_sempre_pro():
    assert planos.plano_efetivo({"teste_termina_em": _dias(-10), "plano_cortesia": True}) == "pro"


def test_resumo_conta_dias_restantes_do_teste():
    resumo = planos.resumo({"teste_termina_em": _dias(3) })
    assert resumo["plano"] == "trial"
    assert resumo["dias_restantes_teste"] in (3, 4)
    assert resumo["preco"] == "R$ 9,90/mês"
    assert resumo["medicoes_por_dia_free"] == 1


# --------------------------------------------------------------------------
# Limites do plano gratuito no bot
# --------------------------------------------------------------------------

def test_free_registra_a_primeira_glicemia_do_dia_e_bloqueia_a_segunda():
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))
    _perfil(fake, usuario)

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()):
        primeira = _executar(comandos.processar_comando(usuario, "glicemia 110"))
        _glicemia_hoje(fake, usuario)  # o banco real preenche "horario" sozinho
        segunda = _executar(comandos.processar_comando(usuario, "glicemia 120"))

    assert "Glicemia registrada" in primeira
    assert "1 medição por dia" in segunda
    assert "/dashboard/assinatura" in segunda


def test_free_sempre_registra_glicemia_fora_da_faixa():
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))
    _perfil(fake, usuario)
    _glicemia_hoje(fake, usuario)

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()), \
         patch.object(comandos.ia, "gerar_dicas", new=AsyncMock(return_value=["Beba água"])):
        alta = _executar(comandos.processar_comando(usuario, "glicemia 250"))
        baixa = _executar(comandos.processar_comando(usuario, "glicemia 60"))
        emergencia = _executar(comandos.processar_comando(usuario, "glicemia 600"))

    for resposta in (alta, baixa, emergencia):
        assert "1 medição por dia" not in resposta
    assert len(fake.store["registros_glicemia"]) == 4


def test_teste_gratis_e_pro_nao_tem_limite_de_medicoes():
    for extra in ({"teste_termina_em": _dias(2)}, {"teste_termina_em": _dias(-5), "assinatura_status": "active"}):
        fake = FakeSupabase()
        _ligar(fake)
        usuario = _usuario(fake, **extra)
        _perfil(fake, usuario)
        _glicemia_hoje(fake, usuario)
        _glicemia_hoje(fake, usuario)

        with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()):
            resposta = _executar(comandos.processar_comando(usuario, "glicemia 110"))

        assert "Glicemia registrada" in resposta


def test_free_nao_cria_lembretes_mas_pode_listar():
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))

    resposta = _executar(comandos.processar_comando(usuario, "lembrete adicionar 08:00"))

    assert "GlicAI Pro" in resposta
    assert fake.store.get("lembretes", []) == []
    assert "lembretes ativos" in _executar(comandos.processar_comando(usuario, "lembrete listar"))


def test_comando_plano_mostra_o_plano_atual():
    fake = FakeSupabase()
    _ligar(fake)
    em_teste = _usuario(fake, teste_termina_em=_dias(3))
    free = _usuario(fake, telefone="2", teste_termina_em=_dias(-1))

    assert "teste grátis" in _executar(comandos.processar_comando(em_teste, "plano"))
    assert "plano gratuito" in _executar(comandos.processar_comando(free, "plano"))


# --------------------------------------------------------------------------
# Lembretes e avisos automáticos
# --------------------------------------------------------------------------

def test_scheduler_nao_manda_lembrete_pro_plano_free():
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))
    agora = datetime.now(timezone.utc).astimezone()
    fake.table("lembretes").insert(
        {"usuario_id": usuario["id"], "tipo": "outro", "ativo": True, "dias_semana": list(range(8)),
         "horario": agora.strftime("%H:%M")}
    ).execute()

    with patch.object(scheduler, "enviar_mensagem", new=AsyncMock()) as enviar, \
         patch.object(scheduler, "agora_usuario", return_value=agora), \
         patch.object(scheduler, "dia_semana_supabase", return_value=0):
        _executar(scheduler._checar_lembretes())
        assert enviar.await_count == 0

        fake.table("usuarios").update({"assinatura_status": "active"}).eq("id", usuario["id"]).execute()
        _executar(scheduler._checar_lembretes())
        assert enviar.await_count == 1


def test_remedicao_nao_manda_pro_plano_free():
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))
    fake.table("lembretes_remedicao").insert(
        {"usuario_id": usuario["id"], "disparar_em": _dias(-1), "enviado": False, "tipo": "hipoglicemia"}
    ).execute()

    with patch.object(remedicao, "enviar_mensagem", new=AsyncMock()) as enviar:
        _executar(remedicao.verificar_pendentes())

    assert enviar.await_count == 0
    assert fake.store["lembretes_remedicao"][0]["enviado"] is True


def test_aviso_de_fim_do_teste_sai_uma_unica_vez():
    fake = FakeSupabase()
    _ligar(fake)
    recem_vencido = _usuario(fake, telefone="1", teste_termina_em=_dias(0) if False else (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())
    antigo = _usuario(fake, telefone="2", teste_termina_em=_dias(-20))
    assinante = _usuario(
        fake, telefone="3", teste_termina_em=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(), assinatura_status="active"
    )

    with patch("app.services.whatsapp_sender.enviar_mensagem", new=AsyncMock()) as enviar:
        _executar(planos.avisar_fim_do_teste())
        _executar(planos.avisar_fim_do_teste())

    assert enviar.await_count == 1
    assert enviar.await_args.args[0] == recem_vencido["telefone"]
    marcados = {u["telefone"]: u.get("aviso_fim_teste_em") for u in fake.store["usuarios"]}
    assert marcados["1"] and marcados["2"]  # o antigo é marcado sem receber mensagem
    assert antigo["id"] != assinante["id"]


# --------------------------------------------------------------------------
# Stripe
# --------------------------------------------------------------------------

@pytest.fixture
def stripe_configurado(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(settings, "stripe_publishable_key", "pk_test_x")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_x")


def test_sem_chaves_do_stripe_pagamentos_ficam_indisponiveis(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    assert pagamentos.disponivel() is False
    with pytest.raises(pagamentos.PagamentosIndisponiveis):
        _executar(pagamentos.assinar({"id": "u1"}, "pm_x"))


def _obj(dados: dict):
    """Como o Stripe devolve em producao: StripeObject, que nao e dict e nao tem .get()."""
    return stripe.StripeObject.construct_from(dados, "sk_test_x")


def _assinatura(status="active", **extra):
    return _obj({
        "id": "sub_1", "status": status, "customer": "cus_1", "metadata": {"usuario_id": None},
        "items": {"data": [{"current_period_end": int(time.time()) + 86400 * 30}]}, **extra,
    })


def test_sincronizar_assinatura_libera_o_pro(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))

    with patch.object(stripe.Subscription, "retrieve_async", new=AsyncMock(return_value=_assinatura())):
        _executar(pagamentos.sincronizar_assinatura("sub_1", usuario_id=usuario["id"]))

    salvo = fake.store["usuarios"][0]
    assert salvo["assinatura_status"] == "active"
    assert salvo["stripe_customer_id"] == "cus_1"
    assert salvo["assinatura_renova_em"]
    assert planos.plano_efetivo(salvo) == "pro"


def test_cancelamento_derruba_pro_e_cancelar_no_fim_mantem_ate_la(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1), stripe_customer_id="cus_1")

    with patch.object(stripe.Subscription, "retrieve_async", new=AsyncMock(return_value=_assinatura(cancel_at_period_end=True))):
        _executar(pagamentos.sincronizar_assinatura("sub_1"))  # acha o usuário pelo cliente do Stripe
    salvo = fake.store["usuarios"][0]
    assert salvo["assinatura_cancela_no_fim"] is True
    assert planos.plano_efetivo(salvo) == "pro"

    with patch.object(stripe.Subscription, "retrieve_async", new=AsyncMock(return_value=_assinatura("canceled"))):
        _executar(pagamentos.sincronizar_assinatura("sub_1"))
    assert planos.plano_efetivo(fake.store["usuarios"][0]) == "free"
    assert usuario["id"] == fake.store["usuarios"][0]["id"]


def test_confirmar_recusa_assinatura_de_outro_usuario(stripe_configurado):
    with patch.object(stripe.Subscription, "retrieve_async",
                      new=AsyncMock(return_value=_assinatura(metadata={"usuario_id": "outro"}))):
        with pytest.raises(PermissionError):
            _executar(pagamentos.confirmar({"id": "u1"}, "sub_1"))


def test_confirmar_assinatura_paga_libera_na_hora(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))
    assinatura = _assinatura(metadata={"usuario_id": usuario["id"]})

    with patch.object(stripe.Subscription, "retrieve_async", new=AsyncMock(return_value=assinatura)):
        resultado = _executar(pagamentos.confirmar(usuario, "sub_1"))

    assert resultado["status"] == "ok"
    assert resultado["plano"] == "pro"


def test_confirmar_assinatura_ainda_incompleta_fica_pendente(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))
    assinatura = _assinatura("incomplete", metadata={"usuario_id": usuario["id"]})

    with patch.object(stripe.Subscription, "retrieve_async", new=AsyncMock(return_value=assinatura)):
        resultado = _executar(pagamentos.confirmar(usuario, "sub_1"))

    assert resultado["status"] == "pendente"
    assert resultado["plano"] == "free"


# --- assinar(): cartao coletado no formulario do site --------------------------

def _stripe_assinar(assinatura, intencao=None, existentes=()):
    """Troca as chamadas ao Stripe usadas por assinar() por mocks."""
    mocks = {
        "criar_cliente": patch.object(stripe.Customer, "create_async", new=AsyncMock(return_value=_obj({"id": "cus_novo"}))),
        "atualizar_cliente": patch.object(stripe.Customer, "modify_async", new=AsyncMock()),
        "anexar": patch.object(stripe.PaymentMethod, "attach_async", new=AsyncMock(return_value=_obj({"id": "pm_card"}))),
        "listar_assinaturas": patch.object(stripe.Subscription, "list_async",
                                           new=AsyncMock(return_value=_obj({"data": list(existentes)}))),
        "criar_assinatura": patch.object(stripe.Subscription, "create_async", new=AsyncMock(return_value=assinatura)),
        "cancelar": patch.object(stripe.Subscription, "cancel_async", new=AsyncMock()),
        "intencao": patch.object(stripe.PaymentIntent, "retrieve_async", new=AsyncMock(return_value=_obj(intencao or {}))),
        "preco": patch.object(pagamentos, "_preco_id", new=AsyncMock(return_value="price_9_90")),
    }
    return mocks


def test_assinar_cobra_na_hora_e_libera_o_pro(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))
    mocks = _stripe_assinar(_assinatura(metadata={"usuario_id": usuario["id"]}))
    ativos = {n: m.start() for n, m in mocks.items()}
    try:
        with patch.object(stripe.Subscription, "retrieve_async",
                          new=AsyncMock(return_value=_assinatura(metadata={"usuario_id": usuario["id"]}))):
            resultado = _executar(pagamentos.assinar(usuario, "pm_card"))
    finally:
        for m in mocks.values():
            m.stop()

    assert resultado["status"] == "ok" and resultado["plano"] == "pro"
    params = ativos["criar_assinatura"].await_args.kwargs
    assert params["items"] == [{"price": "price_9_90"}]
    assert params["default_payment_method"] == "pm_card"
    assert params["metadata"] == {"usuario_id": usuario["id"]}
    ativos["anexar"].assert_awaited_once_with("pm_card", customer="cus_novo")
    assert fake.store["usuarios"][0]["stripe_customer_id"] == "cus_1"  # sincronizar grava o cliente da assinatura


def test_assinar_reaproveita_cliente_e_cancela_tentativas_incompletas(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1), stripe_customer_id="cus_9")
    mocks = _stripe_assinar(_assinatura(metadata={"usuario_id": usuario["id"]}), existentes=[{"id": "sub_velha"}])
    ativos = {n: m.start() for n, m in mocks.items()}
    try:
        with patch.object(stripe.Subscription, "retrieve_async",
                          new=AsyncMock(return_value=_assinatura(metadata={"usuario_id": usuario["id"]}))):
            _executar(pagamentos.assinar(usuario, "pm_card"))
    finally:
        for m in mocks.values():
            m.stop()

    ativos["criar_cliente"].assert_not_awaited()
    ativos["anexar"].assert_awaited_once_with("pm_card", customer="cus_9")
    ativos["cancelar"].assert_awaited_once_with("sub_velha")


def test_assinar_pede_3d_secure_quando_o_banco_exige(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))
    incompleta = _assinatura("incomplete", latest_invoice={"confirmation_secret": {"client_secret": "pi_77_secret_abc"}})
    mocks = _stripe_assinar(incompleta, intencao={"status": "requires_action"})
    ativos = {n: m.start() for n, m in mocks.items()}
    try:
        resultado = _executar(pagamentos.assinar(usuario, "pm_card"))
    finally:
        for m in mocks.values():
            m.stop()

    assert resultado == {"status": "requer_acao", "assinatura_id": "sub_1", "client_secret": "pi_77_secret_abc"}
    assert ativos["intencao"].await_args.args == ("pi_77",)
    ativos["cancelar"].assert_not_awaited()


def test_assinar_cartao_recusado_cancela_a_assinatura_e_explica(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))
    incompleta = _assinatura("incomplete", latest_invoice={"confirmation_secret": {"client_secret": "pi_77_secret_abc"}})
    mocks = _stripe_assinar(
        incompleta, intencao={"status": "requires_payment_method", "last_payment_error": {"decline_code": "insufficient_funds"}}
    )
    ativos = {n: m.start() for n, m in mocks.items()}
    try:
        with pytest.raises(pagamentos.CartaoRecusado, match="sem saldo"):
            _executar(pagamentos.assinar(usuario, "pm_card"))
    finally:
        for m in mocks.values():
            m.stop()

    ativos["cancelar"].assert_awaited_once_with("sub_1")


def test_assinar_recusa_metodo_de_pagamento_invalido(stripe_configurado):
    with pytest.raises(ValueError):
        _executar(pagamentos.assinar({"id": "u1"}, "tok_qualquer"))


def test_evento_de_fatura_paga_sincroniza_a_assinatura(stripe_configurado):
    sincronizar = AsyncMock()
    with patch.object(pagamentos, "sincronizar_assinatura", new=sincronizar):
        _executar(pagamentos.processar_evento(_obj(
            {"type": "invoice.payment_failed", "data": {"object": {"parent": {"subscription_details": {"subscription": "sub_7"}}}}}
        )))
        _executar(pagamentos.processar_evento(_obj({"type": "customer.subscription.deleted", "data": {"object": {"id": "sub_8"}}})))
        _executar(pagamentos.processar_evento(_obj({"type": "charge.succeeded", "data": {"object": {"id": "ch_1"}}})))

    assert [c.args[0] for c in sincronizar.await_args_list] == ["sub_7", "sub_8"]


# --------------------------------------------------------------------------
# Webhook HTTP
# --------------------------------------------------------------------------

class _Req:
    def __init__(self, corpo=b"{}", assinatura="t=1,v1=abc"):
        self._corpo = corpo
        self.headers = {"stripe-signature": assinatura}

    async def body(self):
        return self._corpo


def test_webhook_recusa_assinatura_invalida(stripe_configurado):
    with pytest.raises(HTTPException) as erro:
        _executar(stripe_webhook.receber_evento(_Req()))
    assert erro.value.status_code == 400


def test_webhook_sem_segredo_configurado_responde_503(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    with pytest.raises(HTTPException) as erro:
        _executar(stripe_webhook.receber_evento(_Req()))
    assert erro.value.status_code == 503


def test_webhook_assinado_processa_o_evento(stripe_configurado):
    import hashlib
    import hmac

    corpo = json.dumps({"id": "evt_1", "object": "event", "type": "customer.subscription.updated",
                        "data": {"object": {"id": "sub_1"}}}).encode()
    ts = int(time.time())
    assinatura = hmac.new(b"whsec_x", f"{ts}.".encode() + corpo, hashlib.sha256).hexdigest()

    with patch.object(pagamentos, "processar_evento", new=AsyncMock()) as processar:
        resposta = _executar(stripe_webhook.receber_evento(_Req(corpo, f"t={ts},v1={assinatura}")))

    assert resposta == {"status": "ok"}
    assert processar.await_args.args[0]["type"] == "customer.subscription.updated"


# --------------------------------------------------------------------------
# Cancelar / reativar pelo próprio site
# --------------------------------------------------------------------------

def test_cancelar_vale_no_fim_do_periodo_e_o_pro_continua_ate_la(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-10), stripe_subscription_id="sub_1", assinatura_status="active")
    modificar = AsyncMock()

    with patch.object(stripe.Subscription, "modify_async", new=modificar), \
         patch.object(stripe.Subscription, "retrieve_async",
                      new=AsyncMock(return_value=_assinatura(cancel_at_period_end=True, metadata={"usuario_id": usuario["id"]}))):
        resultado = _executar(pagamentos.alterar_cancelamento(usuario, True))

    modificar.assert_awaited_once_with("sub_1", cancel_at_period_end=True)
    assert resultado["cancela_no_fim"] is True
    assert resultado["plano"] == "pro"  # ainda tem acesso até o fim do período pago
    assert resultado["renova_em"]
    assert fake.store["usuarios"][0]["assinatura_cancela_no_fim"] is True


def test_reativar_desfaz_o_cancelamento(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(
        fake, teste_termina_em=_dias(-10), stripe_subscription_id="sub_1", assinatura_status="active",
        assinatura_cancela_no_fim=True,
    )
    modificar = AsyncMock()

    with patch.object(stripe.Subscription, "modify_async", new=modificar), \
         patch.object(stripe.Subscription, "retrieve_async",
                      new=AsyncMock(return_value=_assinatura(cancel_at_period_end=False, metadata={"usuario_id": usuario["id"]}))):
        resultado = _executar(pagamentos.alterar_cancelamento(usuario, False))

    modificar.assert_awaited_once_with("sub_1", cancel_at_period_end=False)
    assert resultado["cancela_no_fim"] is False and resultado["plano"] == "pro"


@pytest.mark.parametrize(
    "extra",
    [
        {},  # nunca assinou
        {"plano_cortesia": True},  # cortesia não tem assinatura no Stripe
        {"stripe_subscription_id": "sub_1", "assinatura_status": "canceled"},  # já encerrada
    ],
)
def test_cancelar_sem_assinatura_ativa_e_recusado(stripe_configurado, extra):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-10), **extra)
    modificar = AsyncMock()

    with patch.object(stripe.Subscription, "modify_async", new=modificar):
        with pytest.raises(ValueError):
            _executar(pagamentos.alterar_cancelamento(usuario, True))
    modificar.assert_not_awaited()


def test_cancelar_so_mexe_na_assinatura_do_proprio_usuario(stripe_configurado):
    """O id da assinatura vem do banco (linha do usuário logado), nunca do corpo da requisição."""
    import inspect

    from app.routes import web_api

    assert list(inspect.signature(web_api.cancelar_assinatura).parameters) == ["usuario"]
    assert list(inspect.signature(web_api.reativar_assinatura).parameters) == ["usuario"]


def test_rota_de_cancelar_traduz_os_erros(stripe_configurado):
    from fastapi import HTTPException

    from app.routes import web_api

    with pytest.raises(HTTPException) as erro:
        _executar(web_api.cancelar_assinatura(usuario={"id": "u1", "teste_termina_em": _dias(-1)}))
    assert erro.value.status_code == 400


# --------------------------------------------------------------------------
# Cartão e faturas no próprio site
# --------------------------------------------------------------------------

def test_dados_pagamento_mostra_cartao_e_faturas_sem_rascunhos(stripe_configurado):
    usuario = {"id": "u1", "stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1", "assinatura_status": "active"}
    assinatura = _obj({"id": "sub_1", "default_payment_method": {"id": "pm_1", "card": {"brand": "visa", "last4": "4242", "exp_month": 3, "exp_year": 2033}}})
    faturas = _obj({"data": [
        {"id": "in_1", "created": 1_800_000_000, "total": 990, "status": "paid", "invoice_pdf": "https://pdf", "hosted_invoice_url": "https://url"},
        {"id": "in_2", "created": 1_790_000_000, "total": 990, "status": "open", "invoice_pdf": None, "hosted_invoice_url": None},
        {"id": "in_3", "created": 1_780_000_000, "total": 0, "status": "draft"},
    ]})

    with patch.object(stripe.Subscription, "retrieve_async", new=AsyncMock(return_value=assinatura)), \
         patch.object(stripe.Invoice, "list_async", new=AsyncMock(return_value=faturas)), \
         patch.object(stripe.Charge, "list_async", new=AsyncMock(return_value=_obj({"data": []}))):
        dados = _executar(pagamentos.dados_pagamento(usuario))

    assert dados["cartao"] == {"marca": "visa", "final": "4242", "mes": 3, "ano": 2033}
    assert [(f["id"], f["valor"], f["status"]) for f in dados["faturas"]] == [("in_1", 9.9, "paga"), ("in_2", 9.9, "em_aberto")]
    assert dados["faturas"][0]["pdf"] == "https://pdf"


def test_dados_pagamento_sem_cliente_no_stripe_vem_vazio(stripe_configurado):
    assert _executar(pagamentos.dados_pagamento({"id": "u1"})) == {"cartao": None, "faturas": [], "proxima": None}


def test_dados_pagamento_de_quem_cancelou_usa_o_cartao_do_cliente(stripe_configurado):
    usuario = {"id": "u1", "stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1", "assinatura_status": "canceled"}
    cliente = _obj({"invoice_settings": {"default_payment_method": {"card": {"brand": "mastercard", "last4": "4444", "exp_month": 1, "exp_year": 2030}}}})
    buscar_assinatura = AsyncMock()

    with patch.object(stripe.Subscription, "retrieve_async", new=buscar_assinatura), \
         patch.object(stripe.Customer, "retrieve_async", new=AsyncMock(return_value=cliente)), \
         patch.object(stripe.Invoice, "list_async", new=AsyncMock(return_value=_obj({"data": []}))), \
         patch.object(stripe.Charge, "list_async", new=AsyncMock(return_value=_obj({"data": []}))):
        dados = _executar(pagamentos.dados_pagamento(usuario))

    buscar_assinatura.assert_not_awaited()
    assert dados["cartao"]["final"] == "4444"


def _usuario_assinante(**extra):
    return {"id": "u1", "stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1", "assinatura_status": "active", **extra}


def test_trocar_cartao_define_o_novo_como_padrao_e_remove_o_antigo(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-10), stripe_customer_id="cus_1", stripe_subscription_id="sub_1", assinatura_status="active")
    assinatura = _assinatura(default_payment_method="pm_antigo", metadata={"usuario_id": usuario["id"]})
    modificar_cliente, modificar_assinatura, remover = AsyncMock(), AsyncMock(), AsyncMock()

    with patch.object(stripe.PaymentMethod, "retrieve_async", new=AsyncMock(return_value=_obj({"id": "pm_novo", "customer": "cus_1"}))), \
         patch.object(stripe.Subscription, "retrieve_async", new=AsyncMock(return_value=assinatura)), \
         patch.object(stripe.Customer, "modify_async", new=modificar_cliente), \
         patch.object(stripe.Subscription, "modify_async", new=modificar_assinatura), \
         patch.object(stripe.PaymentMethod, "detach_async", new=remover):
        resultado = _executar(pagamentos.confirmar_troca_cartao(usuario, "pm_novo"))

    assert resultado["status"] == "ok"
    modificar_cliente.assert_awaited_once_with("cus_1", invoice_settings={"default_payment_method": "pm_novo"})
    modificar_assinatura.assert_awaited_once_with("sub_1", default_payment_method="pm_novo")
    remover.assert_awaited_once_with("pm_antigo")


def test_trocar_cartao_recusa_cartao_de_outro_cliente(stripe_configurado):
    modificar = AsyncMock()
    with patch.object(stripe.PaymentMethod, "retrieve_async", new=AsyncMock(return_value=_obj({"id": "pm_x", "customer": "cus_OUTRO"}))), \
         patch.object(stripe.Customer, "modify_async", new=modificar), \
         patch.object(stripe.Subscription, "modify_async", new=modificar):
        with pytest.raises(PermissionError):
            _executar(pagamentos.confirmar_troca_cartao(_usuario_assinante(), "pm_x"))
    modificar.assert_not_awaited()


def test_trocar_cartao_exige_assinatura_ativa_e_id_valido(stripe_configurado):
    for usuario in ({"id": "u1"}, _usuario_assinante(assinatura_status="canceled")):
        with pytest.raises(ValueError):
            _executar(pagamentos.confirmar_troca_cartao(usuario, "pm_x"))
    with pytest.raises(ValueError):
        _executar(pagamentos.confirmar_troca_cartao(_usuario_assinante(), "tok_qualquer"))
    with pytest.raises(ValueError):
        _executar(pagamentos.preparar_troca_cartao({"id": "u1"}))


def test_trocar_cartao_com_fatura_em_atraso_tenta_cobrar_de_novo(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-10), stripe_customer_id="cus_1", stripe_subscription_id="sub_1", assinatura_status="past_due")
    assinatura = _assinatura("past_due", latest_invoice="in_aberta", metadata={"usuario_id": usuario["id"]})
    cobrar = AsyncMock()

    with patch.object(stripe.PaymentMethod, "retrieve_async", new=AsyncMock(return_value=_obj({"id": "pm_novo", "customer": "cus_1"}))), \
         patch.object(stripe.Subscription, "retrieve_async", new=AsyncMock(return_value=assinatura)), \
         patch.object(stripe.Customer, "modify_async", new=AsyncMock()), \
         patch.object(stripe.Subscription, "modify_async", new=AsyncMock()), \
         patch.object(stripe.Invoice, "pay_async", new=cobrar):
        _executar(pagamentos.confirmar_troca_cartao(usuario, "pm_novo"))

    cobrar.assert_awaited_once_with("in_aberta", payment_method="pm_novo")


def test_preparar_troca_de_cartao_so_aceita_cartao(stripe_configurado):
    criar = AsyncMock(return_value=_obj({"client_secret": "seti_1_secret_x"}))
    with patch.object(stripe.SetupIntent, "create_async", new=criar):
        resultado = _executar(pagamentos.preparar_troca_cartao(_usuario_assinante()))

    assert resultado == {"client_secret": "seti_1_secret_x", "publishable_key": "pk_test_x"}
    params = criar.await_args.kwargs
    assert params["customer"] == "cus_1" and params["usage"] == "off_session"
    assert params["automatic_payment_methods"] == {"enabled": True, "allow_redirects": "never"}
    assert "payment_method_types" not in params  # a API nova do Stripe recusa esse parâmetro


def test_preco_novo_leva_o_nome_do_glicai_no_extrato_do_cartao(stripe_configurado, monkeypatch):
    monkeypatch.setattr(pagamentos, "_preco_em_cache", None)
    monkeypatch.setattr(settings, "stripe_price_id", "")
    criar = AsyncMock(return_value=_obj({"id": "price_novo"}))

    with patch.object(stripe.Price, "list_async", new=AsyncMock(return_value=_obj({"data": []}))), \
         patch.object(stripe.Price, "create_async", new=criar):
        assert _executar(pagamentos._preco_id()) == "price_novo"

    produto = criar.await_args.kwargs["product_data"]
    assert produto["statement_descriptor"] == "GLICIA PRO"
    assert len(pagamentos.DESCRITOR_EXTRATO) <= 22 and "BOLSO" not in pagamentos.DESCRITOR_EXTRATO
    monkeypatch.setattr(pagamentos, "_preco_em_cache", None)


def _fatura_paga(id_, pi, valor=990):
    return {"id": id_, "created": 1_800_000_000, "total": valor, "status": "paid", "invoice_pdf": "https://pdf", "hosted_invoice_url": None,
            "payments": {"data": [{"status": "paid", "payment": {"type": "payment_intent", "payment_intent": pi}}]}}


def test_fatura_reembolsada_aparece_como_reembolsada(stripe_configurado):
    usuario = {"id": "u1", "stripe_customer_id": "cus_1", "assinatura_status": "canceled"}
    faturas = _obj({"data": [
        _fatura_paga("in_ok", "pi_ok"),
        _fatura_paga("in_reemb", "pi_reemb"),
        _fatura_paga("in_parcial", "pi_parcial"),
        {"id": "in_void", "created": 1_700_000_000, "total": 990, "status": "void", "invoice_pdf": None, "hosted_invoice_url": None},
    ]})
    cobrancas = _obj({"data": [
        {"payment_intent": "pi_ok", "refunded": False, "amount_refunded": 0},
        {"payment_intent": "pi_reemb", "refunded": True, "amount_refunded": 990},
        {"payment_intent": "pi_parcial", "refunded": False, "amount_refunded": 400},
    ]})
    cliente = _obj({"invoice_settings": {"default_payment_method": None}})

    with patch.object(stripe.Customer, "retrieve_async", new=AsyncMock(return_value=cliente)), \
         patch.object(stripe.Invoice, "list_async", new=AsyncMock(return_value=faturas)), \
         patch.object(stripe.Charge, "list_async", new=AsyncMock(return_value=cobrancas)):
        dados = _executar(pagamentos.dados_pagamento(usuario))

    assert {f["id"]: f["status"] for f in dados["faturas"]} == {
        "in_ok": "paga", "in_reemb": "reembolsada", "in_parcial": "reembolso_parcial", "in_void": "cancelada",
    }


def test_proxima_cobranca_agendada_cancelada_ou_inexistente(stripe_configurado):
    base = {"id": "u1", "stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1", "assinatura_renova_em": "2026-11-09T12:00:00+00:00"}
    vazio = _obj({"data": []})

    def consultar(**extra):
        usuario = {**base, "assinatura_status": "active", **extra}
        assinatura = _obj({"id": "sub_1", "default_payment_method": None})
        cliente = _obj({"invoice_settings": {"default_payment_method": None}})
        with patch.object(stripe.Subscription, "retrieve_async", new=AsyncMock(return_value=assinatura)), \
             patch.object(stripe.Customer, "retrieve_async", new=AsyncMock(return_value=cliente)), \
             patch.object(stripe.Invoice, "list_async", new=AsyncMock(return_value=vazio)), \
             patch.object(stripe.Charge, "list_async", new=AsyncMock(return_value=vazio)):
            return _executar(pagamentos.dados_pagamento(usuario))["proxima"]

    assert consultar() == {"data": "2026-11-09T12:00:00+00:00", "valor": 9.9, "status": "agendada"}
    assert consultar(assinatura_cancela_no_fim=True)["status"] == "cancelada"
    assert consultar(assinatura_status="canceled") is None
