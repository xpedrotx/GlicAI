"""
Autenticação do site de acompanhamento (CPF + senha).

Não existe CPF nem senha coletados hoje — o cadastro via WhatsApp só pede
telefone/nome. O paciente cria a senha no próprio site, provando posse da
conta com um código de 6 dígitos — mas o código é *gerado pelo comando
`criar senha` no próprio WhatsApp* (ver comandos.py), não solicitado a
partir de um telefone digitado no site.

Isso é proposital, não só estilo: `usuarios.telefone` guarda o JID que o
WhatsApp deu pra conversa, e esse JID às vezes é `@lid` (um ID interno,
sem NENHUMA relação com o número de telefone real — ver o mesmo problema
resolvido em cuidadores.py) em vez de `@c.us` (que ao menos começa com o
número). Não tem como o paciente digitar um "telefone" no site e a gente
casar isso de forma confiável — só o próprio WhatsApp sabe endereçar a
conversa certa, então é ele quem tem que iniciar.

O mesmo fluxo serve pra "esqueci minha senha": qualquer confirmação de
código válida sobrescreve a senha atual, não tem comando/tela separado.

Sessão é um token aleatório opaco (não JWT stateless) guardado com hash em
sessoes_web — dá pra revogar no logout sem precisar de lista de revogação
separada, e é consistente com o padrão já usado no projeto pra
códigos/convites (tabela com expiração + uso único).
"""
import hashlib
import random
import secrets
import string
from datetime import datetime, timedelta, timezone

import bcrypt

from app.services.supabase_client import supabase
from app.utils import validar_cpf

MINUTOS_VALIDADE_CODIGO = 10
DIAS_VALIDADE_SESSAO = 30
SENHA_MINIMO_CARACTERES = 8

# Rate limiting contra força bruta no código de 6 dígitos e na senha —
# bloqueia por IP depois de MAX_TENTATIVAS falhas em JANELA_BLOQUEIO_MINUTOS.
# 6 dígitos = 1 milhão de combinações; sem isso, dá pra varrer via automação
# dentro da janela de validade do próprio código (10 min).
JANELA_BLOQUEIO_MINUTOS = 15
MAX_TENTATIVAS = 5


class ErroAutenticacao(Exception):
    """Erro esperado (código/CPF/senha inválidos) — a mensagem já é a que o usuário deve ver."""


_MENSAGEM_BLOQUEIO = "Muitas tentativas. Aguarde alguns minutos antes de tentar de novo."


def _bloqueado(identificador: str, tipo: str) -> bool:
    limite = (datetime.now(timezone.utc) - timedelta(minutes=JANELA_BLOQUEIO_MINUTOS)).isoformat()
    tentativas = (
        supabase.table("tentativas_auth")
        .select("id")
        .eq("identificador", identificador)
        .eq("tipo", tipo)
        .gte("criado_em", limite)
        .execute()
        .data
    )
    return len(tentativas) >= MAX_TENTATIVAS


def _registrar_falha(identificador: str, tipo: str) -> None:
    supabase.table("tentativas_auth").insert({"identificador": identificador, "tipo": tipo}).execute()


def _verificar_rate_limit(identificador: str, tipo: str) -> None:
    if _bloqueado(identificador, tipo):
        raise ErroAutenticacao(_MENSAGEM_BLOQUEIO)


def gerar_codigo_login(usuario_id: str) -> str:
    """
    Cria um código de 6 dígitos pra esse usuário e devolve o texto pronto
    pra mandar como resposta do comando `criar senha` — quem entrega a
    mensagem é o roteador de comandos normal (comandos.py), não essa
    função, já que ele sabe endereçar a conversa certa (seja @c.us ou
    @lid) sem precisar saber o número de telefone real.
    """
    codigo = "".join(random.choices(string.digits, k=6))
    expira_em = (datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_VALIDADE_CODIGO)).isoformat()
    supabase.table("codigos_login_web").insert(
        {"usuario_id": usuario_id, "codigo": codigo, "expira_em": expira_em}
    ).execute()

    return (
        f"🔑 *Código de acesso ao site*\n\n{codigo}\n\n"
        f"Vale por {MINUTOS_VALIDADE_CODIGO} minutos. Digita ele em "
        "*glicia.pedrotx.com.br/criar-senha* pra criar sua senha."
    )


async def confirmar_codigo(codigo: str, cpf: str, senha: str, ip: str) -> str:
    """
    Confirma o código, valida CPF e senha, hasheia a senha e cria a sessão.
    O código sozinho já identifica o usuário (não precisa de telefone) —
    quem só souber um código alheio ainda precisaria adivinhar o CPF certo
    também, mas o código é a prova real de posse da conta.
    Retorna o token de sessão em texto puro (só o hash fica no banco).

    "ip" é só pra rate limiting (ver _verificar_rate_limit) — nunca guardado
    junto do código/CPF, só na tabela de tentativas falhas.
    """
    _verificar_rate_limit(ip, "confirmar_codigo")
    try:
        return await _confirmar_codigo_interno(codigo, cpf, senha)
    except ErroAutenticacao:
        _registrar_falha(ip, "confirmar_codigo")
        raise


async def _confirmar_codigo_interno(codigo: str, cpf: str, senha: str) -> str:
    agora = datetime.now(timezone.utc).isoformat()
    pendentes = (
        supabase.table("codigos_login_web")
        .select("*")
        .eq("codigo", codigo)
        .is_("usado_em", "null")
        .gte("expira_em", agora)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not pendentes:
        raise ErroAutenticacao("Código inválido ou expirado.")
    usuario_id = pendentes[0]["usuario_id"]

    if not validar_cpf(cpf):
        raise ErroAutenticacao("CPF inválido.")
    cpf_digitos = "".join(c for c in cpf if c.isdigit())

    if len(senha) < SENHA_MINIMO_CARACTERES:
        raise ErroAutenticacao(f"A senha precisa ter pelo menos {SENHA_MINIMO_CARACTERES} caracteres.")

    outro_dono = (
        supabase.table("usuarios")
        .select("id")
        .eq("cpf", cpf_digitos)
        .neq("id", usuario_id)
        .limit(1)
        .execute()
        .data
    )
    if outro_dono:
        raise ErroAutenticacao("Esse CPF já está associado a outra conta.")

    senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
    supabase.table("usuarios").update({"cpf": cpf_digitos, "senha_hash": senha_hash}).eq(
        "id", usuario_id
    ).execute()
    supabase.table("codigos_login_web").update({"usado_em": agora}).eq("id", pendentes[0]["id"]).execute()

    return await criar_sessao(usuario_id)


async def login(cpf: str, senha: str, ip: str) -> str:
    """
    Erro sempre com a mesma mensagem genérica ("CPF ou senha inválidos"),
    tanto pra CPF não encontrado quanto pra senha errada — não dá pra dar
    dica de qual dos dois estava errado (evita enumeração de CPFs válidos).

    "ip" é só pra rate limiting (ver _verificar_rate_limit).
    """
    _verificar_rate_limit(ip, "login")
    cpf_digitos = "".join(c for c in cpf if c.isdigit())
    resultado = supabase.table("usuarios").select("*").eq("cpf", cpf_digitos).limit(1).execute().data
    if not resultado:
        _registrar_falha(ip, "login")
        raise ErroAutenticacao("CPF ou senha inválidos.")
    usuario = resultado[0]
    senha_hash = usuario.get("senha_hash")
    if not senha_hash or not bcrypt.checkpw(senha.encode(), senha_hash.encode()):
        _registrar_falha(ip, "login")
        raise ErroAutenticacao("CPF ou senha inválidos.")
    return await criar_sessao(usuario["id"])


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def criar_sessao(usuario_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expira_em = (datetime.now(timezone.utc) + timedelta(days=DIAS_VALIDADE_SESSAO)).isoformat()
    supabase.table("sessoes_web").insert(
        {"usuario_id": usuario_id, "token_hash": _hash_token(token), "expira_em": expira_em}
    ).execute()
    return token


async def validar_sessao(token: str | None) -> dict | None:
    if not token:
        return None
    agora = datetime.now(timezone.utc).isoformat()
    sessoes = (
        supabase.table("sessoes_web")
        .select("*")
        .eq("token_hash", _hash_token(token))
        .gte("expira_em", agora)
        .limit(1)
        .execute()
        .data
    )
    if not sessoes:
        return None
    usuarios = supabase.table("usuarios").select("*").eq("id", sessoes[0]["usuario_id"]).execute().data
    return usuarios[0] if usuarios else None


async def logout(token: str) -> None:
    supabase.table("sessoes_web").delete().eq("token_hash", _hash_token(token)).execute()
