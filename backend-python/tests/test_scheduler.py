import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from app import scheduler
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------
# _acao_ja_feita_recentemente: base da checagem de "já fez, não precisa
# lembrar" — pedido real do usuário depois de receber um lembrete de medir
# glicemia 15 minutos depois de já ter medido por conta própria.
# --------------------------------------------------------------------------

def test_ja_feita_recentemente_glicemia_registrada_na_janela():
    fake = FakeSupabase()
    scheduler.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    fake.table("registros_glicemia").insert(
        {"usuario_id": usuario_id, "valor": 110, "horario": (agora - timedelta(minutes=15)).isoformat()}
    ).execute()

    assert _executar(scheduler._acao_ja_feita_recentemente(usuario_id, "medir_glicemia", agora)) is True


def test_ja_feita_recentemente_glicemia_fora_da_janela_nao_conta():
    fake = FakeSupabase()
    scheduler.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    fake.table("registros_glicemia").insert(
        {"usuario_id": usuario_id, "valor": 110, "horario": (agora - timedelta(minutes=90)).isoformat()}
    ).execute()

    assert _executar(scheduler._acao_ja_feita_recentemente(usuario_id, "medir_glicemia", agora)) is False


def test_ja_feita_recentemente_sem_nenhum_registro():
    fake = FakeSupabase()
    scheduler.supabase = fake
    usuario_id = str(uuid.uuid4())

    resultado = _executar(
        scheduler._acao_ja_feita_recentemente(usuario_id, "medir_glicemia", datetime.now(timezone.utc))
    )
    assert resultado is False


def test_ja_feita_recentemente_bolus_usa_horario_aplicacao():
    fake = FakeSupabase()
    scheduler.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    # um cálculo de bolus feito há pouco, mas AINDA NÃO aplicado (sem
    # horario_aplicacao) não deve contar como "já feito"
    fake.table("registros_bolus").insert(
        {"usuario_id": usuario_id, "carboidratos_g": 40, "horario": (agora - timedelta(minutes=5)).isoformat()}
    ).execute()
    assert _executar(scheduler._acao_ja_feita_recentemente(usuario_id, "aplicar_bolus", agora)) is False

    # depois que aplica de fato (horario_aplicacao preenchido), passa a contar
    fake.table("registros_bolus").insert(
        {
            "usuario_id": usuario_id,
            "carboidratos_g": 0,
            "horario": (agora - timedelta(minutes=5)).isoformat(),
            "dose_aplicada": 4.0,
            "horario_aplicacao": (agora - timedelta(minutes=5)).isoformat(),
        }
    ).execute()
    assert _executar(scheduler._acao_ja_feita_recentemente(usuario_id, "aplicar_bolus", agora)) is True


def test_ja_feita_recentemente_basal_e_outro_sempre_false():
    """Não existe comando de confirmação equivalente pra basal/outro ainda
    — sempre manda o lembrete nesses casos (comportamento inalterado)."""
    fake = FakeSupabase()
    scheduler.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    assert _executar(scheduler._acao_ja_feita_recentemente(usuario_id, "aplicar_basal", agora)) is False
    assert _executar(scheduler._acao_ja_feita_recentemente(usuario_id, "outro", agora)) is False


# --------------------------------------------------------------------------
# _checar_lembretes: integração — pula o envio quando já feito, manda
# normalmente quando não.
# --------------------------------------------------------------------------

def _preparar_usuario_e_lembrete(fake: FakeSupabase, agora_local: datetime, tipo="medir_glicemia") -> tuple[dict, dict]:
    usuario = fake.table("usuarios").insert(
        {
            "id": str(uuid.uuid4()),
            "telefone": "5511999999999@c.us",
            "nome": "Pedro",
            "status_cadastro": "completo",
            "timezone": "America/Sao_Paulo",
        }
    ).execute().data[0]
    lembrete = fake.table("lembretes").insert(
        {
            "usuario_id": usuario["id"],
            "tipo": tipo,
            "horario": agora_local.strftime("%H:%M:%S"),
            "dias_semana": list(range(7)),
        }
    ).execute().data[0]
    return usuario, lembrete


_AGORA_LOCAL_FIXA = datetime(2026, 8, 6, 17, 0, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_checar_lembretes_pula_envio_quando_ja_feito():
    fake = FakeSupabase()
    scheduler.supabase = fake
    usuario, _lembrete = _preparar_usuario_e_lembrete(fake, _AGORA_LOCAL_FIXA)

    agora_utc = _AGORA_LOCAL_FIXA.astimezone(timezone.utc)
    fake.table("registros_glicemia").insert(
        {
            "usuario_id": usuario["id"],
            "valor": 110,
            "horario": (agora_utc - timedelta(minutes=10)).isoformat(),
        }
    ).execute()

    with patch.object(scheduler, "agora_usuario", return_value=_AGORA_LOCAL_FIXA), patch.object(
        scheduler, "enviar_mensagem", new=AsyncMock()
    ) as mock_enviar:
        _executar(scheduler._checar_lembretes())

    mock_enviar.assert_not_awaited()


def test_checar_lembretes_manda_normalmente_quando_nao_feito():
    fake = FakeSupabase()
    scheduler.supabase = fake
    _preparar_usuario_e_lembrete(fake, _AGORA_LOCAL_FIXA)

    with patch.object(scheduler, "agora_usuario", return_value=_AGORA_LOCAL_FIXA), patch.object(
        scheduler, "enviar_mensagem", new=AsyncMock()
    ) as mock_enviar:
        _executar(scheduler._checar_lembretes())

    mock_enviar.assert_awaited_once()


def test_checar_lembretes_basal_sempre_manda_mesmo_sem_dado_pra_checar():
    fake = FakeSupabase()
    scheduler.supabase = fake
    _preparar_usuario_e_lembrete(fake, _AGORA_LOCAL_FIXA, tipo="aplicar_basal")

    with patch.object(scheduler, "agora_usuario", return_value=_AGORA_LOCAL_FIXA), patch.object(
        scheduler, "enviar_mensagem", new=AsyncMock()
    ) as mock_enviar:
        _executar(scheduler._checar_lembretes())

    mock_enviar.assert_awaited_once()
