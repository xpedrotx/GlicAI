import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import monitoramento
from tests.fake_supabase import FakeSupabase

LIMITE = monitoramento.LIMITE_BYTES_PLANO_GRATUITO


def _executar(coro):
    return asyncio.run(coro)


def _mockar_httpx_post():
    """Monta um patch de httpx.AsyncClient cujo .post() é um AsyncMock que
    retorna uma resposta sem erro (raise_for_status não levanta)."""
    mock_client = AsyncMock()
    mock_resposta = MagicMock()
    mock_resposta.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resposta)

    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_cls, mock_client


def test_nao_alerta_abaixo_do_limiar():
    fake = FakeSupabase()
    monitoramento.supabase = fake
    fake.rpc_retornos["tamanho_banco_bytes"] = int(LIMITE * 0.5)

    mock_cls, mock_client = _mockar_httpx_post()
    with patch.object(monitoramento, "httpx") as mock_httpx:
        mock_httpx.AsyncClient = mock_cls
        _executar(monitoramento.verificar_uso_banco())

    mock_client.post.assert_not_awaited()
    assert fake.store.get("monitoramento_estado", []) == []


def test_alerta_quando_acima_do_limiar():
    fake = FakeSupabase()
    monitoramento.supabase = fake
    fake.rpc_retornos["tamanho_banco_bytes"] = int(LIMITE * 0.85)
    monitoramento.settings.resend_api_key = "chave-teste"

    mock_cls, mock_client = _mockar_httpx_post()
    try:
        with patch.object(monitoramento, "httpx") as mock_httpx:
            mock_httpx.AsyncClient = mock_cls
            _executar(monitoramento.verificar_uso_banco())
    finally:
        monitoramento.settings.resend_api_key = ""

    mock_client.post.assert_awaited_once()
    kwargs = mock_client.post.await_args.kwargs
    assert kwargs["json"]["to"] == [monitoramento.EMAIL_DESTINO]
    assert "GlicAI" in kwargs["json"]["subject"]
    assert "85%" in kwargs["json"]["subject"]

    estado = fake.store["monitoramento_estado"][0]
    assert estado["chave"] == "uso_banco"
    assert estado["valor"]["ultimo_alerta_em"] is not None


def test_sem_resend_api_key_nao_envia_e_nao_marca_estado():
    fake = FakeSupabase()
    monitoramento.supabase = fake
    fake.rpc_retornos["tamanho_banco_bytes"] = int(LIMITE * 0.9)
    monitoramento.settings.resend_api_key = ""

    mock_cls, mock_client = _mockar_httpx_post()
    with patch.object(monitoramento, "httpx") as mock_httpx:
        mock_httpx.AsyncClient = mock_cls
        _executar(monitoramento.verificar_uso_banco())

    mock_client.post.assert_not_awaited()
    assert fake.store.get("monitoramento_estado", []) == []


def test_nao_repete_alerta_dentro_da_janela_de_7_dias():
    fake = FakeSupabase()
    monitoramento.supabase = fake
    fake.rpc_retornos["tamanho_banco_bytes"] = int(LIMITE * 0.9)
    monitoramento.settings.resend_api_key = "chave-teste"

    recente = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    fake.table("monitoramento_estado").insert(
        {"chave": "uso_banco", "valor": {"ultimo_alerta_em": recente}}
    ).execute()

    mock_cls, mock_client = _mockar_httpx_post()
    try:
        with patch.object(monitoramento, "httpx") as mock_httpx:
            mock_httpx.AsyncClient = mock_cls
            _executar(monitoramento.verificar_uso_banco())
    finally:
        monitoramento.settings.resend_api_key = ""

    mock_client.post.assert_not_awaited()


def test_alerta_de_novo_apos_janela_expirar():
    fake = FakeSupabase()
    monitoramento.supabase = fake
    fake.rpc_retornos["tamanho_banco_bytes"] = int(LIMITE * 0.9)
    monitoramento.settings.resend_api_key = "chave-teste"

    antigo = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    fake.table("monitoramento_estado").insert(
        {"chave": "uso_banco", "valor": {"ultimo_alerta_em": antigo}}
    ).execute()

    mock_cls, mock_client = _mockar_httpx_post()
    try:
        with patch.object(monitoramento, "httpx") as mock_httpx:
            mock_httpx.AsyncClient = mock_cls
            _executar(monitoramento.verificar_uso_banco())
    finally:
        monitoramento.settings.resend_api_key = ""

    mock_client.post.assert_awaited_once()
