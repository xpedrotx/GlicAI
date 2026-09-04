"""Helpers compartilhados entre cadastro, comandos, bolus e scheduler."""
import re
import unicodedata
from datetime import datetime, time
from zoneinfo import ZoneInfo

_NUMERO_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
_HORA_RE = re.compile(r"^(\d{1,2})[:h]?(\d{2})?$")


def parse_numero(texto: str) -> float | None:
    """
    Extrai o primeiro número de um texto, aceitando vírgula ou ponto como
    separador decimal e tolerando unidades coladas (ex: "120mg/dl", "40g",
    "-20%"). Retorna None se não achar nenhum número.
    """
    if texto is None:
        return None
    match = _NUMERO_RE.search(texto)
    if match is None:
        return None
    try:
        return float(match.group().replace(",", "."))
    except ValueError:
        return None


def parse_hora(texto: str) -> time | None:
    """
    Converte texto tipo "18:00", "18h00", "18h" ou "1800" em datetime.time.
    Retorna None se não conseguir interpretar.
    """
    if texto is None:
        return None
    texto = texto.strip().lower().replace("hs", "").replace(" ", "")
    match = _HORA_RE.match(texto)
    if match is None:
        return None
    hora = int(match.group(1))
    minuto = int(match.group(2)) if match.group(2) else 0
    try:
        return time(hour=hora, minute=minuto)
    except ValueError:
        return None


def remover_acentos(texto: str) -> str:
    """Tira acentos pra comparação mais tolerante (ex: 'não' casa com 'nao')."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def dia_semana_supabase(data: datetime) -> int:
    """
    Converte a convenção do Python (Monday=0 .. Sunday=6) para a convenção
    usada no schema (0=domingo .. 6=sábado).
    """
    return (data.weekday() + 1) % 7


def agora_usuario(timezone_str: str) -> datetime:
    """Retorna o horário atual no timezone do usuário (ex: 'America/Sao_Paulo')."""
    return datetime.now(ZoneInfo(timezone_str))


def formatar_hora_local(horario_iso: str, timezone_str: str) -> str:
    """
    Converte um horário salvo em ISO (sempre UTC no banco) pro fuso do
    usuário e formata só HH:MM — usado nas confirmações de *apliquei*/
    *tratei*, onde mostrar a hora certa (não a UTC) importa pro paciente e
    pros cuidadores conferirem quando a dose foi de fato aplicada.
    """
    return datetime.fromisoformat(horario_iso).astimezone(ZoneInfo(timezone_str)).strftime("%H:%M")


def validar_cpf(cpf: str) -> bool:
    """
    Valida CPF pelo algoritmo padrão de dígito verificador. Aceita com ou
    sem pontuação (tira tudo que não for dígito antes de validar). Rejeita
    sequências óbvias tipo "111.111.111-11" (passam no cálculo do dígito
    verificador, mas nunca são CPFs reais).
    """
    digitos = re.sub(r"\D", "", cpf or "")
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False

    def _digito_verificador(parcial: str) -> str:
        peso = len(parcial) + 1
        soma = sum(int(d) * (peso - i) for i, d in enumerate(parcial))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    d1 = _digito_verificador(digitos[:9])
    d2 = _digito_verificador(digitos[:9] + d1)
    return digitos[-2:] == d1 + d2
