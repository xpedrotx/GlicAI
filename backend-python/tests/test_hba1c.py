import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.services import hba1c
from app.services.hba1c import calcular_gmi, formatar_estimativa, gerar_estimativa
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def test_calcular_gmi_formula_bergenstal():
    # 3.31 + 0.02392 * 154 ~= 7.0%, valor de referência comum na literatura
    assert round(calcular_gmi(154), 1) == 7.0


def test_gerar_estimativa_com_dados_suficientes():
    fake = FakeSupabase()
    hba1c.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    fake.store["registros_glicemia"] = [
        {"usuario_id": usuario_id, "valor": v, "horario": (agora - timedelta(days=i)).isoformat()}
        for i, v in enumerate([120, 130, 140, 150, 160, 170])
    ]

    estimativa = _executar(gerar_estimativa(usuario_id, 90))

    assert estimativa is not None
    assert estimativa["num_medicoes"] == 6
    assert estimativa["media_glicemia"] == 145.0
    assert round(estimativa["gmi"], 2) == round(calcular_gmi(145.0), 2)


def test_gerar_estimativa_com_poucos_dados_retorna_none():
    fake = FakeSupabase()
    hba1c.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    fake.store["registros_glicemia"] = [
        {"usuario_id": usuario_id, "valor": 120, "horario": agora.isoformat()},
    ]

    assert _executar(gerar_estimativa(usuario_id, 90)) is None


def test_formatar_estimativa_inclui_aviso():
    texto = formatar_estimativa({"media_glicemia": 150.0, "gmi": 6.9, "num_medicoes": 20, "dias": 90})
    assert "6.9%" in texto
    assert "não substitui o exame de sangue" in texto
