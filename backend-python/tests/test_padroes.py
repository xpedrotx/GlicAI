import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.services import padroes
from app.services.padroes import _periodo_do_dia, detectar_padroes, formatar_padroes
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def test_periodo_do_dia():
    assert _periodo_do_dia(3) == "de madrugada"
    assert _periodo_do_dia(8) == "de manhã"
    assert _periodo_do_dia(14) == "à tarde"
    assert _periodo_do_dia(20) == "à noite"


def _horario_na_proxima(dia_semana_alvo: int, hora: int) -> datetime:
    """Um datetime (UTC) dentro dos últimos 60 dias que cai no dia da semana e hora pedidos."""
    base = datetime.now(timezone.utc) - timedelta(days=30)
    while base.weekday() != dia_semana_alvo:
        base -= timedelta(days=1)
    return base.replace(hour=hora, minute=0, second=0, microsecond=0)


def test_detectar_padrao_de_glicemia_alta():
    fake = FakeSupabase()
    padroes.supabase = fake
    usuario_id = str(uuid.uuid4())

    fake.store["perfil_glicemico"] = [
        {"usuario_id": usuario_id, "meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180}
    ]

    # 3 terças de manhã com glicemia bem acima do limite alto
    terca = 1  # Python: segunda=0, terça=1
    fake.store["registros_glicemia"] = [
        {"usuario_id": usuario_id, "valor": v, "horario": _horario_na_proxima(terca, 8).isoformat()}
        for v in (220, 230, 210)
    ]
    # e um monte de leituras normais em outros dias, pra não confundir
    for i, v in enumerate([100, 110, 105, 115]):
        fake.store["registros_glicemia"].append(
            {"usuario_id": usuario_id, "valor": v, "horario": _horario_na_proxima((terca + 1) % 7, 8).isoformat()}
        )

    resultado = _executar(detectar_padroes(usuario_id, 60))

    assert len(resultado) >= 1
    padrao_terca = next(p for p in resultado if p["dia_semana"] == terca)
    assert padrao_terca["tipo"] == "alta"
    assert padrao_terca["n"] == 3


def test_detectar_padrao_ignora_bucket_com_poucas_medicoes():
    fake = FakeSupabase()
    padroes.supabase = fake
    usuario_id = str(uuid.uuid4())

    fake.store["perfil_glicemico"] = [
        {"usuario_id": usuario_id, "meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180}
    ]
    # só 2 medições altas -> abaixo do mínimo de 3, não deve virar "padrão"
    fake.store["registros_glicemia"] = [
        {"usuario_id": usuario_id, "valor": v, "horario": _horario_na_proxima(1, 8).isoformat()}
        for v in (220, 230)
    ]

    resultado = _executar(detectar_padroes(usuario_id, 60))
    assert resultado == []


def test_detectar_padrao_sem_perfil_retorna_vazio():
    fake = FakeSupabase()
    padroes.supabase = fake

    assert _executar(detectar_padroes(str(uuid.uuid4()), 60)) == []


def test_formatar_padroes_sem_nenhum():
    texto = formatar_padroes([], 60)
    assert "Não encontrei nenhum padrão" in texto


def test_formatar_padroes_com_resultado():
    texto = formatar_padroes(
        [{"dia_semana": 1, "periodo": "de manhã", "media": 220.0, "tipo": "alta", "n": 3}], 60
    )
    assert "terça-feira" in texto
    assert "de manhã" in texto
    assert "vem alta" in texto
    assert "220" in texto
