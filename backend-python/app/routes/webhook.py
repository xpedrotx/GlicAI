import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services import cadastro, comandos, cuidadores
from app.services.supabase_client import supabase
from app.services.whatsapp_sender import enviar_mensagem

logger = logging.getLogger("glicia.webhook")

router = APIRouter()

_MENSAGEM_ERRO_INTERNO = (
    "Ops, deu um problema técnico aqui do meu lado. 😕\n"
    "Tenta de novo em alguns instantes — se continuar, me avisa."
)


class MensagemRecebida(BaseModel):
    telefone: str
    mensagem: str
    timestamp: int


def normalizar_telefone(telefone_whatsapp: str) -> str:
    """
    Guarda o JID completo (ex: '5545999999999@c.us' ou, para contas no novo
    sistema de identidade do WhatsApp, '123456789012345@lid') como
    identificador do usuário — sem cortar o sufixo. Contas endereçáveis só
    via @lid quebram se reconstruirmos o JID como @c.us mais tarde, então
    preservamos exatamente o que o WhatsApp mandou.
    """
    return telefone_whatsapp


def buscar_usuario(telefone: str) -> dict | None:
    resultado = supabase.table("usuarios").select("*").eq("telefone", telefone).execute()
    return resultado.data[0] if resultado.data else None


def criar_usuario(telefone: str) -> dict:
    novo_usuario = supabase.table("usuarios").insert({
        "telefone": telefone,
        "status_cadastro": "incompleto",
    }).execute()
    return novo_usuario.data[0]


async def _rotear_paciente(usuario: dict, mensagem: str) -> str:
    if usuario["status_cadastro"] == "incompleto":
        return await cadastro.processar_passo(usuario, mensagem)
    return await comandos.processar_comando(usuario, mensagem)


@router.post("/webhook")
async def receber_mensagem(
    payload: MensagemRecebida,
    x_internal_api_key: str = Header(None),
):
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Chave interna inválida")

    telefone = normalizar_telefone(payload.telefone)

    # O bot nunca pode ficar mudo por erro interno — silêncio é pior que uma
    # mensagem de erro, o paciente não sabe se foi recebido.
    try:
        # Checa "vincular <código> <nome>" antes de tratar como paciente
        # conhecido — senão um "oi" antes do vincular criaria um cadastro de
        # paciente incompleto sem querer.
        resposta_vinculo = await cuidadores.tentar_vincular(telefone, payload.mensagem)

        if resposta_vinculo is not None:
            resposta = resposta_vinculo
        else:
            usuario = buscar_usuario(telefone)

            if usuario is not None:
                resposta = await _rotear_paciente(usuario, payload.mensagem)
            elif await cuidadores.eh_cuidador(telefone):
                resposta = (
                    "Esse número só recebe avisos sobre quem te convidou. "
                    "Se precisar de algo, fale direto com a pessoa. 🙂"
                )
            else:
                usuario = criar_usuario(telefone)
                resposta = await _rotear_paciente(usuario, payload.mensagem)
    except Exception:
        logger.exception("Falha ao processar mensagem de %s", telefone)
        resposta = _MENSAGEM_ERRO_INTERNO

    try:
        await enviar_mensagem(payload.telefone, resposta)
    except Exception:
        logger.exception("Falha ao enviar resposta pra %s", telefone)

    return {"status": "recebido"}
