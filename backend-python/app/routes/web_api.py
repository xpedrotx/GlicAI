"""Rotas JSON protegidas do dashboard do site de acompanhamento — exigem sessão válida (ver web_auth.usuario_atual)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.routes.web_auth import usuario_atual
from app.services import cuidadores as cuidadores_service
from app.services import estoque as estoque_service
from app.services import hba1c, padroes, perfil as perfil_service, relatorios
from app.services.exportacao import DIAS_MAXIMO, DIAS_PADRAO, buscar_dados_historico

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/historico")
async def historico(
    dias: int = Query(DIAS_PADRAO, ge=1, le=DIAS_MAXIMO),
    usuario: dict = Depends(usuario_atual),
):
    """
    Mesmos dados que alimentam o PDF de exportação (buscar_dados_historico,
    reaproveitado de exportacao.py), só que em JSON pro dashboard — a
    classificação clínica (cor/seta por faixa) fica a cargo do front-end,
    que já recebe meta/limite_baixo/limite_alto pra calcular igual.
    """
    dados = await buscar_dados_historico(usuario["id"], dias)
    if dados is None:
        return {"perfil": None, "timezone": None, "periodo": None, "glicemias": [], "bolus": []}

    perfil = dados["perfil"]
    return {
        "perfil": {
            "meta_glicemia": perfil["meta_glicemia"],
            "limite_baixo": perfil["limite_baixo"],
            "limite_alto": perfil["limite_alto"],
        },
        "timezone": dados["usuario"].get("timezone") or "America/Sao_Paulo",
        "periodo": {
            "inicio": dados["data_inicio"].isoformat(),
            "fim": dados["data_fim"].isoformat(),
        },
        "glicemias": [
            {"horario": g["horario"], "valor": g["valor"], "contexto": g.get("contexto")}
            for g in dados["glicemias"]
        ],
        "bolus": [
            {
                "horario": b["horario"],
                "carboidratos_g": b.get("carboidratos_g"),
                "glicemia_referencia": b.get("glicemia_referencia"),
                "dose_calculada": b.get("dose_calculada"),
                "dose_aplicada": b.get("dose_aplicada"),
            }
            for b in dados["bolus"]
        ],
    }


@router.get("/perfil")
async def obter_perfil(usuario: dict = Depends(usuario_atual)):
    """Mesmo dado que _perfil()/_basal() mostram em texto no WhatsApp (comandos.py), estruturado pro dashboard."""
    dados = await perfil_service.buscar_perfil_completo(usuario["id"])
    if dados is None:
        raise HTTPException(status_code=404, detail="Ainda não achei seu perfil glicêmico.")

    p = dados["perfil"]
    return {
        "nome": dados["nome"],
        "meta_glicemia": p["meta_glicemia"],
        "limite_baixo": p["limite_baixo"],
        "limite_alto": p["limite_alto"],
        "fator_sensibilidade": p["fator_sensibilidade"],
        "tempo_insulina_ativa_horas": p.get("tempo_insulina_ativa_horas"),
        "relacoes_ic": [
            {
                "periodo": r["periodo"],
                "hora_inicio": str(r["hora_inicio"])[:5],
                "hora_fim": str(r["hora_fim"])[:5],
                "gramas_por_unidade": r["gramas_por_unidade"],
            }
            for r in dados["relacoes_ic"]
        ],
        "basal": [
            {"horario": str(b["horario"])[:5], "dose": b["dose"], "tipo_insulina": b.get("tipo_insulina")}
            for b in dados["basal"]
        ],
        "modificadores": [
            {
                "nome": m["nome"],
                "tipo_ajuste": m["tipo_ajuste"],
                "valor_ajuste": m["valor_ajuste"],
                "ativo": m["ativo"],
            }
            for m in dados["modificadores"]
        ],
    }


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
    """Mesmos dados do resumo periódico mandado automaticamente no WhatsApp (relatorios.py), em JSON."""
    if periodo not in relatorios.DIAS_POR_PERIODO:
        raise HTTPException(status_code=400, detail="Período inválido. Use 'semana' ou 'mes'.")

    dados = await relatorios.buscar_dados_relatorio(usuario["id"], periodo)
    if dados is None:
        return {"perfil": None}

    valores = [g["valor"] for g in dados["glicemias"]]
    limite_baixo = dados["perfil"]["limite_baixo"]
    limite_alto = dados["perfil"]["limite_alto"]
    na_faixa = sum(1 for v in valores if limite_baixo <= v <= limite_alto)
    hipos = sum(1 for v in valores if v < limite_baixo)
    hipers = sum(1 for v in valores if v > limite_alto)

    dias_periodo = max(1, (dados["data_fim"] - dados["data_inicio"]).days)
    total_insulina = sum(dados["doses_aplicadas"])

    return {
        "perfil": {"limite_baixo": limite_baixo, "limite_alto": limite_alto},
        "periodo": periodo,
        "data_inicio": dados["data_inicio"].isoformat(),
        "data_fim": dados["data_fim"].isoformat(),
        "num_medicoes": len(valores),
        "media_glicemia": (sum(valores) / len(valores)) if valores else None,
        "na_faixa_pct": round(100 * na_faixa / len(valores)) if valores else None,
        "hipoglicemias": hipos,
        "hiperglicemias": hipers,
        "doses_aplicadas": len(dados["doses_aplicadas"]),
        "total_insulina": total_insulina if dados["doses_aplicadas"] else None,
        "media_insulina_dia": (total_insulina / dias_periodo) if dados["doses_aplicadas"] else None,
        "eventos_criticos": dados["eventos_criticos"],
    }


@router.get("/hba1c")
async def hba1c_estimativa(
    dias: int = Query(hba1c.DIAS_PADRAO, ge=1),
    usuario: dict = Depends(usuario_atual),
):
    """Mesma estimativa de GMI/HbA1c do comando *hba1c* no WhatsApp (hba1c.py)."""
    estimativa = await hba1c.gerar_estimativa(usuario["id"], dias)
    if estimativa is None:
        return {"disponivel": False, "minimo_medicoes": hba1c.MINIMO_MEDICOES, "dias": dias}
    return {"disponivel": True, **estimativa}


@router.get("/padroes")
async def padroes_detectados(
    dias: int = Query(padroes.DIAS_PADRAO, ge=1),
    usuario: dict = Depends(usuario_atual),
):
    """Mesma detecção de padrões do comando *padroes* no WhatsApp (padroes.py)."""
    lista = await padroes.detectar_padroes(usuario["id"], dias)
    return {
        "dias": dias,
        "padroes": [
            {
                "dia_semana_label": padroes.DIAS_SEMANA_PT[p["dia_semana"]],
                "periodo": p["periodo"],
                "media": p["media"],
                "tipo": p["tipo"],
                "n": p["n"],
            }
            for p in lista
        ],
    }


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
