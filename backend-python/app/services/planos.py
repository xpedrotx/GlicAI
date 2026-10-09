"""
Planos do GlicAI.

- trial: 7 dias grátis a partir do cadastro, com tudo liberado.
- free: depois do teste, sem assinatura — 1 medição de glicemia por dia e sem
  lembretes (os agendados e os de "meça de novo" depois de um alerta).
- pro: assinatura ativa no Stripe (R$ 9,90/mês) ou conta de cortesia.

Regra de segurança: o limite do Free nunca impede o bot de reagir a uma
glicemia fora dos limites do paciente (hipo/hiper) nem a emergências — esses
valores são sempre registrados e geram os avisos de sempre, inclusive pros
cuidadores. O limite vale só pra medições de rotina, dentro da faixa.
"""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings
from app.services.supabase_client import supabase

PRECO_TEXTO = "R$ 9,90/mês"
DIAS_TESTE = 7
MEDICOES_POR_DIA_FREE = 1

# past_due fica como Pro: o Stripe ainda está tentando cobrar de novo, e
# cortar o acesso de quem é paciente por uma falha de cartão passageira seria
# pior do que dar uns dias de folga. Se as tentativas esgotam, vira canceled.
_STATUS_COM_ACESSO = {"active", "trialing", "past_due"}


def site_url() -> str:
    return settings.site_url.rstrip("/")


def link_assinatura() -> str:
    return f"{site_url()}/dashboard/assinatura"


def _data(valor) -> datetime | None:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))


def plano_efetivo(usuario: dict, agora: datetime | None = None) -> str:
    """'pro', 'trial' ou 'free'."""
    if usuario.get("plano_cortesia") or usuario.get("assinatura_status") in _STATUS_COM_ACESSO:
        return "pro"

    fim_teste = _data(usuario.get("teste_termina_em"))
    # Sem data de fim de teste (linha antiga, migration ainda não rodou): na
    # dúvida, não corta o acesso de ninguém.
    if fim_teste is None or (agora or datetime.now(timezone.utc)) < fim_teste:
        return "trial"
    return "free"


def tem_acesso_completo(usuario: dict) -> bool:
    return plano_efetivo(usuario) in ("trial", "pro")


def resumo(usuario: dict) -> dict:
    agora = datetime.now(timezone.utc)
    plano = plano_efetivo(usuario, agora)
    fim_teste = _data(usuario.get("teste_termina_em"))

    dias_restantes = None
    if plano == "trial" and fim_teste is not None:
        dias_restantes = max(1, -(-int((fim_teste - agora).total_seconds()) // 86400))

    renova_em = _data(usuario.get("assinatura_renova_em"))
    return {
        "plano": plano,
        "cortesia": bool(usuario.get("plano_cortesia")),
        "teste_termina_em": fim_teste.isoformat() if fim_teste else None,
        "dias_restantes_teste": dias_restantes,
        "assinatura_status": usuario.get("assinatura_status"),
        "renova_em": renova_em.isoformat() if renova_em else None,
        "cancela_no_fim": bool(usuario.get("assinatura_cancela_no_fim")),
        "tem_cliente_stripe": bool(usuario.get("stripe_customer_id")),
        "preco": PRECO_TEXTO,
        "medicoes_por_dia_free": MEDICOES_POR_DIA_FREE,
    }


def _inicio_do_dia_utc(usuario: dict) -> datetime:
    tz = ZoneInfo(usuario.get("timezone") or "America/Sao_Paulo")
    hoje = datetime.now(tz).date()
    return datetime.combine(hoje, time.min, tzinfo=tz).astimezone(timezone.utc)


def _medicoes_hoje(usuario: dict) -> int:
    registros = (
        supabase.table("registros_glicemia")
        .select("id")
        .eq("usuario_id", usuario["id"])
        .gte("horario", _inicio_do_dia_utc(usuario).isoformat())
        .execute()
        .data
    )
    return len(registros)


def _fora_da_faixa(usuario_id: str, valor: float) -> bool:
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data
    if not perfis:
        return False
    return valor < perfis[0]["limite_baixo"] or valor > perfis[0]["limite_alto"]


def mensagem_limite_glicemia(usuario: dict, valor: float) -> str | None:
    """
    Texto pra responder no lugar de registrar, se o plano Free já usou a
    medição do dia — ou None se pode registrar normalmente.
    """
    if tem_acesso_completo(usuario):
        return None
    if _fora_da_faixa(usuario["id"], valor):
        return None
    if _medicoes_hoje(usuario) < MEDICOES_POR_DIA_FREE:
        return None

    return (
        "🔒 No plano gratuito dá pra registrar *1 medição por dia*, e a de hoje já foi.\n\n"
        f"Com o *GlicAI Pro* ({PRECO_TEXTO}) você registra quantas quiser e ainda recebe lembretes: "
        f"{link_assinatura()}\n\n"
        "_Se a glicemia estiver fora da faixa, é só mandar que eu registro e te ajudo do mesmo jeito._"
    )


def mensagem_so_pro(recurso: str) -> str:
    return (
        f"🔒 {recurso} é um recurso do *GlicAI Pro* ({PRECO_TEXTO}).\n"
        f"Assine em {link_assinatura()} e libere tudo."
    )


def mensagem_plano(usuario: dict) -> str:
    info = resumo(usuario)
    plano = info["plano"]
    if plano == "pro":
        if info["cortesia"]:
            return "⭐ Você está no *GlicAI Pro* (cortesia). Tudo liberado!"
        extra = ""
        if info["renova_em"]:
            data = _data(info["renova_em"]).astimezone(ZoneInfo(usuario.get("timezone") or "America/Sao_Paulo"))
            extra = (
                f"\nAcesso até {data:%d/%m/%Y}." if info["cancela_no_fim"] else f"\nRenova em {data:%d/%m/%Y}."
            )
        return f"⭐ Você está no *GlicAI Pro*. Tudo liberado!{extra}\nGerenciar assinatura: {link_assinatura()}"
    if plano == "trial":
        dias = info["dias_restantes_teste"]
        quando = "termina hoje" if dias == 1 else f"termina em {dias} dias"
        return (
            f"🎁 Seu teste grátis {quando}. Por enquanto, tudo liberado!\n"
            f"Pra continuar sem limites depois, assine o *GlicAI Pro* ({PRECO_TEXTO}): {link_assinatura()}"
        )
    return (
        "Você está no *plano gratuito*: 1 medição por dia e sem lembretes.\n"
        f"Assine o *GlicAI Pro* ({PRECO_TEXTO}) pra liberar tudo: {link_assinatura()}"
    )


async def avisar_fim_do_teste() -> None:
    """
    Roda no scheduler (1x por hora): quem acabou de passar pro plano Free
    recebe uma única mensagem explicando o que mudou e como assinar.
    """
    from app.services.whatsapp_sender import enviar_mensagem  # evita import circular

    agora = datetime.now(timezone.utc)
    candidatos = (
        supabase.table("usuarios")
        .select("*")
        .lte("teste_termina_em", agora.isoformat())
        .is_("aviso_fim_teste_em", "null")
        .eq("status_cadastro", "completo")
        .execute()
        .data
    )
    for usuario in candidatos:
        # Só avisa até 3 dias depois do fim: evita mandar "seu teste acabou"
        # de repente pra uma conta antiga quando esta rotina entra no ar.
        fim = _data(usuario["teste_termina_em"])
        if fim is None or agora - fim > timedelta(days=3):
            supabase.table("usuarios").update({"aviso_fim_teste_em": agora.isoformat()}).eq("id", usuario["id"]).execute()
            continue
        if plano_efetivo(usuario, agora) == "pro":
            continue
        try:
            await enviar_mensagem(
                usuario["telefone"],
                "⏳ Seu teste grátis de 7 dias terminou.\n\n"
                f"Você segue no *plano gratuito*: 1 medição por dia e sem lembretes. "
                f"Pra liberar tudo de novo, assine o *GlicAI Pro* ({PRECO_TEXTO}): {link_assinatura()}",
            )
            supabase.table("usuarios").update({"aviso_fim_teste_em": agora.isoformat()}).eq("id", usuario["id"]).execute()
        except Exception:
            import logging

            logging.getLogger("glicia.planos").exception("Falha ao avisar fim de teste do usuário %s", usuario["id"])
