import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.services import remedicao
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def test_agendar_cria_lembrete_15min_no_futuro():
    fake = FakeSupabase()
    remedicao.supabase = fake
    usuario_id = str(uuid.uuid4())

    _executar(remedicao.agendar(usuario_id))

    linhas = fake.store["lembretes_remedicao"]
    assert len(linhas) == 1
    assert linhas[0]["usuario_id"] == usuario_id
    assert linhas[0]["enviado"] is False
    disparar_em = datetime.fromisoformat(linhas[0]["disparar_em"])
    delta = disparar_em - datetime.now(timezone.utc)
    assert timedelta(minutes=14) < delta < timedelta(minutes=16)


def test_verificar_pendentes_manda_e_marca_enviado_quando_vencido():
    fake = FakeSupabase()
    remedicao.supabase = fake
    usuario = fake.table("usuarios").insert({"telefone": "5545999999999@c.us", "nome": "Pedro"}).execute().data[0]
    vencido = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    lembrete = fake.table("lembretes_remedicao").insert(
        {"usuario_id": usuario["id"], "disparar_em": vencido, "enviado": False}
    ).execute().data[0]

    with patch.object(remedicao, "enviar_mensagem", new=AsyncMock()) as mock_enviar:
        _executar(remedicao.verificar_pendentes())

    mock_enviar.assert_awaited_once()
    assert "15 minutos" in mock_enviar.await_args.args[1]
    atualizado = next(l for l in fake.store["lembretes_remedicao"] if l["id"] == lembrete["id"])
    assert atualizado["enviado"] is True


def test_verificar_pendentes_ignora_lembrete_ainda_nao_vencido():
    fake = FakeSupabase()
    remedicao.supabase = fake
    usuario = fake.table("usuarios").insert({"telefone": "5545999999999@c.us", "nome": "Pedro"}).execute().data[0]
    no_futuro = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    fake.table("lembretes_remedicao").insert(
        {"usuario_id": usuario["id"], "disparar_em": no_futuro, "enviado": False}
    ).execute()

    with patch.object(remedicao, "enviar_mensagem", new=AsyncMock()) as mock_enviar:
        _executar(remedicao.verificar_pendentes())

    mock_enviar.assert_not_awaited()


def test_verificar_pendentes_ignora_lembrete_ja_enviado():
    fake = FakeSupabase()
    remedicao.supabase = fake
    usuario = fake.table("usuarios").insert({"telefone": "5545999999999@c.us", "nome": "Pedro"}).execute().data[0]
    vencido = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    fake.table("lembretes_remedicao").insert(
        {"usuario_id": usuario["id"], "disparar_em": vencido, "enviado": True}
    ).execute()

    with patch.object(remedicao, "enviar_mensagem", new=AsyncMock()) as mock_enviar:
        _executar(remedicao.verificar_pendentes())

    mock_enviar.assert_not_awaited()
