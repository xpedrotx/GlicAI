"""
Cuidadores (esposa, mãe etc) que acompanham a glicemia do paciente.

Um número de telefone só vira cuidador mandando "vincular <código> <nome>"
pro bot — não dá pra simplesmente cadastrar o número diretamente porque o
WhatsApp às vezes só endereça um contato via @lid (não @c.us a partir do
número puro), e isso só se descobre a partir de uma mensagem real vinda
daquele número (ver whatsapp_sender.py / routes/webhook.py).
"""
import logging
import random
import string
from datetime import datetime, timedelta, timezone

from app.services.supabase_client import supabase
from app.services.whatsapp_sender import enviar_mensagem
from app.utils import remover_acentos

logger = logging.getLogger("glicia.cuidadores")

MINUTOS_VALIDADE_CONVITE = 30

# Rate limiting contra força bruta no código de convite (6 dígitos) — mesmo
# raciocínio do login web (ver auth_web.py): sem isso, dá pra varrer o
# espaço de códigos por automação dentro da janela de validade.
JANELA_BLOQUEIO_MINUTOS = 15
MAX_TENTATIVAS = 5


def _bloqueado(telefone: str) -> bool:
    """Nunca levanta exceção — se a checagem falhar (ex: tabela ainda não
    migrada), assume que NÃO está bloqueado (ver mesmo raciocínio em
    auth_web.py: rate limiting não pode derrubar o fluxo principal)."""
    try:
        limite = (datetime.now(timezone.utc) - timedelta(minutes=JANELA_BLOQUEIO_MINUTOS)).isoformat()
        tentativas = (
            supabase.table("tentativas_auth")
            .select("id")
            .eq("identificador", telefone)
            .eq("tipo", "vincular")
            .gte("criado_em", limite)
            .execute()
            .data
        )
        return len(tentativas) >= MAX_TENTATIVAS
    except Exception:
        logger.exception("Falha ao checar rate limit de vínculo — seguindo sem bloquear")
        return False


def _registrar_falha(telefone: str) -> None:
    try:
        supabase.table("tentativas_auth").insert({"identificador": telefone, "tipo": "vincular"}).execute()
    except Exception:
        logger.exception("Falha ao registrar tentativa de vínculo")


async def tentar_vincular(telefone: str, mensagem: str) -> str | None:
    """
    Só reage a mensagens "vincular <codigo> <nome>". Retorna None se a
    mensagem não é isso (deixa o webhook seguir o fluxo normal de paciente).
    """
    partes = mensagem.strip().split()
    if not partes or remover_acentos(partes[0].lower()) != "vincular":
        return None

    if len(partes) < 3:
        return "Pra vincular, manda assim: *vincular <código> <seu nome>*"

    if _bloqueado(telefone):
        return "Muitas tentativas com código inválido. Aguarde alguns minutos e peça um código novo."

    codigo = partes[1]
    nome = " ".join(partes[2:])

    agora = datetime.now(timezone.utc).isoformat()
    convites = (
        supabase.table("convites_cuidador")
        .select("*")
        .eq("codigo", codigo)
        .is_("usado_em", "null")
        .gte("expira_em", agora)
        .execute()
        .data
    )
    if not convites:
        _registrar_falha(telefone)
        return "Esse código não é válido ou já expirou. Peça um novo código pra quem te convidou."

    convite = convites[0]
    usuario_id = convite["usuario_id"]

    supabase.table("cuidadores").insert(
        {"usuario_id": usuario_id, "nome": nome, "telefone": telefone}
    ).execute()
    supabase.table("convites_cuidador").update({"usado_em": agora}).eq("id", convite["id"]).execute()

    # Se esse número mandou qualquer coisa pro bot antes do "vincular" (ex:
    # "oi"), pode ter sobrado um cadastro de paciente incompleto e abandonado
    # pra esse mesmo telefone. Remove pra não confundir esse número (agora
    # cuidador) com um paciente em mensagens futuras.
    supabase.table("usuarios").delete().eq("telefone", telefone).execute()

    pacientes = supabase.table("usuarios").select("nome").eq("id", usuario_id).execute().data
    nome_paciente = pacientes[0]["nome"] if pacientes else "seu familiar"

    return (
        f"✅ Prontinho, {nome}! Você agora recebe avisos sobre a glicemia de "
        f"*{nome_paciente}* por aqui. 💙"
    )


async def eh_cuidador(telefone: str) -> bool:
    resultado = (
        supabase.table("cuidadores")
        .select("id")
        .eq("telefone", telefone)
        .eq("ativo", True)
        .limit(1)
        .execute()
        .data
    )
    return bool(resultado)


async def criar_convite(usuario_id: str) -> dict:
    """
    Gera e persiste um novo código de convite — usado tanto pelo comando
    `cuidador convidar` no WhatsApp (gerar_convite, abaixo) quanto pelo
    endpoint do dashboard web (site de acompanhamento), que mostra o código
    numa tela em vez de um texto de chat pronto.
    """
    codigo = "".join(random.choices(string.digits, k=6))
    expira_em = (datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_VALIDADE_CONVITE)).isoformat()

    supabase.table("convites_cuidador").insert(
        {"usuario_id": usuario_id, "codigo": codigo, "expira_em": expira_em}
    ).execute()

    return {"codigo": codigo, "expira_em": expira_em, "minutos_validade": MINUTOS_VALIDADE_CONVITE}


async def gerar_convite(usuario_id: str) -> str:
    convite = await criar_convite(usuario_id)
    codigo = convite["codigo"]
    return (
        f"🔑 Código de convite: *{codigo}*\n\n"
        "Manda esse código pra quem você quer que acompanhe sua glicemia. "
        f"Ela(e) deve mandar pra mim: *vincular {codigo} <o nome dela(e)>*\n\n"
        f"⏳ Vale por {MINUTOS_VALIDADE_CONVITE} minutos."
    )


async def buscar_cuidadores(usuario_id: str) -> list[dict]:
    return (
        supabase.table("cuidadores")
        .select("*")
        .eq("usuario_id", usuario_id)
        .eq("ativo", True)
        .execute()
        .data
    )


async def listar_cuidadores(usuario_id: str) -> str:
    lista = await buscar_cuidadores(usuario_id)
    if not lista:
        return "👨‍👩‍👧 Você ainda não tem ninguém acompanhando sua glicemia. Manda *cuidador convidar* pra adicionar alguém."

    linhas = ["👨‍👩‍👧 *Quem acompanha você*", ""]
    for c in lista:
        linhas.append(f"• {c['nome']}")
    return "\n".join(linhas)


async def desativar_cuidador(usuario_id: str, nome: str) -> dict | None:
    """Desativa o cuidador com esse nome (comparação sem diferenciar
    maiúsculas/minúsculas). Retorna a linha desativada, ou None se não
    achou ninguém com esse nome — quem chama decide como comunicar isso
    (texto de chat no WhatsApp, 404 na API web)."""
    lista = await buscar_cuidadores(usuario_id)
    alvo = next((c for c in lista if c["nome"].lower() == nome.lower()), None)
    if alvo is None:
        return None

    supabase.table("cuidadores").update({"ativo": False}).eq("id", alvo["id"]).execute()
    return alvo


async def remover_cuidador(usuario_id: str, nome: str) -> str:
    alvo = await desativar_cuidador(usuario_id, nome)
    if alvo is None:
        return f'Não achei "{nome}" na sua lista.'
    return f"✅ Beleza, *{alvo['nome']}* não vai receber mais avisos."


async def notificar_cuidadores(usuario_id: str, texto: str) -> None:
    cuidadores = (
        supabase.table("cuidadores")
        .select("*")
        .eq("usuario_id", usuario_id)
        .eq("ativo", True)
        .execute()
        .data
    )
    for c in cuidadores:
        try:
            await enviar_mensagem(c["telefone"], texto)
        except Exception:
            logger.exception("Falha ao notificar cuidador %s", c["id"])
