"""Rotas JSON protegidas do dashboard do site de acompanhamento — exigem sessão válida (ver web_auth.usuario_atual)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.routes.web_auth import usuario_atual
from app.services import auth_web
from app.services import cuidadores as cuidadores_service
from app.services import estoque as estoque_service
from app.services import medicos as medicos_service
from app.services import hba1c, pagamentos, padroes, perfil as perfil_service, planos, relatorios, visao_paciente
from app.services.exportacao import DIAS_MAXIMO, DIAS_PADRAO

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/historico")
async def historico(
    dias: int = Query(DIAS_PADRAO, ge=1, le=DIAS_MAXIMO),
    usuario: dict = Depends(usuario_atual),
):
    return await visao_paciente.historico_json(usuario["id"], dias)


@router.get("/perfil")
async def obter_perfil(usuario: dict = Depends(usuario_atual)):
    dados = await visao_paciente.perfil_json(usuario["id"])
    if dados is None:
        raise HTTPException(status_code=404, detail="Ainda não achei seu perfil glicêmico.")
    return dados


class AtualizarPerfilBody(BaseModel):
    campo: str
    valor: str


@router.put("/perfil")
async def atualizar_perfil(body: AtualizarPerfilBody, usuario: dict = Depends(usuario_atual)):
    """Mesmas regras de validação do comando `editar` no WhatsApp (ver app/services/perfil.py)."""
    try:
        if body.campo == "nome":
            await perfil_service.atualizar_nome(usuario["id"], body.valor)
        else:
            try:
                valor_numero = float(body.valor)
            except ValueError as erro_conversao:
                raise perfil_service.ErroValidacaoPerfil("Manda um número válido.") from erro_conversao
            await perfil_service.atualizar_campo_perfil(usuario["id"], body.campo, valor_numero)
    except perfil_service.ErroValidacaoPerfil as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro

    return {"status": "ok"}


@router.get("/relatorio")
async def relatorio(periodo: str = Query("semana"), usuario: dict = Depends(usuario_atual)):
    if periodo not in relatorios.DIAS_POR_PERIODO:
        raise HTTPException(status_code=400, detail="Período inválido. Use 'semana' ou 'mes'.")
    return await visao_paciente.relatorio_json(usuario["id"], periodo)


@router.get("/hba1c")
async def hba1c_estimativa(
    dias: int = Query(hba1c.DIAS_PADRAO, ge=1),
    usuario: dict = Depends(usuario_atual),
):
    return await visao_paciente.hba1c_json(usuario["id"], dias)


@router.get("/padroes")
async def padroes_detectados(
    dias: int = Query(padroes.DIAS_PADRAO, ge=1),
    usuario: dict = Depends(usuario_atual),
):
    return await visao_paciente.padroes_json(usuario["id"], dias)


@router.get("/cuidadores")
async def listar_cuidadores_dashboard(usuario: dict = Depends(usuario_atual)):
    lista = await cuidadores_service.buscar_cuidadores(usuario["id"])
    return {"cuidadores": [{"nome": c["nome"]} for c in lista]}


@router.post("/cuidadores/convite")
async def gerar_convite_dashboard(usuario: dict = Depends(usuario_atual)):
    return await cuidadores_service.criar_convite(usuario["id"])


@router.delete("/cuidadores/{nome}")
async def remover_cuidador_dashboard(nome: str, usuario: dict = Depends(usuario_atual)):
    alvo = await cuidadores_service.desativar_cuidador(usuario["id"], nome)
    if alvo is None:
        raise HTTPException(status_code=404, detail=f'Não achei "{nome}" na sua lista.')
    return {"status": "ok"}


@router.get("/estoque")
async def listar_estoque_dashboard(usuario: dict = Depends(usuario_atual)):
    linhas = await estoque_service.listar(usuario["id"])
    return {
        "itens": [
            {
                "tipo": l["tipo"],
                "label": estoque_service.TIPOS.get(l["tipo"], l["tipo"]),
                "quantidade_atual": l["quantidade_atual"],
                "quantidade_por_reposicao": l["quantidade_por_reposicao"],
                "limite_alerta": l["limite_alerta"],
            }
            for l in linhas
        ]
    }


class ConfigurarEstoqueBody(BaseModel):
    tipo: str
    quantidade_por_reposicao: float
    limite_alerta: float | None = None


@router.post("/estoque/configurar")
async def configurar_estoque_dashboard(body: ConfigurarEstoqueBody, usuario: dict = Depends(usuario_atual)):
    tipo = estoque_service.TIPOS_ENTRADA.get(body.tipo)
    if tipo is None:
        raise HTTPException(status_code=400, detail="Tipo não reconhecido. Use 'insulina' ou 'fita_dextro'.")
    if body.quantidade_por_reposicao <= 0:
        raise HTTPException(status_code=400, detail="Quantidade precisa ser maior que zero.")

    limite = body.limite_alerta
    if limite is None or limite < 0:
        limite = round(body.quantidade_por_reposicao * estoque_service.FRACAO_LIMITE_PADRAO, 1)

    await estoque_service.configurar(usuario["id"], tipo, body.quantidade_por_reposicao, limite)
    return {"status": "ok"}


class ReabastecerEstoqueBody(BaseModel):
    tipo: str
    quantidade: float


@router.post("/estoque/reabastecer")
async def reabastecer_estoque_dashboard(body: ReabastecerEstoqueBody, usuario: dict = Depends(usuario_atual)):
    tipo = estoque_service.TIPOS_ENTRADA.get(body.tipo)
    if tipo is None:
        raise HTTPException(status_code=400, detail="Tipo não reconhecido. Use 'insulina' ou 'fita_dextro'.")
    if body.quantidade <= 0:
        raise HTTPException(status_code=400, detail="Quantidade precisa ser maior que zero.")

    ok = await estoque_service.reabastecer(usuario["id"], tipo, body.quantidade)
    if not ok:
        raise HTTPException(status_code=404, detail="Esse tipo ainda não foi configurado.")
    return {"status": "ok"}


# --------------------------------------------------------------------------
# Médicos que acompanham o paciente
# --------------------------------------------------------------------------

@router.get("/medicos")
async def listar_medicos_dashboard(usuario: dict = Depends(usuario_atual)):
    return {"medicos": await medicos_service.medicos_do_paciente(usuario["id"])}


class VincularMedicoBody(BaseModel):
    codigo: str
    confirmar: bool = False


@router.post("/medicos/vincular")
async def vincular_medico_dashboard(body: VincularMedicoBody, usuario: dict = Depends(usuario_atual)):
    """
    Em dois passos, de propósito: com confirmar=false só mostra QUEM é o
    médico dono do código (nome e CRM); o acesso só é concedido quando o
    paciente confirma, já sabendo pra quem está liberando os dados.
    """
    try:
        medico = await medicos_service.buscar_por_codigo(body.codigo, usuario["id"])
    except (medicos_service.ErroMedico, auth_web.ErroAutenticacao) as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro

    publico = {"id": medico["id"], "nome": medico["nome"], "crm": medico["crm"], "uf": medico["uf"]}
    if not body.confirmar:
        return {"status": "confirmar", "medico": publico}

    novo = await medicos_service.vincular(usuario["id"], medico)
    return {"status": "vinculado" if novo else "ja_vinculado", "medico": publico}


@router.delete("/medicos/{medico_id}")
async def remover_medico_dashboard(medico_id: str, usuario: dict = Depends(usuario_atual)):
    if not await medicos_service.desvincular(medico_id, usuario["id"]):
        raise HTTPException(status_code=404, detail="Esse médico não está na sua lista.")
    return {"status": "ok"}


# --------------------------------------------------------------------------
# Plano e assinatura (Stripe)
# --------------------------------------------------------------------------

@router.get("/plano")
async def obter_plano(usuario: dict = Depends(usuario_atual)):
    return {
        **planos.resumo(usuario),
        "pagamentos_disponiveis": pagamentos.disponivel(),
        # chave publicável é pública por natureza (vai no JavaScript do site)
        "publishable_key": settings.stripe_publishable_key if pagamentos.disponivel() else None,
    }


class AssinarBody(BaseModel):
    metodo_pagamento_id: str


@router.post("/plano/assinar")
async def assinar_plano(body: AssinarBody, usuario: dict = Depends(usuario_atual)):
    """Recebe o pm_... gerado pelo Stripe no navegador e cria a assinatura."""
    if planos.plano_efetivo(usuario) == "pro":
        raise HTTPException(status_code=400, detail="Você já está no GlicAI Pro.")
    try:
        return await pagamentos.assinar(usuario, body.metodo_pagamento_id.strip())
    except ValueError as erro:
        raise HTTPException(status_code=400, detail="Dados do cartão inválidos. Tente de novo.") from erro
    except pagamentos.CartaoRecusado as erro:
        raise HTTPException(status_code=402, detail=str(erro)) from erro
    except pagamentos.PagamentosIndisponiveis as erro:
        raise HTTPException(status_code=503, detail="Pagamentos indisponíveis no momento.") from erro


class ConfirmarAssinaturaBody(BaseModel):
    assinatura_id: str


@router.post("/plano/confirmar")
async def confirmar_assinatura(body: ConfirmarAssinaturaBody, usuario: dict = Depends(usuario_atual)):
    """Chamado depois que o 3D Secure foi concluído no navegador."""
    try:
        return await pagamentos.confirmar(usuario, body.assinatura_id)
    except PermissionError as erro:
        raise HTTPException(status_code=403, detail="Essa assinatura não é sua.") from erro
    except pagamentos.PagamentosIndisponiveis as erro:
        raise HTTPException(status_code=503, detail="Pagamentos indisponíveis no momento.") from erro


@router.post("/plano/portal")
async def abrir_portal(usuario: dict = Depends(usuario_atual)):
    try:
        return {"url": await pagamentos.criar_portal(usuario)}
    except ValueError as erro:
        raise HTTPException(status_code=400, detail="Você ainda não tem uma assinatura.") from erro
    except pagamentos.PagamentosIndisponiveis as erro:
        raise HTTPException(status_code=503, detail="Pagamentos indisponíveis no momento.") from erro