"""Rotas HTTP de login/sessão do site de acompanhamento (CPF + senha)."""
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

from app.config import settings
from app.services import auth_web

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NOME = "glicai_sessao"


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
async def confirmar_codigo(body: ConfirmarCodigoBody, response: Response):
    try:
        token = await auth_web.confirmar_codigo(body.codigo.strip(), body.cpf, body.senha)
    except auth_web.ErroAutenticacao as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro

    _setar_cookie_sessao(response, token)
    return {"status": "ok"}


class LoginBody(BaseModel):
    cpf: str
    senha: str


@router.post("/login")
async def login(body: LoginBody, response: Response):
    try:
        token = await auth_web.login(body.cpf, body.senha)
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
