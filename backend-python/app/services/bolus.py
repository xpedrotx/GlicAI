"""Cálculo de dose de bolus (relação IC + fator de sensibilidade + modificadores)."""
import math
from datetime import datetime, time, timedelta, timezone

from app.services.supabase_client import supabase


def encontrar_relacao_ic_atual(relacoes: list[dict], hora_atual: time) -> dict | None:
    """
    Acha a relação insulina:carboidrato cujo intervalo [hora_inicio, hora_fim]
    cobre o horário atual. Se nenhuma cobrir, cai pro período 'livre' (se existir).
    OBS: não trata intervalos que cruzam a meia-noite (ex: 22:00-02:00) — para
    esse caso o paciente deve cadastrar um período 'livre' como fallback.
    """
    for relacao in relacoes:
        inicio = _para_time(relacao["hora_inicio"])
        fim = _para_time(relacao["hora_fim"])
        if inicio <= hora_atual <= fim:
            return relacao

    for relacao in relacoes:
        if relacao["periodo"] == "livre":
            return relacao

    return None


def _para_time(valor) -> time:
    if isinstance(valor, time):
        return valor
    return time.fromisoformat(valor)


def _iob_de_uma_dose(dose: float, horas_passadas: float, duracao_horas: float) -> float:
    """Decaimento linear: a dose perde efeito uniformemente ao longo de duracao_horas."""
    if duracao_horas <= 0 or horas_passadas < 0 or horas_passadas >= duracao_horas:
        return 0.0
    return dose * (1 - horas_passadas / duracao_horas)


async def calcular_insulina_ativa(usuario_id: str, duracao_horas: float | None) -> float:
    """
    Soma a insulina ainda ativa no corpo (IOB), com decaimento linear ao
    longo de duracao_horas. Só conta doses confirmadas (dose_aplicada
    preenchida). O decaimento conta a partir de `horario_aplicacao` (quando
    o paciente de fato aplicou), não de `horario` (quando o bot calculou) —
    podem ser bem diferentes se o paciente demora pra aplicar.
    """
    if not duracao_horas or duracao_horas <= 0:
        return 0.0

    agora = datetime.now(timezone.utc)

    registros = (
        supabase.table("registros_bolus").select("*").eq("usuario_id", usuario_id).execute().data
    )

    total = 0.0
    for r in registros:
        if r["dose_aplicada"] is None:
            continue
        momento = r.get("horario_aplicacao") or r["horario"]
        horario_aplicacao = datetime.fromisoformat(momento)
        horas_passadas = (agora - horario_aplicacao).total_seconds() / 3600
        total += _iob_de_uma_dose(float(r["dose_aplicada"]), horas_passadas, duracao_horas)

    return total


def calcular_dose(
    meta_glicemia: float,
    limite_baixo: float,
    fator_sensibilidade: float,
    gramas_por_unidade: float,
    carboidratos_g: float,
    glicemia_atual: float,
    modificadores: list[dict],
    insulina_ativa: float = 0.0,
) -> dict:
    """
    Lógica pura de cálculo — não toca no banco, só recebe os dados já
    carregados. Isso permite testar a matemática sem depender do Supabase.

    modificadores: lista de {"id", "nome", "tipo_ajuste": "percentual"|"fixo", "valor_ajuste"}
    insulina_ativa: unidades de insulina de doses recentes que ainda devem
    estar agindo no corpo (IOB) — abate do total (carboidrato + correção),
    não só da correção, pra não empilhar dose em cima do que já está ativo.

    Abaixo do limite_baixo (hipoglicemia), bloqueia o cálculo — o manual de
    diabetes é explícito: não aplicar insulina em hipoglicemia, só tratar
    com carboidrato de ação rápida e medir de novo em 15 minutos.
    """
    if glicemia_atual < limite_baixo:
        return {
            "hipo": True,
            "dose_final": None,
            "modificadores_aplicados": [],
            "explicacao": (
                f"⚠️ Sua glicemia está em {glicemia_atual:.0f} mg/dL, abaixo do seu "
                f"limite de hipoglicemia ({limite_baixo} mg/dL). Não aplique insulina agora — "
                "trate com carboidrato de ação rápida e meça de novo em 15 minutos."
            ),
        }

    dose_carboidrato = carboidratos_g / gramas_por_unidade if gramas_por_unidade else 0.0
    dose_correcao = max(0.0, (glicemia_atual - meta_glicemia) / fator_sensibilidade)
    subtotal_bruto = dose_carboidrato + dose_correcao
    subtotal = max(0.0, subtotal_bruto - insulina_ativa)

    percentuais = [m for m in modificadores if m["tipo_ajuste"] == "percentual"]
    fixos = [m for m in modificadores if m["tipo_ajuste"] == "fixo"]

    ajuste_percentual_total = sum(m["valor_ajuste"] for m in percentuais)
    ajuste_fixo_total = sum(m["valor_ajuste"] for m in fixos)

    apos_percentual = subtotal * (1 + ajuste_percentual_total / 100)
    dose_exata = apos_percentual + ajuste_fixo_total
    # Sempre arredonda pra baixo, pro número inteiro mais próximo — dose de
    # insulina não deve ser aplicada com casa decimal nem arredondada pra cima.
    dose_final = float(max(0, math.floor(dose_exata)))

    linhas = []
    if carboidratos_g > 0:
        linhas.append(f"Carboidrato: {carboidratos_g}g ÷ {gramas_por_unidade}g/U = {dose_carboidrato:.1f}U")
    linhas.append(f"Correção: ({glicemia_atual} - {meta_glicemia}) ÷ {fator_sensibilidade} = {dose_correcao:.1f}U")
    if carboidratos_g > 0:
        linhas.append(f"Subtotal bruto: {subtotal_bruto:.1f}U")
    if insulina_ativa > 0:
        linhas.append(f"Insulina ativa (ainda agindo): -{insulina_ativa:.1f}U")
        linhas.append(f"Subtotal: {subtotal:.1f}U")
    for m in modificadores:
        sinal = "+" if m["valor_ajuste"] >= 0 else ""
        unidade = "%" if m["tipo_ajuste"] == "percentual" else "U"
        linhas.append(f"Modificador '{m['nome']}': {sinal}{m['valor_ajuste']}{unidade}")
    linhas.append(f"*Dose final: {dose_final:.0f}U*")

    return {
        "hipo": False,
        "dose_carboidrato": round(dose_carboidrato, 1),
        "dose_correcao": round(dose_correcao, 1),
        "subtotal": round(subtotal, 1),
        "ajuste_percentual_total": ajuste_percentual_total,
        "ajuste_fixo_total": ajuste_fixo_total,
        "dose_final": dose_final,
        "dose_exata": round(dose_exata, 2),
        "modificadores_aplicados": [m["id"] for m in modificadores],
        "explicacao": "\n".join(linhas),
    }


async def calcular_e_registrar_bolus(
    usuario_id: str, carboidratos_g: float, glicemia_atual: float, agora: datetime
) -> dict:
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data
    if not perfis:
        return {"erro": "Ainda não achei seu perfil glicêmico completo — termina o cadastro antes de calcular o bolus."}
    perfil = perfis[0]

    relacoes = supabase.table("relacao_ic").select("*").eq("usuario_id", usuario_id).execute().data
    relacao = encontrar_relacao_ic_atual(relacoes, agora.time())
    if relacao is None:
        return {
            "erro": (
                "Não achei uma relação insulina:carboidrato pra esse horário. "
                "Cadastra um período *livre* pra cobrir os horários que faltam."
            )
        }

    modificadores = (
        supabase.table("modificadores_bolus")
        .select("*")
        .eq("usuario_id", usuario_id)
        .eq("ativo", True)
        .execute()
        .data
    )

    insulina_ativa = await calcular_insulina_ativa(usuario_id, perfil.get("tempo_insulina_ativa_horas"))

    resultado = calcular_dose(
        meta_glicemia=perfil["meta_glicemia"],
        limite_baixo=perfil["limite_baixo"],
        fator_sensibilidade=perfil["fator_sensibilidade"],
        gramas_por_unidade=float(relacao["gramas_por_unidade"]),
        carboidratos_g=carboidratos_g,
        glicemia_atual=glicemia_atual,
        modificadores=modificadores,
        insulina_ativa=insulina_ativa,
    )

    if resultado["hipo"]:
        return resultado

    return await _persistir_registro(usuario_id, carboidratos_g, glicemia_atual, resultado)


async def calcular_correcao(usuario_id: str, glicemia_atual: float) -> dict | None:
    """
    Sugestão de dose de correção quando o paciente manda só a glicemia (sem
    carboidratos), sem depender de relação insulina:carboidrato. Qualquer
    valor acima da meta já gera sugestão (não só acima do limite crítico) —
    doses pequenas demais são descartadas pelo arredondamento em
    calcular_dose. Retorna None se não estiver acima da meta ou o perfil
    estiver incompleto. Se a dose der zero, ainda retorna o resultado (com a
    explicação), só não persiste em registros_bolus.
    """
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data
    if not perfis:
        return None
    perfil = perfis[0]

    if glicemia_atual <= perfil["meta_glicemia"]:
        return None

    modificadores = (
        supabase.table("modificadores_bolus")
        .select("*")
        .eq("usuario_id", usuario_id)
        .eq("ativo", True)
        .execute()
        .data
    )

    insulina_ativa = await calcular_insulina_ativa(usuario_id, perfil.get("tempo_insulina_ativa_horas"))

    resultado = calcular_dose(
        meta_glicemia=perfil["meta_glicemia"],
        limite_baixo=perfil["limite_baixo"],
        fator_sensibilidade=perfil["fator_sensibilidade"],
        gramas_por_unidade=1,
        carboidratos_g=0,
        glicemia_atual=glicemia_atual,
        modificadores=modificadores,
        insulina_ativa=insulina_ativa,
    )

    if resultado["dose_final"] <= 0:
        resultado["registro_id"] = None
        return resultado

    return await _persistir_registro(usuario_id, 0, glicemia_atual, resultado)


async def _persistir_registro(usuario_id: str, carboidratos_g: float, glicemia_atual: float, resultado: dict) -> dict:
    registro = (
        supabase.table("registros_bolus")
        .insert(
            {
                "usuario_id": usuario_id,
                "carboidratos_g": int(carboidratos_g),
                "glicemia_referencia": int(glicemia_atual),
                "dose_calculada": resultado["dose_final"],
            }
        )
        .execute()
        .data[0]
    )

    if resultado["modificadores_aplicados"]:
        supabase.table("registros_bolus_modificadores").insert(
            [
                {"registro_bolus_id": registro["id"], "modificador_id": mid}
                for mid in resultado["modificadores_aplicados"]
            ]
        ).execute()

    resultado["registro_id"] = registro["id"]
    return resultado


JANELA_APLIQUEI_MINUTOS = 60


async def registrar_dose_aplicada(
    usuario_id: str, dose_aplicada: float, horario_aplicacao: datetime | None = None
) -> dict:
    """
    Registra que o paciente aplicou `dose_aplicada` unidades de insulina.

    `horario_aplicacao` vem preenchido só em registro retroativo (ex:
    "apliquei 6u 12:20") — o IOB passa a decair a partir daquele horário, não
    de agora. Se houver um bolus/correção calculado pelo bot nos últimos
    JANELA_APLIQUEI_MINUTOS minutos e ainda sem dose confirmada, anexa a essa
    dose (e cancela o escalonamento pros cuidadores, se pendente). Senão,
    cria um registro novo — "apliquei" funciona mesmo sem cálculo prévio.

    Corrige um bug real: antes sempre pegava o último registro do usuário
    (idade/estado ignorados) e sobrescrevia — um "apliquei" avulso podia
    "confirmar" um cálculo de horas atrás e fazer o IOB parecer zerado com a
    dose real recém aplicada.
    """
    momento = horario_aplicacao or datetime.now(timezone.utc)
    limite = (momento - timedelta(minutes=JANELA_APLIQUEI_MINUTOS)).isoformat()

    pendentes = (
        supabase.table("registros_bolus")
        .select("*")
        .eq("usuario_id", usuario_id)
        .is_("dose_aplicada", "null")
        .gte("horario", limite)
        .lte("horario", momento.isoformat())
        .order("horario", desc=True)
        .limit(1)
        .execute()
        .data
    )

    if pendentes:
        alvo = pendentes[0]
        supabase.table("registros_bolus").update(
            {"dose_aplicada": dose_aplicada, "horario_aplicacao": momento.isoformat()}
        ).eq("id", alvo["id"]).execute()
        alvo["dose_aplicada"] = dose_aplicada
        alvo["horario_aplicacao"] = momento.isoformat()
        return alvo

    return (
        supabase.table("registros_bolus")
        .insert(
            {
                "usuario_id": usuario_id,
                "carboidratos_g": 0,
                "glicemia_referencia": None,
                "dose_calculada": dose_aplicada,
                "dose_aplicada": dose_aplicada,
                "horario": momento.isoformat(),
                "horario_aplicacao": momento.isoformat(),
            }
        )
        .execute()
        .data[0]
    )
