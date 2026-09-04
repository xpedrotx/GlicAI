import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.services import relatorios
from app.services.relatorios import _formatar_relatorio, _pode_enviar, gerar_relatorio
from tests.fake_supabase import FakeSupabase

PERFIL = {"limite_baixo": 70, "limite_alto": 180}


def _executar(coro):
    return asyncio.run(coro)


def test_formatar_relatorio_sem_dados():
    inicio = datetime.now(timezone.utc) - timedelta(days=7)
    fim = datetime.now(timezone.utc)

    texto = _formatar_relatorio("semana", inicio, fim, PERFIL, [], [], 0)

    assert "Sem registros de glicemia" in texto
    assert "Nenhuma dose de insulina" in texto
    assert "Eventos críticos" not in texto


def test_formatar_relatorio_com_dados():
    inicio = datetime.now(timezone.utc) - timedelta(days=7)
    fim = datetime.now(timezone.utc)
    glicemias = [{"valor": v} for v in (100, 110, 90, 200, 60, 130)]  # 1 hiper (200), 1 hipo (60)
    doses = [4.0, 5.0, 3.5]

    texto = _formatar_relatorio("semana", inicio, fim, PERFIL, glicemias, doses, 2)

    assert "6 medições" in texto
    assert "Hipoglicemias: 1" in texto
    assert "Hiperglicemias: 1" in texto
    assert "3 doses aplicadas" in texto
    assert "12.5U" in texto  # total
    assert "Eventos críticos" in texto
    assert "2" in texto


def test_formatar_relatorio_calcula_percentual_na_faixa_corretamente():
    inicio = datetime.now(timezone.utc) - timedelta(days=7)
    fim = datetime.now(timezone.utc)
    # 3 de 4 na faixa (70-180) -> 75%
    glicemias = [{"valor": v} for v in (100, 150, 90, 250)]

    texto = _formatar_relatorio("semana", inicio, fim, PERFIL, glicemias, [], 0)

    assert "75%" in texto


def test_pode_enviar_sem_envio_anterior():
    assert _pode_enviar(None, datetime.now(timezone.utc), 6) is True


def test_pode_enviar_respeita_intervalo_minimo():
    agora = datetime.now(timezone.utc)
    enviado_ontem = (agora - timedelta(days=1)).isoformat()
    enviado_semana_passada = (agora - timedelta(days=8)).isoformat()

    assert _pode_enviar(enviado_ontem, agora, 6) is False
    assert _pode_enviar(enviado_semana_passada, agora, 6) is True


def test_gerar_relatorio_usa_dados_do_periodo():
    fake = FakeSupabase()
    relatorios.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    fake.store["perfil_glicemico"] = [{"usuario_id": usuario_id, "limite_baixo": 70, "limite_alto": 180}]
    fake.store["registros_glicemia"] = [
        {"usuario_id": usuario_id, "valor": 120, "horario": (agora - timedelta(days=2)).isoformat()},
        # fora da janela de 7 dias -> não deve contar
        {"usuario_id": usuario_id, "valor": 300, "horario": (agora - timedelta(days=20)).isoformat()},
    ]
    fake.store["registros_bolus"] = [
        {"usuario_id": usuario_id, "dose_aplicada": 5.0, "horario": (agora - timedelta(days=1)).isoformat()},
    ]

    texto = _executar(gerar_relatorio(usuario_id, "semana"))

    assert texto is not None
    assert "1 medições" in texto
    assert "1 doses aplicadas" in texto


def test_gerar_relatorio_sem_perfil_retorna_none():
    fake = FakeSupabase()
    relatorios.supabase = fake

    assert _executar(gerar_relatorio(str(uuid.uuid4()), "semana")) is None
