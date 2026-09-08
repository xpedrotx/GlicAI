"""
Lembrete automático de remedição — depois de uma glicemia fora da faixa,
medir de novo depois de um tempo pra ver a tendência (subindo/descendo)
antes de decidir qualquer outra coisa. Diferente de confirmacoes.py (que
escala pros cuidadores se o paciente não confirmar tratamento/aplicação):
aqui é só um lembrete pro próprio paciente, sem depender de confirmação.

Dois intervalos, cada um com a própria justificativa clínica:
- Hipoglicemia: 15 minutos — "regra dos 15" (ADA), padrão já estabelecido
  pra reavaliar depois de tratar com carboidrato de ação rápida.
- Hiperglicemia: 60 minutos — insulina rápida começa a agir em ~15min e
  atinge o pico em 1-2h; 1 hora já mostra uma tendência real sem repetir
  a correção cedo demais (risco de "stacking" — aplicar de novo antes da
  dose anterior terminar de agir).
"""
import logging
from datetime import datetime, timedelta, timezone

from app.services.supabase_client import supabase
from app.services.whatsapp_sender import enviar_mensagem

logger = logging.getLogger("glicia.remedicao")

MINUTOS_HIPOGLICEMIA = 15
MINUTOS_HIPERGLICEMIA = 60

_MINUTOS_POR_TIPO = {
    "hipoglicemia": MINUTOS_HIPOGLICEMIA,
    "hiperglicemia": MINUTOS_HIPERGLICEMIA,
}

_MENSAGENS_POR_TIPO = {
    "hipoglicemia": (
        "⏰ *Hora de medir de novo*\n\n"
        f"Já se passaram {MINUTOS_HIPOGLICEMIA} minutos desde a hipoglicemia — meça sua "
        "glicemia de novo pra ver se já estabilizou. Manda *glicemia <valor>*."
    ),
    "hiperglicemia": (
        "⏰ *Hora de medir de novo*\n\n"
        "Já se passou 1 hora desde a glicemia alta — meça de novo pra ver se já está "
        "baixando. Manda *glicemia <valor>*."
    ),
}


async def agendar(usuario_id: str, tipo: str) -> None:
    """Nunca levanta exceção — isso é chamado no meio do fluxo de resposta a
    uma glicemia fora da faixa (ver comandos.py), e uma falha aqui (ex:
    tabela ainda não migrada) não pode derrubar o aviso crítico que o
    paciente precisa ver. Sem o lembrete agendado, o pior caso é só não
    receber o "meça de novo" — o aviso principal continua saindo normal.

    "tipo": "hipoglicemia" ou "hiperglicemia" — define tanto o intervalo
    quanto o texto do lembrete (ver _MINUTOS_POR_TIPO / _MENSAGENS_POR_TIPO).
    """
    try:
        minutos = _MINUTOS_POR_TIPO[tipo]
        disparar_em = datetime.now(timezone.utc) + timedelta(minutes=minutos)
        supabase.table("lembretes_remedicao").insert(
            {"usuario_id": usuario_id, "disparar_em": disparar_em.isoformat(), "enviado": False, "tipo": tipo}
        ).execute()
    except Exception:
        logger.exception("Falha ao agendar lembrete de remedição (%s) pro usuário %s", tipo, usuario_id)


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
                # Linhas criadas antes da migration do campo "tipo" não têm
                # esse valor — só existiam pra hipoglicemia até então.
                tipo = l.get("tipo") or "hipoglicemia"
                await enviar_mensagem(usuario["telefone"], _MENSAGENS_POR_TIPO[tipo])
            supabase.table("lembretes_remedicao").update({"enviado": True}).eq("id", l["id"]).execute()
        except Exception:
            logger.exception("Falha ao mandar lembrete de remedição %s", l["id"])
