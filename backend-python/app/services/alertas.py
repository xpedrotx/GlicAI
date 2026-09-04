"""Alertas de hipo/hiperglicemia, disparados no momento em que uma glicemia é registrada."""
from datetime import datetime, timedelta, timezone

from app.services.supabase_client import supabase

JANELA_THROTTLE_MINUTOS = 15


def _classificar(valor: float, limite_baixo: int, limite_alto: int) -> str | None:
    if valor < limite_baixo:
        return "hipoglicemia"
    if valor > limite_alto:
        return "hiperglicemia"
    return None


def _alerta_recente(usuario_id: str, tipo: str) -> bool:
    limite = (datetime.now(timezone.utc) - timedelta(minutes=JANELA_THROTTLE_MINUTOS)).isoformat()
    recentes = (
        supabase.table("alertas_enviados")
        .select("id")
        .eq("usuario_id", usuario_id)
        .eq("tipo", tipo)
        .gte("horario_envio", limite)
        .limit(1)
        .execute()
        .data
    )
    return bool(recentes)


async def checar_alerta_glicemia(usuario: dict, valor: float) -> dict | None:
    """
    Compara a glicemia registrada com os limites do perfil. Retorna None se
    o valor está dentro da faixa. Se estiver fora, retorna sempre
    {"tipo": "hipoglicemia"|"hiperglicemia", "novo": bool, "limite": int} —
    "tipo" permite ao chamador (comandos._glicemia) acionar a sugestão de
    correção e o ciclo de confirmação mesmo quando "novo" vem False porque o
    aviso já foi mandado há menos de 15 min (throttle, ver _alerta_recente):
    nesse caso o chamador ainda recalcula a dose a cada leitura, só não
    repete o cartão completo de alerta + dicas de novo. "limite" é o limite
    baixo (hipo) ou alto (hiper) que foi ultrapassado, pro chamador montar a
    mensagem sem precisar buscar o perfil de novo.
    """
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario["id"]).execute().data
    if not perfis:
        return None
    perfil = perfis[0]

    tipo = _classificar(valor, perfil["limite_baixo"], perfil["limite_alto"])
    if tipo is None:
        return None

    limite = perfil["limite_baixo"] if tipo == "hipoglicemia" else perfil["limite_alto"]

    if _alerta_recente(usuario["id"], tipo):
        return {"tipo": tipo, "novo": False, "limite": limite}

    supabase.table("alertas_enviados").insert(
        {"usuario_id": usuario["id"], "tipo": tipo, "valor_glicemia": int(valor)}
    ).execute()

    return {"tipo": tipo, "novo": True, "limite": limite}
