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
        _executar(pagamentos.criar_checkout({"id": "u1"}))


def test_checkout_cobra_9_90_por_mes_e_marca_o_usuario(stripe_configurado):
    criar = AsyncMock(return_value={"client_secret": "cs_123"})
    with patch.object(stripe.checkout.Session, "create_async", new=criar):
        resultado = _executar(pagamentos.criar_checkout({"id": "u1"}))

    assert resultado == {"client_secret": "cs_123", "publishable_key": "pk_test_x"}
    params = criar.await_args.kwargs
    assert params["mode"] == "subscription"
    assert params["ui_mode"] == "embedded_page"
    assert params["metadata"] == {"usuario_id": "u1"}
    preco = params["line_items"][0]["price_data"]
    assert (preco["currency"], preco["unit_amount"], preco["recurring"]["interval"]) == ("brl", 990, "month")
    assert "customer" not in params


def test_checkout_reaproveita_cliente_existente(stripe_configurado):
    criar = AsyncMock(return_value={"client_secret": "cs_1"})
    with patch.object(stripe.checkout.Session, "create_async", new=criar):
        _executar(pagamentos.criar_checkout({"id": "u1", "stripe_customer_id": "cus_9"}))
    assert criar.await_args.kwargs["customer"] == "cus_9"


def _assinatura(status="active", **extra):
    return {
        "id": "sub_1", "status": status, "customer": "cus_1", "metadata": {"usuario_id": None},
        "items": {"data": [{"current_period_end": int(time.time()) + 86400 * 30}]}, **extra,
    }


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


def test_confirmar_sessao_recusa_sessao_de_outro_usuario(stripe_configurado):
    sessao = {"metadata": {"usuario_id": "outro"}, "status": "complete", "subscription": "sub_1"}
    with patch.object(stripe.checkout.Session, "retrieve_async", new=AsyncMock(return_value=sessao)):
        with pytest.raises(PermissionError):
            _executar(pagamentos.confirmar_sessao({"id": "u1"}, "cs_1"))


def test_confirmar_sessao_paga_libera_na_hora(stripe_configurado):
    fake = FakeSupabase()
    _ligar(fake)
    usuario = _usuario(fake, teste_termina_em=_dias(-1))
    sessao = {"metadata": {"usuario_id": usuario["id"]}, "status": "complete", "subscription": "sub_1"}

    with patch.object(stripe.checkout.Session, "retrieve_async", new=AsyncMock(return_value=sessao)), \
         patch.object(stripe.Subscription, "retrieve_async", new=AsyncMock(return_value=_assinatura())):
        resultado = _executar(pagamentos.confirmar_sessao(usuario, "cs_1"))

    assert resultado["status"] == "ok"
    assert resultado["plano"] == "pro"


def test_confirmar_sessao_ainda_nao_paga_fica_pendente(stripe_configurado):
    sessao = {"metadata": {"usuario_id": "u1"}, "status": "open"}
    with patch.object(stripe.checkout.Session, "retrieve_async", new=AsyncMock(return_value=sessao)):
        resultado = _executar(pagamentos.confirmar_sessao({"id": "u1", "teste_termina_em": _dias(-1)}, "cs_1"))
    assert resultado["status"] == "pendente"
    assert resultado["plano"] == "free"


def test_portal_exige_cliente_do_stripe(stripe_configurado):
    with pytest.raises(ValueError):
        _executar(pagamentos.criar_portal({"id": "u1"}))

    abrir = AsyncMock(return_value={"url": "https://billing.stripe.com/p/x"})
    with patch.object(stripe.billing_portal.Session, "create_async", new=abrir):
        assert _executar(pagamentos.criar_portal({"id": "u1", "stripe_customer_id": "cus_1"})) == "https://billing.stripe.com/p/x"


def test_evento_de_fatura_paga_sincroniza_a_assinatura(stripe_configurado):
    sincronizar = AsyncMock()
    with patch.object(pagamentos, "sincronizar_assinatura", new=sincronizar):
        _executar(pagamentos.processar_evento(
            {"type": "invoice.payment_failed", "data": {"object": {"parent": {"subscription_details": {"subscription": "sub_7"}}}}}
        ))
        _executar(pagamentos.processar_evento({"type": "customer.subscription.deleted", "data": {"object": {"id": "sub_8"}}}))
        _executar(pagamentos.processar_evento({"type": "charge.succeeded", "data": {"object": {"id": "ch_1"}}}))

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
