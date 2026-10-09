"""
Painel do médico.

O médico cria conta no site (nome, e-mail, CRM, senha) e ganha um código de
vinculação próprio (ex: DR-K7M2QX). O paciente digita esse código — no
WhatsApp (`medico DR-K7M2QX`) ou no painel dele — e a partir daí o médico
acompanha, somente leitura, as glicemias, doses e o perfil desse paciente.

Quem concede o acesso é sempre o paciente: o código sozinho só identifica o
médico e não dá acesso a nada. O paciente vê quem tem acesso e pode revogar a
qualquer momento; o médico nunca vê telefone nem CPF do paciente, só o nome.

O CRM é informado pelo próprio médico e não é verificado automaticamente — o
paciente vê nome e CRM antes de confirmar o vínculo, justamente pra poder
conferir que é o médico dele.
"""
import hashlib
import hmac
import html
import logging
import re
import secrets
import string
from datetime import datetime, timedelta, timezone

import bcrypt

from app.services import email_envio
from app.services.auth_web import (
    DIAS_VALIDADE_SESSAO,
    SENHA_MINIMO_CARACTERES,
    ErroAutenticacao,
    _hash_token,
    _registrar_falha,
    _verificar_rate_limit,
)
from app.services.supabase_client import supabase

logger = logging.getLogger("glicia.medicos")

_ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sem 0/O/1/I/L, que se confundem
_TAMANHO_CODIGO = 6
_REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}
DIAS_RESUMO = 14


class ErroMedico(Exception):
    """Erro esperado — a mensagem já é a que o usuário deve ver."""


# --------------------------------------------------------------------------
# Código de vinculação
# --------------------------------------------------------------------------

def _gerar_codigo() -> str:
    return "DR-" + "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(_TAMANHO_CODIGO))


def normalizar_codigo(texto: str) -> str | None:
    """'dr k7m2qx', 'DR-K7M2QX' e 'k7m2qx' viram 'DR-K7M2QX'; None se não parece um código."""
    limpo = re.sub(r"[\s\-_.]", "", (texto or "").upper())
    if limpo.startswith("DR"):
        limpo = limpo[2:]
    if len(limpo) != _TAMANHO_CODIGO or any(c not in _ALFABETO_CODIGO for c in limpo):
        return None
    return f"DR-{limpo}"


# --------------------------------------------------------------------------
# Conta do médico
# --------------------------------------------------------------------------

def _validar_cadastro(nome: str, email: str, crm: str, uf: str, senha: str) -> tuple[str, str, str, str]:
    nome = " ".join((nome or "").split())
    email = (email or "").strip().lower()
    crm = re.sub(r"\D", "", crm or "")
    uf = (uf or "").strip().upper()

    if len(nome) < 3:
        raise ErroAutenticacao("Informe seu nome completo.")
    if not _REGEX_EMAIL.match(email):
        raise ErroAutenticacao("E-mail inválido.")
    if not 4 <= len(crm) <= 8:
        raise ErroAutenticacao("Informe o número do CRM (só números).")
    if uf not in UFS:
        raise ErroAutenticacao("Escolha a UF do CRM.")
    if len(senha or "") < SENHA_MINIMO_CARACTERES:
        raise ErroAutenticacao(f"A senha precisa ter pelo menos {SENHA_MINIMO_CARACTERES} caracteres.")
    return nome, email, crm, uf


MINUTOS_VALIDADE_CODIGO_EMAIL = 15
MAX_ERROS_CODIGO_EMAIL = 5
MAX_REENVIOS = 3
SEGUNDOS_ENTRE_ENVIOS = 60


def _hash_codigo_email(codigo: str) -> str:
    return hashlib.sha256(codigo.encode()).hexdigest()


async def _enviar_codigo_por_email(nome: str, email: str, codigo: str) -> None:
    primeiro_nome = html.escape(nome.split()[0])
    texto = (
        f"Olá, {nome.split()[0]}!\n\n"
        f"Seu código de confirmação do GlicAI é: {codigo}\n\n"
        f"Ele vale por {MINUTOS_VALIDADE_CODIGO_EMAIL} minutos. Se você não pediu esse cadastro, é só ignorar este e-mail."
    )
    corpo = (
        f'<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;color:#1b3a4b">'
        f"<h2 style=\"margin:0 0 12px\">Confirme seu e-mail</h2>"
        f"<p>Olá, {primeiro_nome}! Use este código para concluir seu cadastro no GlicAI:</p>"
        f'<p style="font-size:34px;font-weight:bold;letter-spacing:8px;margin:20px 0">{codigo}</p>'
        f"<p>Ele vale por {MINUTOS_VALIDADE_CODIGO_EMAIL} minutos. Se você não pediu esse cadastro, é só ignorar este e-mail.</p>"
        f"</div>"
    )
    try:
        await email_envio.enviar(email, "Seu código de confirmação do GlicAI", texto, corpo)
    except email_envio.EmailIndisponivel as erro:
        raise ErroAutenticacao("Não consegui enviar o e-mail agora. Tente de novo em instantes.") from erro


async def iniciar_cadastro(nome: str, email: str, crm: str, uf: str, senha: str, ip: str) -> str:
    """
    1ª etapa: valida os dados e manda um código de 6 dígitos pro e-mail. A conta
    só é criada em confirmar_email() — assim ninguém cria conta com e-mail
    alheio. Devolve o e-mail já normalizado.
    """
    _verificar_rate_limit(ip, "cadastro_medico")
    nome, email, crm, uf = _validar_cadastro(nome, email, crm, uf, senha)

    if supabase.table("medicos").select("id").eq("email", email).limit(1).execute().data:
        raise ErroAutenticacao("Já existe uma conta com esse e-mail. Entre ou use outro e-mail.")

    codigo = "".join(secrets.choice(string.digits) for _ in range(6))
    agora = datetime.now(timezone.utc)
    pendente = {
        "nome": nome,
        "email": email,
        "crm": crm,
        "uf": uf,
        "senha_hash": bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode(),
        "codigo_hash": _hash_codigo_email(codigo),
        "expira_em": (agora + timedelta(minutes=MINUTOS_VALIDADE_CODIGO_EMAIL)).isoformat(),
        "tentativas": 0,
        "reenvios": 0,
        "ultimo_envio_em": agora.isoformat(),
    }

    # Manda o e-mail ANTES de gravar: se o envio falhar, não sobra cadastro pendente
    await _enviar_codigo_por_email(nome, email, codigo)

    # recomeçar o cadastro com o mesmo e-mail substitui o pendente anterior
    supabase.table("cadastros_medico_pendentes").delete().eq("email", email).execute()
    supabase.table("cadastros_medico_pendentes").insert(pendente).execute()

    # Conta todo cadastro iniciado (não só as falhas): sem isso, dava pra disparar e-mails em massa.
    _registrar_falha(ip, "cadastro_medico")
    return email


def _pendente(email: str) -> dict | None:
    achados = (
        supabase.table("cadastros_medico_pendentes").select("*").eq("email", (email or "").strip().lower()).limit(1).execute().data
    )
    return achados[0] if achados else None


async def reenviar_codigo(email: str) -> None:
    pendente = _pendente(email)
    if pendente is None:
        raise ErroAutenticacao("Não achei esse cadastro. Preencha os dados de novo.")
    if pendente["reenvios"] >= MAX_REENVIOS:
        raise ErroAutenticacao("Muitos reenvios. Preencha o cadastro de novo.")

    agora = datetime.now(timezone.utc)
    ultimo = datetime.fromisoformat(str(pendente["ultimo_envio_em"]).replace("Z", "+00:00"))
    if (agora - ultimo).total_seconds() < SEGUNDOS_ENTRE_ENVIOS:
        raise ErroAutenticacao("Aguarde um minuto para pedir outro código.")

    codigo = "".join(secrets.choice(string.digits) for _ in range(6))
    await _enviar_codigo_por_email(pendente["nome"], pendente["email"], codigo)
    supabase.table("cadastros_medico_pendentes").update(
        {
            "codigo_hash": _hash_codigo_email(codigo),
            "expira_em": (agora + timedelta(minutes=MINUTOS_VALIDADE_CODIGO_EMAIL)).isoformat(),
            "tentativas": 0,
            "reenvios": pendente["reenvios"] + 1,
            "ultimo_envio_em": agora.isoformat(),
        }
    ).eq("id", pendente["id"]).execute()


async def confirmar_email(email: str, codigo: str) -> str:
    """2ª etapa: com o código certo, cria a conta e devolve o token de sessão."""
    pendente = _pendente(email)
    if pendente is None:
        raise ErroAutenticacao("Código inválido ou expirado. Preencha o cadastro de novo.")

    agora = datetime.now(timezone.utc)
    expira_em = datetime.fromisoformat(str(pendente["expira_em"]).replace("Z", "+00:00"))
    if agora > expira_em:
        supabase.table("cadastros_medico_pendentes").delete().eq("id", pendente["id"]).execute()
        raise ErroAutenticacao("O código expirou. Preencha o cadastro de novo para receber outro.")

    digitado = re.sub(r"\D", "", codigo or "")
    if not hmac.compare_digest(_hash_codigo_email(digitado), pendente["codigo_hash"]):
        tentativas = pendente["tentativas"] + 1
        if tentativas >= MAX_ERROS_CODIGO_EMAIL:
            supabase.table("cadastros_medico_pendentes").delete().eq("id", pendente["id"]).execute()
            raise ErroAutenticacao("Muitos erros de código. Preencha o cadastro de novo.")
        supabase.table("cadastros_medico_pendentes").update({"tentativas": tentativas}).eq("id", pendente["id"]).execute()
        raise ErroAutenticacao(f"Código incorreto. Você tem mais {MAX_ERROS_CODIGO_EMAIL - tentativas} tentativa(s).")

    if supabase.table("medicos").select("id").eq("email", pendente["email"]).limit(1).execute().data:
        supabase.table("cadastros_medico_pendentes").delete().eq("id", pendente["id"]).execute()
        raise ErroAutenticacao("Já existe uma conta com esse e-mail. Entre com sua senha.")

    for _ in range(8):
        codigo_vinculo = _gerar_codigo()
        if not supabase.table("medicos").select("id").eq("codigo_vinculo", codigo_vinculo).limit(1).execute().data:
            break
    else:
        raise ErroAutenticacao("Não consegui gerar seu código agora. Tente de novo.")

    medico = (
        supabase.table("medicos")
        .insert(
            {
                "nome": pendente["nome"],
                "email": pendente["email"],
                "crm": pendente["crm"],
                "uf": pendente["uf"],
                "senha_hash": pendente["senha_hash"],
                "codigo_vinculo": codigo_vinculo,
            }
        )
        .execute()
        .data[0]
    )
    supabase.table("cadastros_medico_pendentes").delete().eq("id", pendente["id"]).execute()
    return await criar_sessao(medico["id"])


async def login(email: str, senha: str, ip: str) -> str:
    """Mesma mensagem genérica pra e-mail inexistente e senha errada (evita enumerar e-mails)."""
    _verificar_rate_limit(ip, "login_medico")
    achados = supabase.table("medicos").select("*").eq("email", (email or "").strip().lower()).limit(1).execute().data
    medico = achados[0] if achados else None
    if not medico or not bcrypt.checkpw((senha or "").encode(), medico["senha_hash"].encode()):
        _registrar_falha(ip, "login_medico")
        raise ErroAutenticacao("E-mail ou senha inválidos.")
    return await criar_sessao(medico["id"])


async def criar_sessao(medico_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expira_em = (datetime.now(timezone.utc) + timedelta(days=DIAS_VALIDADE_SESSAO)).isoformat()
    supabase.table("sessoes_medico").insert(
        {"medico_id": medico_id, "token_hash": _hash_token(token), "expira_em": expira_em}
    ).execute()
    return token


async def validar_sessao(token: str | None) -> dict | None:
    if not token:
        return None
    sessoes = (
        supabase.table("sessoes_medico")
        .select("*")
        .eq("token_hash", _hash_token(token))
        .gte("expira_em", datetime.now(timezone.utc).isoformat())
        .limit(1)
        .execute()
        .data
    )
    if not sessoes:
        return None
    medicos = supabase.table("medicos").select("*").eq("id", sessoes[0]["medico_id"]).execute().data
    return medicos[0] if medicos else None


async def logout(token: str) -> None:
    supabase.table("sessoes_medico").delete().eq("token_hash", _hash_token(token)).execute()


def dados_publicos(medico: dict) -> dict:
    """O que o próprio médico (e o paciente que vai vincular) pode ver — nunca o hash da senha."""
    return {
        "id": medico["id"],
        "nome": medico["nome"],
        "email": medico.get("email"),
        "crm": medico["crm"],
        "uf": medico["uf"],
        "codigo_vinculo": medico["codigo_vinculo"],
    }


# --------------------------------------------------------------------------
# Vínculo (lado do paciente)
# --------------------------------------------------------------------------

async def buscar_por_codigo(texto: str, quem: str) -> dict:
    """
    Acha o médico dono do código. "quem" (id do paciente) só serve de chave do
    rate limit: sem ele dava pra testar códigos em massa até acertar algum.
    """
    _verificar_rate_limit(quem, "vincular_medico")
    codigo = normalizar_codigo(texto)
    medico = None
    if codigo:
        achados = supabase.table("medicos").select("*").eq("codigo_vinculo", codigo).limit(1).execute().data
        medico = achados[0] if achados else None
    if medico is None:
        _registrar_falha(quem, "vincular_medico")
        raise ErroMedico("Não encontrei nenhum médico com esse código. Confira com ele(a) e tente de novo.")
    return medico


def descricao_medico(medico: dict) -> str:
    return f"Dr(a). {medico['nome']} (CRM {medico['crm']}/{medico['uf']})"


async def vincular(usuario_id: str, medico: dict) -> bool:
    """Concede o acesso. False se já estava vinculado e ativo."""
    existente = (
        supabase.table("medico_pacientes")
        .select("*")
        .eq("medico_id", medico["id"])
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
        .data
    )
    if existente:
        if existente[0]["ativo"]:
            return False
        supabase.table("medico_pacientes").update(
            {"ativo": True, "vinculado_em": datetime.now(timezone.utc).isoformat(), "desvinculado_em": None}
        ).eq("id", existente[0]["id"]).execute()
        return True

    supabase.table("medico_pacientes").insert(
        {
            "medico_id": medico["id"],
            "usuario_id": usuario_id,
            "ativo": True,
            "vinculado_em": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()
    return True


async def medicos_do_paciente(usuario_id: str) -> list[dict]:
    vinculos = (
        supabase.table("medico_pacientes").select("*").eq("usuario_id", usuario_id).eq("ativo", True).execute().data
    )
    if not vinculos:
        return []
    medicos = supabase.table("medicos").select("*").in_("id", [v["medico_id"] for v in vinculos]).execute().data
    por_id = {m["id"]: m for m in medicos}
    return [
        {
            "id": v["medico_id"],
            "nome": por_id[v["medico_id"]]["nome"],
            "crm": por_id[v["medico_id"]]["crm"],
            "uf": por_id[v["medico_id"]]["uf"],
            "vinculado_em": v["vinculado_em"],
        }
        for v in vinculos
        if v["medico_id"] in por_id
    ]


async def desvincular(medico_id: str, usuario_id: str) -> bool:
    """Revoga o acesso (vale tanto pro paciente revogando quanto pro médico saindo). False se não havia vínculo ativo."""
    existente = (
        supabase.table("medico_pacientes")
        .select("id")
        .eq("medico_id", medico_id)
        .eq("usuario_id", usuario_id)
        .eq("ativo", True)
        .limit(1)
        .execute()
        .data
    )
    if not existente:
        return False
    supabase.table("medico_pacientes").update(
        {"ativo": False, "desvinculado_em": datetime.now(timezone.utc).isoformat()}
    ).eq("id", existente[0]["id"]).execute()
    return True


# --------------------------------------------------------------------------
# Pacientes (lado do médico)
# --------------------------------------------------------------------------

def _vinculo_ativo(medico_id: str, paciente_id: str) -> dict | None:
    achados = (
        supabase.table("medico_pacientes")
        .select("*")
        .eq("medico_id", medico_id)
        .eq("usuario_id", paciente_id)
        .eq("ativo", True)
        .limit(1)
        .execute()
        .data
    )
    return achados[0] if achados else None


async def paciente_autorizado(medico_id: str, paciente_id: str) -> dict | None:
    """
    O paciente (linha de usuarios) se — e somente se — existe vínculo ATIVO
    com esse médico; senão None. É o único portão de acesso aos dados
    clínicos no painel do médico: toda rota que lê dado de paciente passa por aqui.
    """
    if _vinculo_ativo(medico_id, paciente_id) is None:
        return None
    achados = supabase.table("usuarios").select("*").eq("id", paciente_id).limit(1).execute().data
    return achados[0] if achados else None


async def resumo_do_paciente(medico_id: str, paciente_id: str) -> dict | None:
    vinculo = _vinculo_ativo(medico_id, paciente_id)
    usuario = await paciente_autorizado(medico_id, paciente_id)
    if vinculo is None or usuario is None:
        return None
    return _resumo_paciente(usuario, vinculo["vinculado_em"])


def _resumo_paciente(usuario: dict, vinculado_em: str) -> dict:
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario["id"]).execute().data
    perfil = perfis[0] if perfis else None

    desde = (datetime.now(timezone.utc) - timedelta(days=DIAS_RESUMO)).isoformat()
    leituras = (
        supabase.table("registros_glicemia")
        .select("valor,horario")
        .eq("usuario_id", usuario["id"])
        .gte("horario", desde)
        .order("horario")
        .execute()
        .data
    )
    valores = [l["valor"] for l in leituras]
    ultima = leituras[-1] if leituras else None

    resumo = {
        "id": usuario["id"],
        "nome": usuario.get("nome"),
        "vinculado_em": vinculado_em,
        "tem_perfil": perfil is not None,
        "ultima_glicemia": {"valor": ultima["valor"], "horario": ultima["horario"]} if ultima else None,
        "medicoes": len(valores),
        "media": round(sum(valores) / len(valores)) if valores else None,
        "na_faixa_pct": None,
        "hipoglicemias": 0,
        "hiperglicemias": 0,
        "ultima_fora_da_faixa": False,
        "limite_baixo": perfil["limite_baixo"] if perfil else None,
        "limite_alto": perfil["limite_alto"] if perfil else None,
    }
    if perfil and valores:
        baixo, alto = perfil["limite_baixo"], perfil["limite_alto"]
        resumo["na_faixa_pct"] = round(100 * sum(1 for v in valores if baixo <= v <= alto) / len(valores))
        resumo["hipoglicemias"] = sum(1 for v in valores if v < baixo)
        resumo["hiperglicemias"] = sum(1 for v in valores if v > alto)
        resumo["ultima_fora_da_faixa"] = not baixo <= ultima["valor"] <= alto
    return resumo


async def pacientes_do_medico(medico_id: str) -> list[dict]:
    vinculos = (
        supabase.table("medico_pacientes").select("*").eq("medico_id", medico_id).eq("ativo", True).execute().data
    )
    if not vinculos:
        return []
    usuarios = supabase.table("usuarios").select("*").in_("id", [v["usuario_id"] for v in vinculos]).execute().data
    por_id = {u["id"]: u for u in usuarios}
    resumos = [
        _resumo_paciente(por_id[v["usuario_id"]], v["vinculado_em"]) for v in vinculos if v["usuario_id"] in por_id
    ]
    return sorted(resumos, key=lambda r: (r["nome"] or "~").lower())
