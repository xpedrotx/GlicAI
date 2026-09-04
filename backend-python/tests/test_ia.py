import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import ia


def _executar(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------
# gerar_dicas: nunca pode travar o alerta de hiper/hipo — sem chave, com
# falha na API, ou com resposta vazia, sempre cai pro fallback fixo.
# --------------------------------------------------------------------------

def test_gerar_dicas_sem_chave_configurada_usa_padrao():
    ia._client = None
    with patch.object(ia.settings, "anthropic_api_key", ""):
        dicas = _executar(ia.gerar_dicas("hiperglicemia", 205))
    assert dicas == ia.DICAS_PADRAO["hiperglicemia"]


def test_gerar_dicas_com_falha_na_api_usa_padrao():
    client_mock = AsyncMock()
    client_mock.messages.create = AsyncMock(side_effect=Exception("boom"))
    with patch.object(ia, "_get_client", return_value=client_mock):
        dicas = _executar(ia.gerar_dicas("hipoglicemia", 55))
    assert dicas == ia.DICAS_PADRAO["hipoglicemia"]


def test_gerar_dicas_resposta_vazia_usa_padrao():
    resposta = SimpleNamespace(content=[])
    client_mock = AsyncMock()
    client_mock.messages.create = AsyncMock(return_value=resposta)
    with patch.object(ia, "_get_client", return_value=client_mock):
        dicas = _executar(ia.gerar_dicas("hiperglicemia", 205))
    assert dicas == ia.DICAS_PADRAO["hiperglicemia"]


def test_gerar_dicas_parseia_resposta_da_ia_e_ignora_itens_vazios():
    bloco = SimpleNamespace(
        type="tool_use", name="dar_dicas", input={"dicas": ["Beba água", "   ", "Descanse um pouco"]}
    )
    resposta = SimpleNamespace(content=[bloco])
    client_mock = AsyncMock()
    client_mock.messages.create = AsyncMock(return_value=resposta)
    with patch.object(ia, "_get_client", return_value=client_mock):
        dicas = _executar(ia.gerar_dicas("hiperglicemia", 205))
    assert dicas == ["Beba água", "Descanse um pouco"]


def test_gerar_dicas_limita_a_quatro_itens():
    bloco = SimpleNamespace(
        type="tool_use",
        name="dar_dicas",
        input={"dicas": ["um", "dois", "tres", "quatro", "cinco"]},
    )
    resposta = SimpleNamespace(content=[bloco])
    client_mock = AsyncMock()
    client_mock.messages.create = AsyncMock(return_value=resposta)
    with patch.object(ia, "_get_client", return_value=client_mock):
        dicas = _executar(ia.gerar_dicas("hipoglicemia", 55))
    assert dicas == ["um", "dois", "tres", "quatro"]
