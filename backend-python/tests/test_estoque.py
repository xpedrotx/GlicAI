import asyncio
import uuid

from app.services import estoque
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def test_consumir_sem_configuracao_retorna_none():
    fake = FakeSupabase()
    estoque.supabase = fake

    assert _executar(estoque.consumir(str(uuid.uuid4()), "insulina", 4)) is None


def test_configurar_e_consumir_sem_atingir_limite():
    fake = FakeSupabase()
    estoque.supabase = fake
    usuario_id = str(uuid.uuid4())

    _executar(estoque.configurar(usuario_id, "insulina", 300, 60))
    aviso = _executar(estoque.consumir(usuario_id, "insulina", 4))

    assert aviso is None
    linha = _executar(estoque.buscar(usuario_id, "insulina"))
    assert linha["quantidade_atual"] == 296


def test_consumir_abaixo_do_limite_gera_aviso():
    fake = FakeSupabase()
    estoque.supabase = fake
    usuario_id = str(uuid.uuid4())

    _executar(estoque.configurar(usuario_id, "insulina", 300, 60))
    _executar(estoque.reabastecer(usuario_id, "insulina", 62))

    aviso = _executar(estoque.consumir(usuario_id, "insulina", 4))

    assert aviso is not None
    assert "insulina" in aviso.lower()
    assert "58" in aviso


def test_consumir_nunca_fica_negativo():
    fake = FakeSupabase()
    estoque.supabase = fake
    usuario_id = str(uuid.uuid4())

    _executar(estoque.configurar(usuario_id, "fita_dextro", 10, 2))
    _executar(estoque.consumir(usuario_id, "fita_dextro", 15))

    linha = _executar(estoque.buscar(usuario_id, "fita_dextro"))
    assert linha["quantidade_atual"] == 0


def test_limite_padrao_e_20_por_cento_quando_nao_informado():
    fake = FakeSupabase()
    estoque.supabase = fake
    usuario_id = str(uuid.uuid4())

    _executar(estoque.configurar(usuario_id, "fita_dextro", 50, 10))
    linha = _executar(estoque.buscar(usuario_id, "fita_dextro"))
    assert linha["limite_alerta"] == 10


def test_reabastecer_sem_configuracao_retorna_false():
    fake = FakeSupabase()
    estoque.supabase = fake

    resultado = _executar(estoque.reabastecer(str(uuid.uuid4()), "insulina", 300))
    assert resultado is False


def test_listar_retorna_todos_os_tipos_configurados():
    fake = FakeSupabase()
    estoque.supabase = fake
    usuario_id = str(uuid.uuid4())

    _executar(estoque.configurar(usuario_id, "insulina", 300, 60))
    _executar(estoque.configurar(usuario_id, "fita_dextro", 50, 10))

    linhas = _executar(estoque.listar(usuario_id))
    tipos = {l["tipo"] for l in linhas}
    assert tipos == {"insulina", "fita_dextro"}
