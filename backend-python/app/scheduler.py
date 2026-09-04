"""Scheduler de lembretes (medir glicemia / aplicar basal / aplicar bolus)."""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services import remedicao
from app.services.confirmacoes import verificar_pendentes
from app.services.monitoramento import verificar_uso_banco
from app.services.relatorios import verificar_relatorios_periodicos
from app.services.supabase_client import supabase
from app.services.whatsapp_sender import enviar_mensagem
from app.utils import agora_usuario, dia_semana_supabase

logger = logging.getLogger("glicia.scheduler")

scheduler = AsyncIOScheduler()

# Se o paciente já fez a ação por conta própria pouco antes do horário
# agendado (ex: mediu a glicemia às 16:45, lembrete cadastrado pras 17:00),
# não faz sentido lembrar de novo — só pula o envio.
JANELA_JA_FEITO_MINUTOS = 60

# Tipos de lembrete pros quais dá pra checar automaticamente se a ação já
# foi feita (tem uma tabela pra consultar). "aplicar_basal" e "outro" não
# têm um comando de confirmação equivalente ainda, então sempre mandam.
_TABELA_POR_TIPO = {
    "medir_glicemia": ("registros_glicemia", "horario"),
    "aplicar_bolus": ("registros_bolus", "horario_aplicacao"),
}


async def _acao_ja_feita_recentemente(usuario_id: str, tipo: str, agora_utc: datetime) -> bool:
    """
    True se o paciente já registrou a ação correspondente (glicemia medida,
    dose de bolus aplicada) nos últimos JANELA_JA_FEITO_MINUTOS minutos —
    nesse caso o lembrete das dessa checagem é pulado, pra não incomodar
    com algo que já foi feito.
    """
    info = _TABELA_POR_TIPO.get(tipo)
    if info is None:
        return False
    tabela, coluna_horario = info

    limite = (agora_utc - timedelta(minutes=JANELA_JA_FEITO_MINUTOS)).isoformat()
    recentes = (
        supabase.table(tabela)
        .select("id")
        .eq("usuario_id", usuario_id)
        .gte(coluna_horario, limite)
        .limit(1)
        .execute()
        .data
    )
    return bool(recentes)


def _texto_lembrete(lembrete: dict) -> str:
    if lembrete["tipo"] == "medir_glicemia":
        return "⏰ Hora de medir sua glicemia! Me manda o valor, tipo *glicemia 110*."
    if lembrete["tipo"] == "aplicar_basal":
        return "⏰ Hora da sua insulina basal."
    if lembrete["tipo"] == "aplicar_bolus":
        return "⏰ Lembrete pra aplicar o bolus."
    return "⏰ Lembrete."


async def _checar_lembretes() -> None:
    """
    Roda a cada minuto: para cada lembrete ativo, calcula "agora" no timezone
    do respectivo usuário e compara com o horário cadastrado. Não guarda jobs
    individuais por lembrete — mais simples de manter em sincronia com o que
    o paciente cadastra/edita via WhatsApp, ao custo de rodar uma checagem
    por minuto (tranquilo pro volume de um protótipo).
    """
    lembretes = supabase.table("lembretes").select("*").eq("ativo", True).execute().data
    if not lembretes:
        return

    usuario_ids = list({l["usuario_id"] for l in lembretes})
    usuarios = supabase.table("usuarios").select("*").in_("id", usuario_ids).execute().data
    usuarios_por_id = {u["id"]: u for u in usuarios}

    for lembrete in lembretes:
        usuario = usuarios_por_id.get(lembrete["usuario_id"])
        if not usuario or usuario.get("status_cadastro") != "completo":
            continue

        agora = agora_usuario(usuario.get("timezone") or "America/Sao_Paulo")
        horario_lembrete = str(lembrete["horario"])[:5]
        horario_atual = agora.strftime("%H:%M")

        if horario_lembrete != horario_atual:
            continue
        if dia_semana_supabase(agora) not in lembrete["dias_semana"]:
            continue

        try:
            if await _acao_ja_feita_recentemente(usuario["id"], lembrete["tipo"], agora.astimezone(timezone.utc)):
                continue
            await enviar_mensagem(usuario["telefone"], _texto_lembrete(lembrete))
        except Exception:
            logger.exception("Falha ao enviar lembrete %s para o usuário %s", lembrete["id"], usuario["id"])


def iniciar_scheduler() -> AsyncIOScheduler:
    scheduler.add_job(_checar_lembretes, CronTrigger(second=0), id="checar_lembretes", replace_existing=True)
    scheduler.add_job(verificar_pendentes, CronTrigger(second=15), id="verificar_confirmacoes", replace_existing=True)
    scheduler.add_job(
        remedicao.verificar_pendentes, CronTrigger(second=45), id="verificar_remedicao", replace_existing=True
    )
    scheduler.add_job(
        verificar_relatorios_periodicos, CronTrigger(minute="*/10"), id="verificar_relatorios", replace_existing=True
    )
    scheduler.add_job(
        verificar_uso_banco, CronTrigger(hour=6, minute=0), id="verificar_uso_banco", replace_existing=True
    )
    scheduler.start()
    return scheduler
