import base64

import httpx
from app.config import settings


async def enviar_mensagem(telefone: str, mensagem: str) -> None:
    """
    Chama o bridge Node.js para enviar uma mensagem ao paciente no WhatsApp.
    Usado para respostas, lembretes de medição/aplicação e alertas de
    hipo/hiperglicemia.

    Timeout generoso (40s): o bridge simula "digitando..." por 5-10s antes
    de mandar de verdade (ver _simularDigitando em whatsappClient.js), e
    ainda pode levar +5s se precisar de 1 retry do envio em si.
    """
    async with httpx.AsyncClient(timeout=40.0) as client:
        resposta = await client.post(
            f"{settings.node_bridge_url}/send",
            json={"telefone": telefone, "mensagem": mensagem},
            headers={"x-internal-api-key": settings.internal_api_key},
        )
        resposta.raise_for_status()


async def enviar_arquivo(telefone: str, nome_arquivo: str, mimetype: str, conteudo: bytes) -> None:
    """Chama o bridge Node.js para enviar um arquivo (ex: PDF de exportação) como documento.

    Timeout generoso (50s): mesma simulação de "digitando..." (5-10s) do
    enviar_mensagem, mais o tempo de upload do arquivo em si e uma margem
    pro retry — arquivo demora mais que texto simples.
    """
    conteudo_base64 = base64.b64encode(conteudo).decode("ascii")
    async with httpx.AsyncClient(timeout=50.0) as client:
        resposta = await client.post(
            f"{settings.node_bridge_url}/send-arquivo",
            json={
                "telefone": telefone,
                "nome_arquivo": nome_arquivo,
                "mimetype": mimetype,
                "conteudo_base64": conteudo_base64,
            },
            headers={"x-internal-api-key": settings.internal_api_key},
        )
        resposta.raise_for_status()
