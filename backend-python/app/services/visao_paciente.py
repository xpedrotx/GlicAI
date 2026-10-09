"""
Dados do paciente em JSON, do jeito que o site mostra.

Usado pelo painel do próprio paciente (routes/web_api.py) e pelo painel do
médico (routes/medico_api.py): as duas telas precisam mostrar exatamente os
mesmos números, então a montagem fica num lugar só. Quem chama é responsável
por já ter autorizado o acesso a esse usuario_id.
"""
from app.services import hba1c, padroes, relatorios
from app.services import perfil as perfil_service
from app.services.exportacao import buscar_dados_historico


async def historico_json(usuario_id: str, dias: int) -> dict:
    """
    Mesmos dados que alimentam o PDF de exportação (buscar_dados_historico,
    reaproveitado de exportacao.py), só que em JSON — a classificação clínica
    (cor/seta por faixa) fica a cargo do front-end, que já recebe
    meta/limite_baixo/limite_alto pra calcular igual.
    """
    dados = await buscar_dados_historico(usuario_id, dias)
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


async def perfil_json(usuario_id: str) -> dict | None:
    """Mesmo dado que _perfil()/_basal() mostram em texto no WhatsApp (comandos.py), estruturado pro site."""
    dados = await perfil_service.buscar_perfil_completo(usuario_id)
    if dados is None:
        return None

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


async def relatorio_json(usuario_id: str, periodo: str) -> dict:
    """Mesmos dados do resumo periódico mandado automaticamente no WhatsApp (relatorios.py), em JSON."""
    dados = await relatorios.buscar_dados_relatorio(usuario_id, periodo)
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


async def hba1c_json(usuario_id: str, dias: int) -> dict:
    """Mesma estimativa de GMI/HbA1c do comando *hba1c* no WhatsApp (hba1c.py)."""
    estimativa = await hba1c.gerar_estimativa(usuario_id, dias)
    if estimativa is None:
        return {"disponivel": False, "minimo_medicoes": hba1c.MINIMO_MEDICOES, "dias": dias}
    return {"disponivel": True, **estimativa}


async def padroes_json(usuario_id: str, dias: int) -> dict:
    """Mesma detecção de padrões do comando *padroes* no WhatsApp (padroes.py)."""
    lista = await padroes.detectar_padroes(usuario_id, dias)
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
