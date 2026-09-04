import base64

import httpx
from app.config import settings


async def enviar_mensagem(telefone: str, mensagem: str) -> None:
    """
    Chama o bridge Node.js para enviar uma mensagem ao paciente no WhatsApp.
    Usado para respostas, lembretes de medição/aplicação e alertas de
    hipo/hiperglicemia.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        resposta = await client.post(
            f"{settings.node_bridge_url}/send",
            json={"telefone": telefone, "mensagem": mensagem},
            headers={"x-internal-api-key": settings.internal_api_key},
        )
        resposta.raise_for_status()


async def enviar_arquivo(telefone: str, nome_arquivo: str, mimetype: str, conteudo: bytes) -> None:
    """Chama o bridge Node.js para enviar um arquivo (ex: PDF de exportação) como documento."""
    conteudo_base64 = base64.b64encode(conteudo).decode("ascii")
    async with httpx.AsyncClient(timeout=30.0) as client:
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
