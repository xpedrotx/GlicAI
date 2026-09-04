"""Rotas HTTP de login/sessão do site de acompanhamento (CPF + senha)."""
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.config import settings
from app.services import auth_web

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NOME = "glicai_sessao"


def _ip_cliente(request: Request) -> str:
    """IP real do paciente, não o do container do Caddy — o backend só é
    alcançado via reverse_proxy, então o IP de conexão TCP (request.client)
    é sempre o do Caddy. Caddy repassa o IP real em X-Forwarded-For."""
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


def _setar_cookie_sessao(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NOME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=auth_web.DIAS_VALIDADE_SESSAO * 24 * 3600,
        path="/",
    )


async def usuario_atual(glicai_sessao: str | None = Cookie(default=None)) -> dict:
    """Dependency pras rotas protegidas do dashboard (fase 2+) — 401 se a sessão não for válida."""
    usuario = await auth_web.validar_sessao(glicai_sessao)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    return usuario


class ConfirmarCodigoBody(BaseModel):
    codigo: str
    cpf: str
    senha: str


@router.post("/confirmar-codigo")
async def confirmar_codigo(body: ConfirmarCodigoBody, request: Request, response: Response):
    try:
        token = await auth_web.confirmar_codigo(body.codigo.strip(), body.cpf, body.senha, _ip_cliente(request))
    except auth_web.ErroAutenticacao as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro

    _setar_cookie_sessao(response, token)
    return {"status": "ok"}


class LoginBody(BaseModel):
    cpf: str
    senha: str


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response):
    try:
        token = await auth_web.login(body.cpf, body.senha, _ip_cliente(request))
    except auth_web.ErroAutenticacao as erro:
        raise HTTPException(status_code=401, detail=str(erro)) from erro

    _setar_cookie_sessao(response, token)
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response, glicai_sessao: str | None = Cookie(default=None)):
    if glicai_sessao:
        await auth_web.logout(glicai_sessao)
    response.delete_cookie(COOKIE_NOME, path="/")
    return {"status": "ok"}


@router.get("/me")
async def me(usuario: dict = Depends(usuario_atual)):
    return {"nome": usuario.get("nome"), "telefone": usuario.get("telefone")}
