"""Estimativa de GMI/HbA1c a partir do histórico de glicemia — aproximada, não substitui exame de sangue."""
from datetime import datetime, timedelta, timezone

from app.services.supabase_client import supabase

DIAS_PADRAO = 90
MINIMO_MEDICOES = 5


def calcular_gmi(media_glicemia: float) -> float:
    """
    GMI (Glucose Management Indicator) — fórmula padrão de Bergenstal et al.
    2018, a mesma usada por CGMs como Dexcom/FreeStyle Libre pra estimar a
    HbA1c a partir da glicemia média.
    """
    return 3.31 + 0.02392 * media_glicemia


async def gerar_estimativa(usuario_id: str, dias: int = DIAS_PADRAO) -> dict | None:
    """Retorna None se não houver medições suficientes no período pra uma estimativa minimamente confiável."""
    data_inicio = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()

    glicemias = (
        supabase.table("registros_glicemia")
        .select("valor")
        .eq("usuario_id", usuario_id)
        .gte("horario", data_inicio)
        .execute()
        .data
    )

    if len(glicemias) < MINIMO_MEDICOES:
        return None

    valores = [g["valor"] for g in glicemias]
    media = sum(valores) / len(valores)

    return {
        "media_glicemia": media,
        "gmi": calcular_gmi(media),
        "num_medicoes": len(valores),
        "dias": dias,
    }


def formatar_estimativa(estimativa: dict) -> str:
    return (
        "🩺 *Estimativa de HbA1c/GMI*\n\n"
        f"Baseado em *{estimativa['num_medicoes']} medições* dos últimos {estimativa['dias']} dias:\n"
        f"• Glicemia média: *{estimativa['media_glicemia']:.0f} mg/dL*\n"
        f"• GMI estimado: *{estimativa['gmi']:.1f}%*\n\n"
        "⚠️ Isso é uma estimativa aproximada baseada nas suas medições manuais "
        "(não num sensor contínuo) e não substitui o exame de sangue de HbA1c. "
        "Use como referência pra conversar com seu médico."
    )
