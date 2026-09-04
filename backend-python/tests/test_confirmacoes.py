import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.services import confirmacoes
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def _minutos_atras(minutos: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutos)).isoformat()


def _preparar_usuario_e_pendencia(fake: FakeSupabase, minutos_atras: int, **overrides) -> tuple[dict, dict]:
    usuario = fake.table("usuarios").insert(
        {"telefone": "5545999999999@c.us", "nome": "Pedro", "status_cadastro": "completo"}
    ).execute().data[0]

    pendencia = {
        "usuario_id": usuario["id"],
        "tipo": "hiperglicemia",
        "valor_glicemia": 201,
        "dose_sugerida": 2.0,
        "horario": _minutos_atras(minutos_atras),
    }
    pendencia.update(overrides)
    linha = fake.table("confirmacoes_glicemia").insert(pendencia).execute().data[0]
    return usuario, linha


def test_criar_confirmacao_nao_duplica_pendencia():
    fake = FakeSupabase()
    confirmacoes.supabase = fake
    usuario_id = str(uuid.uuid4())

    primeira = _executar(confirmacoes.criar_confirmacao(usuario_id, "hiperglicemia", 250, dose_sugerida=3.0))
    segunda = _executar(confirmacoes.criar_confirmacao(usuario_id, "hiperglicemia", 260, dose_sugerida=3.5))

    assert primeira is not None
    assert segunda is None
    assert len(fake.store["confirmacoes_glicemia"]) == 1


def test_criar_confirmacao_tipos_diferentes_nao_colidem():
    fake = FakeSupabase()
    confirmacoes.supabase = fake
    usuario_id = str(uuid.uuid4())

    hiper = _executar(confirmacoes.criar_confirmacao(usuario_id, "hiperglicemia", 250, dose_sugerida=3.0))
    hipo = _executar(confirmacoes.criar_confirmacao(usuario_id, "hipoglicemia", 55))

    assert hiper is not None
    assert hipo is not None
    assert len(fake.store["confirmacoes_glicemia"]) == 2


def test_confirmar_por_registro_bolus_marca_confirmado_e_libera_nova_pendencia():
    fake = FakeSupabase()
    confirmacoes.supabase = fake
    usuario_id = str(uuid.uuid4())
    registro_bolus_id = str(uuid.uuid4())

    criada = _executar(
        confirmacoes.criar_confirmacao(
            usuario_id, "hiperglicemia", 250, dose_sugerida=3.0, registro_bolus_id=registro_bolus_id
        )
    )

    confirmada = _executar(confirmacoes.confirmar_por_registro_bolus(registro_bolus_id))
    assert confirmada["id"] == criada["id"]

    nova = _executar(confirmacoes.criar_confirmacao(usuario_id, "hiperglicemia", 270, dose_sugerida=4.0))
    assert nova is not None


def test_confirmar_por_registro_bolus_sem_pendencia_retorna_none():
    fake = FakeSupabase()
    confirmacoes.supabase = fake

    assert _executar(confirmacoes.confirmar_por_registro_bolus(str(uuid.uuid4()))) is None


def test_confirmar_hipoglicemia():
    fake = FakeSupabase()
    confirmacoes.supabase = fake
    usuario_id = str(uuid.uuid4())

    criada = _executar(confirmacoes.criar_confirmacao(usuario_id, "hipoglicemia", 55))

    confirmada = _executar(confirmacoes.confirmar_hipoglicemia(usuario_id))
    assert confirmada["id"] == criada["id"]

    assert _executar(confirmacoes.confirmar_hipoglicemia(usuario_id)) is None


# --------------------------------------------------------------------------
# verificar_pendentes: ciclo de 2 lembretes (5min, 10min) + escalonamento
# pros cuidadores aos 15min sem confirmação.
# --------------------------------------------------------------------------

def test_verificar_pendentes_manda_primeiro_lembrete_aos_5min():
    fake = FakeSupabase()
    confirmacoes.supabase = fake
    usuario, pendencia = _preparar_usuario_e_pendencia(fake, minutos_atras=6)

    with patch.object(confirmacoes, "enviar_mensagem", new=AsyncMock()) as mock_enviar, patch.object(
        confirmacoes.cuidadores, "notificar_cuidadores", new=AsyncMock()
    ) as mock_notificar:
        _executar(confirmacoes.verificar_pendentes())

    mock_enviar.assert_awaited_once()
    assert mock_enviar.await_args.args[0] == usuario["telefone"]
    mock_notificar.assert_not_awaited()

    linha = fake.table("confirmacoes_glicemia").select("*").eq("id", pendencia["id"]).execute().data[0]
    assert linha["lembrete_enviado"] is True
    assert linha["lembrete2_enviado"] is False
    assert linha["cuidadores_notificados"] is False


def test_verificar_pendentes_manda_segundo_lembrete_aos_10min_sem_repetir_o_primeiro():
    fake = FakeSupabase()
    confirmacoes.supabase = fake
    _usuario, pendencia = _preparar_usuario_e_pendencia(
        fake, minutos_atras=11, lembrete_enviado=True
    )

    with patch.object(confirmacoes, "enviar_mensagem", new=AsyncMock()) as mock_enviar, patch.object(
        confirmacoes.cuidadores, "notificar_cuidadores", new=AsyncMock()
    ) as mock_notificar:
        _executar(confirmacoes.verificar_pendentes())

    mock_enviar.assert_awaited_once()  # só o 2º lembrete, o 1º já tinha sido mandado
    texto = mock_enviar.await_args.args[1]
    assert "Segundo aviso" in texto
    mock_notificar.assert_not_awaited()

    linha = fake.table("confirmacoes_glicemia").select("*").eq("id", pendencia["id"]).execute().data[0]
    assert linha["lembrete2_enviado"] is True
    assert linha["cuidadores_notificados"] is False


def test_verificar_pendentes_escala_pros_cuidadores_aos_15min():
    fake = FakeSupabase()
    confirmacoes.supabase = fake
    _usuario, pendencia = _preparar_usuario_e_pendencia(
        fake, minutos_atras=16, lembrete_enviado=True, lembrete2_enviado=True
    )

    with patch.object(confirmacoes, "enviar_mensagem", new=AsyncMock()) as mock_enviar, patch.object(
        confirmacoes.cuidadores, "notificar_cuidadores", new=AsyncMock()
    ) as mock_notificar:
        _executar(confirmacoes.verificar_pendentes())

    mock_enviar.assert_not_awaited()  # já mandou os 2 lembretes antes, não repete
    mock_notificar.assert_awaited_once()
    texto = mock_notificar.await_args.args[1]
    assert "não aplicou a insulina recomendada" in texto
    assert "201" in texto

    linha = fake.table("confirmacoes_glicemia").select("*").eq("id", pendencia["id"]).execute().data[0]
    assert linha["cuidadores_notificados"] is True


def test_verificar_pendentes_escalonamento_hipoglicemia_menciona_nao_tratou():
    fake = FakeSupabase()
    confirmacoes.supabase = fake
    _usuario, _pendencia = _preparar_usuario_e_pendencia(
        fake,
        minutos_atras=16,
        lembrete_enviado=True,
        lembrete2_enviado=True,
        tipo="hipoglicemia",
        valor_glicemia=55,
        dose_sugerida=None,
    )

    with patch.object(confirmacoes, "enviar_mensagem", new=AsyncMock()), patch.object(
        confirmacoes.cuidadores, "notificar_cuidadores", new=AsyncMock()
    ) as mock_notificar:
        _executar(confirmacoes.verificar_pendentes())

    mock_notificar.assert_awaited_once()
    texto = mock_notificar.await_args.args[1]
    assert "não tratou a hipoglicemia" in texto


def test_verificar_pendentes_ignora_pendencia_ja_confirmada():
    fake = FakeSupabase()
    confirmacoes.supabase = fake
    _preparar_usuario_e_pendencia(
        fake, minutos_atras=20, confirmado_em=datetime.now(timezone.utc).isoformat()
    )

    with patch.object(confirmacoes, "enviar_mensagem", new=AsyncMock()) as mock_enviar, patch.object(
        confirmacoes.cuidadores, "notificar_cuidadores", new=AsyncMock()
    ) as mock_notificar:
        _executar(confirmacoes.verificar_pendentes())

    mock_enviar.assert_not_awaited()
    mock_notificar.assert_not_awaited()
