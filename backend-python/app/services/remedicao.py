"""
Lembrete automático de remedição — Regra dos 15: depois de tratar uma
hipoglicemia, medir a glicemia de novo em 15 minutos antes de decidir
qualquer outra coisa. Diferente de confirmacoes.py (que escala pros
cuidadores se o paciente não confirmar o tratamento): aqui é só um lembrete
pro próprio paciente, sem depender de confirmação nenhuma.
"""
import logging
from datetime import datetime, timedelta, timezone

from app.services.supabase_client import supabase
from app.services.whatsapp_sender import enviar_mensagem

logger = logging.getLogger("glicia.remedicao")

MINUTOS_REMEDICAO = 15


async def agendar(usuario_id: str) -> None:
    disparar_em = datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_REMEDICAO)
    supabase.table("lembretes_remedicao").insert(
        {"usuario_id": usuario_id, "disparar_em": disparar_em.isoformat(), "enviado": False}
    ).execute()


def _buscar_usuario(usuario_id: str) -> dict | None:
    resultado = supabase.table("usuarios").select("*").eq("id", usuario_id).execute().data
    return resultado[0] if resultado else None


async def verificar_pendentes() -> None:
    """Roda no scheduler: dispara os lembretes de remedição vencidos."""
    agora_iso = datetime.now(timezone.utc).isoformat()
    pendentes = (
        supabase.table("lembretes_remedicao")
        .select("*")
        .eq("enviado", False)
        .lte("disparar_em", agora_iso)
        .execute()
        .data
    )
    for l in pendentes:
        try:
            usuario = _buscar_usuario(l["usuario_id"])
            if usuario:
                await enviar_mensagem(
                    usuario["telefone"],
                    "⏰ *Hora de medir de novo*\n\n"
                    "Já se passaram 15 minutos desde a hipoglicemia — meça sua glicemia "
                    "de novo pra ver se já estabilizou. Manda *glicemia <valor>*.",
                )
            supabase.table("lembretes_remedicao").update({"enviado": True}).eq("id", l["id"]).execute()
        except Exception:
            logger.exception("Falha ao mandar lembrete de remedição %s", l["id"])
