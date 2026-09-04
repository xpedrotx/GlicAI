import asyncio
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.routes import webhook


def _executar(coro):
    return asyncio.run(coro)


def _payload(mensagem="oi", telefone="5545999999999@c.us"):
    return webhook.MensagemRecebida(telefone=telefone, mensagem=mensagem, timestamp=0)


def test_webhook_responde_normalmente_quando_tudo_ok():
    usuario = {"id": "u1", "telefone": "5545999999999@c.us", "status_cadastro": "completo"}

    with patch.object(webhook.cuidadores, "tentar_vincular", new=AsyncMock(return_value=None)), \
         patch.object(webhook, "buscar_usuario", return_value=usuario), \
         patch.object(webhook.comandos, "processar_comando", new=AsyncMock(return_value="tudo certo")), \
         patch.object(webhook, "enviar_mensagem", new=AsyncMock()) as mock_enviar:
        resultado = _executar(
            webhook.receber_mensagem(_payload("oi"), x_internal_api_key=settings.internal_api_key)
        )

    assert resultado == {"status": "recebido"}
    mock_enviar.assert_awaited_once_with("5545999999999@c.us", "tudo certo")


def test_webhook_erro_interno_nunca_deixa_o_bot_mudo():
    """
    Reproduz o bug real: um erro inesperado (ex: instabilidade do banco)
    durante o processamento não pode derrubar a resposta inteira sem avisar
    nada ao paciente — silêncio total é pior que uma mensagem de erro.
    """
    usuario = {"id": "u1", "telefone": "5545999999999@c.us", "status_cadastro": "completo"}

    with patch.object(webhook.cuidadores, "tentar_vincular", new=AsyncMock(return_value=None)), \
         patch.object(webhook, "buscar_usuario", return_value=usuario), \
         patch.object(
             webhook.comandos, "processar_comando",
             new=AsyncMock(side_effect=RuntimeError("falha simulada do banco")),
         ), \
         patch.object(webhook, "enviar_mensagem", new=AsyncMock()) as mock_enviar:
        resultado = _executar(
            webhook.receber_mensagem(_payload("glicemias 73"), x_internal_api_key=settings.internal_api_key)
        )

    assert resultado == {"status": "recebido"}
    mock_enviar.assert_awaited_once()
    telefone_enviado, texto_enviado = mock_enviar.await_args.args
    assert telefone_enviado == "5545999999999@c.us"
    assert texto_enviado == webhook._MENSAGEM_ERRO_INTERNO


def test_webhook_ignora_mensagem_de_status_broadcast():
    """status@broadcast é o próprio WhatsApp mandando atualização de status,
    nunca um paciente — não pode virar "usuário" incompleto no banco."""
    with patch.object(webhook, "criar_usuario") as mock_criar, \
         patch.object(webhook, "enviar_mensagem", new=AsyncMock()) as mock_enviar:
        resultado = _executar(
            webhook.receber_mensagem(
                _payload("oi", telefone="status@broadcast"), x_internal_api_key=settings.internal_api_key
            )
        )

    assert resultado == {"status": "ignorado"}
    mock_criar.assert_not_called()
    mock_enviar.assert_not_awaited()


def test_webhook_ignora_jid_malformado():
    with patch.object(webhook, "criar_usuario") as mock_criar, \
         patch.object(webhook, "enviar_mensagem", new=AsyncMock()) as mock_enviar:
        resultado = _executar(
            webhook.receber_mensagem(_payload("oi", telefone="0@c.us"), x_internal_api_key=settings.internal_api_key)
        )

    assert resultado == {"status": "ignorado"}
    mock_criar.assert_not_called()
    mock_enviar.assert_not_awaited()


def test_webhook_detecta_sinal_de_risco_e_responde_com_apoio_sem_rotear_comando():
    """Mensagem de risco tem prioridade absoluta — nunca chega a checar
    vínculo de cuidador nem rotear como comando normal de paciente."""
    with patch.object(webhook.cuidadores, "tentar_vincular", new=AsyncMock()) as mock_vincular, \
         patch.object(webhook, "buscar_usuario") as mock_buscar, \
         patch.object(webhook, "enviar_mensagem", new=AsyncMock()) as mock_enviar:
        resultado = _executar(
            webhook.receber_mensagem(_payload("eu quero morrer"), x_internal_api_key=settings.internal_api_key)
        )

    assert resultado == {"status": "recebido"}
    mock_vincular.assert_not_called()
    mock_buscar.assert_not_called()
    mock_enviar.assert_awaited_once()
    telefone_enviado, texto_enviado = mock_enviar.await_args.args
    assert telefone_enviado == "5545999999999@c.us"
    assert "188" in texto_enviado


def test_webhook_falha_ao_enviar_resposta_nao_derruba_o_endpoint():
    usuario = {"id": "u1", "telefone": "5545999999999@c.us", "status_cadastro": "completo"}

    with patch.object(webhook.cuidadores, "tentar_vincular", new=AsyncMock(return_value=None)), \
         patch.object(webhook, "buscar_usuario", return_value=usuario), \
         patch.object(webhook.comandos, "processar_comando", new=AsyncMock(return_value="oi")), \
         patch.object(webhook, "enviar_mensagem", new=AsyncMock(side_effect=RuntimeError("bridge fora do ar"))):
        resultado = _executar(
            webhook.receber_mensagem(_payload("oi"), x_internal_api_key=settings.internal_api_key)
        )

    assert resultado == {"status": "recebido"}
