"""
Detecção de padrão na glicemia por dia da semana x período do dia.

Ex: "toda terça de manhã sua glicemia costuma vir alta" — útil pro paciente
levar pro médico e ajustar basal/relação insulina:carboidrato nesses horários.

Limitação conhecida: exige só um mínimo de medições no bucket (não
necessariamente em semanas diferentes), então com pouco histórico um padrão
"detectado" pode ser coincidência. Fica mais confiável quanto mais dados.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.services.supabase_client import supabase

DIAS_PADRAO = 60
MINIMO_MEDICOES_POR_BUCKET = 3
MAXIMO_PADROES_REPORTADOS = 3

DIAS_SEMANA_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def _periodo_do_dia(hora: int) -> str:
    if 0 <= hora < 6:
        return "de madrugada"
    if 6 <= hora < 12:
        return "de manhã"
    if 12 <= hora < 18:
        return "à tarde"
    return "à noite"


async def detectar_padroes(usuario_id: str, dias: int = DIAS_PADRAO) -> list[dict]:
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data
    if not perfis:
        return []
    perfil = perfis[0]

    data_inicio = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    glicemias = (
        supabase.table("registros_glicemia")
        .select("valor, horario")
        .eq("usuario_id", usuario_id)
        .gte("horario", data_inicio)
        .execute()
        .data
    )

    buckets = defaultdict(list)
    for g in glicemias:
        dt = datetime.fromisoformat(g["horario"])
        chave = (dt.weekday(), _periodo_do_dia(dt.hour))
        buckets[chave].append(g["valor"])

    padroes = []
    for (dia_semana, periodo), valores in buckets.items():
        if len(valores) < MINIMO_MEDICOES_POR_BUCKET:
            continue
        media = sum(valores) / len(valores)
        if media > perfil["limite_alto"]:
            padroes.append(
                {"dia_semana": dia_semana, "periodo": periodo, "media": media, "tipo": "alta", "n": len(valores)}
            )
        elif media < perfil["limite_baixo"]:
            padroes.append(
                {"dia_semana": dia_semana, "periodo": periodo, "media": media, "tipo": "baixa", "n": len(valores)}
            )

    padroes.sort(key=lambda p: abs(p["media"] - perfil["meta_glicemia"]), reverse=True)
    return padroes[:MAXIMO_PADROES_REPORTADOS]


def formatar_padroes(padroes: list[dict], dias: int) -> str:
    if not padroes:
        return (
            f"🔍 Não encontrei nenhum padrão claro nos últimos {dias} dias — ou "
            "ainda faltam medições suficientes pra detectar algo com confiança."
        )

    linhas = [f"🔍 *Padrões detectados* (últimos {dias} dias)\n"]
    for p in padroes:
        dia_label = DIAS_SEMANA_PT[p["dia_semana"]]
        emoji = "🟠" if p["tipo"] == "alta" else "🔴"
        direcao = "vem alta" if p["tipo"] == "alta" else "vem baixa"
        linhas.append(
            f"{emoji} Toda {dia_label} {p['periodo']}, sua glicemia costuma {direcao} "
            f"(média *{p['media']:.0f} mg/dL* em {p['n']} medições)"
        )
    linhas.append("\nVale comentar isso com seu médico pra ajustar basal/relação IC nesses horários.")
    return "\n".join(linhas)
