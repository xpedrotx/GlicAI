"""Rotas do painel do médico: conta/sessão própria (cookie glicai_medico) e leitura dos pacientes vinculados."""
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from app.config import settings
from app.routes.web_auth import _ip_cliente
from app.services import auth_web, hba1c, medicos, padroes, relatorios, visao_paciente
from app.services.exportacao import DIAS_MAXIMO, DIAS_PADRAO

router = APIRouter(prefix="/api/medico", tags=["medico"])

COOKIE_NOME = "glicai_medico"


def _setar_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NOME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=auth_web.DIAS_VALIDADE_SESSAO * 24 * 3600,
        path="/",
    )


async def medico_atual(glicai_medico: str | None = Cookie(default=None)) -> dict:
    medico = await medicos.validar_sessao(glicai_medico)
    if medico is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    return medico


async def paciente_do_medico(paciente_id: str, medico: dict = Depends(medico_atual)) -> dict:
    """404 (e não 403) pra paciente sem vínculo: não confirma nem que o id existe."""
    paciente = await medicos.paciente_autorizado(medico["id"], paciente_id)
    if paciente is None:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    return paciente


class CadastroBody(BaseModel):
    nome: str
    email: str
    crm: str
    uf: str
    senha: str


@router.post("/cadastro")
async def cadastro(body: CadastroBody, request: Request, response: Response):
    try:
        token = await medicos.cadastrar(body.nome, body.email, body.crm, body.uf, body.senha, _ip_cliente(request))
    except auth_web.ErroAutenticacao as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    _setar_cookie(response, token)
    return {"status": "ok"}


class LoginBody(BaseModel):
    email: str
    senha: str


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response):
    try:
        token = await medicos.login(body.email, body.senha, _ip_cliente(request))
    except auth_web.ErroAutenticacao as erro:
        raise HTTPException(status_code=401, detail=str(erro)) from erro
    _setar_cookie(response, token)
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response, glicai_medico: str | None = Cookie(default=None)):
    if glicai_medico:
        await medicos.logout(glicai_medico)
    response.delete_cookie(COOKIE_NOME, path="/")
    return {"status": "ok"}


@router.get("/me")
async def me(medico: dict = Depends(medico_atual)):
    return medicos.dados_publicos(medico)


@router.get("/pacientes")
async def listar_pacientes(medico: dict = Depends(medico_atual)):
    return {"pacientes": await medicos.pacientes_do_medico(medico["id"])}


@router.get("/pacientes/{paciente_id}")
async def resumo_paciente(paciente_id: str, medico: dict = Depends(medico_atual)):
    resumo = await medicos.resumo_do_paciente(medico["id"], paciente_id)
    if resumo is None:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    return resumo


@router.delete("/pacientes/{paciente_id}")
async def desvincular_paciente(paciente_id: str, medico: dict = Depends(medico_atual)):
    if not await medicos.desvincular(medico["id"], paciente_id):
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    return {"status": "ok"}


@router.get("/pacientes/{paciente_id}/historico")
async def historico_paciente(
    dias: int = Query(DIAS_PADRAO, ge=1, le=DIAS_MAXIMO),
    paciente: dict = Depends(paciente_do_medico),
):
    return await visao_paciente.historico_json(paciente["id"], dias)


@router.get("/pacientes/{paciente_id}/perfil")
async def perfil_paciente(paciente: dict = Depends(paciente_do_medico)):
    dados = await visao_paciente.perfil_json(paciente["id"])
    if dados is None:
        raise HTTPException(status_code=404, detail="Esse paciente ainda não terminou o cadastro.")
    return dados


@router.get("/pacientes/{paciente_id}/relatorio")
async def relatorio_paciente(periodo: str = Query("semana"), paciente: dict = Depends(paciente_do_medico)):
    if periodo not in relatorios.DIAS_POR_PERIODO:
        raise HTTPException(status_code=400, detail="Período inválido. Use 'semana' ou 'mes'.")
    return await visao_paciente.relatorio_json(paciente["id"], periodo)


@router.get("/pacientes/{paciente_id}/hba1c")
async def hba1c_paciente(dias: int = Query(hba1c.DIAS_PADRAO, ge=1), paciente: dict = Depends(paciente_do_medico)):
    return await visao_paciente.hba1c_json(paciente["id"], dias)


@router.get("/pacientes/{paciente_id}/padroes")
async def padroes_paciente(dias: int = Query(padroes.DIAS_PADRAO, ge=1), paciente: dict = Depends(paciente_do_medico)):
    return await visao_paciente.padroes_json(paciente["id"], dias)
