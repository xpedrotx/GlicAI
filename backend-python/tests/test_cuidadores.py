import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.services import cuidadores
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def _preparar_usuario(fake, usuario_id, nome="Ana"):
    fake.store["usuarios"] = [{"id": usuario_id, "nome": nome, "telefone": "5599@lid"}]


def test_tentar_vincular_ignora_mensagens_normais():
    fake = FakeSupabase()
    cuidadores.supabase = fake

    assert _executar(cuidadores.tentar_vincular("5511@c.us", "oi tudo bem")) is None
    assert _executar(cuidadores.tentar_vincular("5511@c.us", "glicemia 110")) is None


def test_tentar_vincular_com_codigo_valido_cria_cuidador():
    fake = FakeSupabase()
    cuidadores.supabase = fake
    usuario_id = str(uuid.uuid4())
    _preparar_usuario(fake, usuario_id)

    convite = _executar(cuidadores.gerar_convite(usuario_id))
    codigo = convite.split("*")[1]

    resposta = _executar(cuidadores.tentar_vincular("5511@c.us", f"vincular {codigo} Maria"))

    assert "Maria" in resposta
    assert len(fake.store["cuidadores"]) == 1
    assert fake.store["cuidadores"][0]["telefone"] == "5511@c.us"
    assert fake.store["cuidadores"][0]["nome"] == "Maria"
    assert fake.store["convites_cuidador"][0]["usado_em"] is not None


def test_tentar_vincular_remove_cadastro_de_paciente_abandonado_do_mesmo_numero():
    """
    Reproduz o bug real: alguém manda 'oi' antes de mandar o vincular (vira
    sem querer um paciente incompleto), depois manda 'vincular ...' — precisa
    linkar como cuidador mesmo assim, e o cadastro abandonado deve sumir pra
    não confundir mensagens futuras desse número com respostas de cadastro.
    """
    fake = FakeSupabase()
    cuidadores.supabase = fake
    usuario_id = str(uuid.uuid4())
    _preparar_usuario(fake, usuario_id)

    # simula o "oi" inicial que criou um usuario incompleto pra esse telefone
    fake.store["usuarios"].append(
        {"id": str(uuid.uuid4()), "telefone": "5511@c.us", "nome": None, "status_cadastro": "incompleto"}
    )

    convite = _executar(cuidadores.gerar_convite(usuario_id))
    codigo = convite.split("*")[1]

    resposta = _executar(cuidadores.tentar_vincular("5511@c.us", f"vincular {codigo} Geovana"))

    assert "Geovana" in resposta
    assert len(fake.store["cuidadores"]) == 1
    restantes = [u for u in fake.store["usuarios"] if u["telefone"] == "5511@c.us"]
    assert restantes == []


def test_tentar_vincular_codigo_invalido():
    fake = FakeSupabase()
    cuidadores.supabase = fake

    resposta = _executar(cuidadores.tentar_vincular("5511@c.us", "vincular 000000 Maria"))

    assert "não é válido" in resposta or "expirou" in resposta
    assert not fake.store.get("cuidadores")


def test_tentar_vincular_codigo_expirado():
    fake = FakeSupabase()
    cuidadores.supabase = fake
    usuario_id = str(uuid.uuid4())
    _preparar_usuario(fake, usuario_id)

    expirado = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    fake.store["convites_cuidador"] = [
        {
            "id": str(uuid.uuid4()),
            "usuario_id": usuario_id,
            "codigo": "111111",
            "expira_em": expirado,
            "usado_em": None,
        }
    ]

    resposta = _executar(cuidadores.tentar_vincular("5511@c.us", "vincular 111111 Maria"))

    assert "não é válido" in resposta or "expirou" in resposta
    assert not fake.store.get("cuidadores")


def test_tentar_vincular_bloqueia_apos_muitas_tentativas_de_codigo_invalido():
    fake = FakeSupabase()
    cuidadores.supabase = fake
    usuario_id = str(uuid.uuid4())
    _preparar_usuario(fake, usuario_id)
    convite = _executar(cuidadores.criar_convite(usuario_id))
    codigo_certo = convite["codigo"]

    telefone_atacante = "5599999999999@c.us"
    for _ in range(cuidadores.MAX_TENTATIVAS):
        _executar(cuidadores.tentar_vincular(telefone_atacante, "vincular 000000 Maria"))

    # código certo dessa vez, mas já bloqueado por tentativas anteriores
    resposta = _executar(cuidadores.tentar_vincular(telefone_atacante, f"vincular {codigo_certo} Maria"))

    assert "tentativas" in resposta.lower()
    assert not fake.store.get("cuidadores")


def test_eh_cuidador():
    fake = FakeSupabase()
    cuidadores.supabase = fake
    usuario_id = str(uuid.uuid4())
    _preparar_usuario(fake, usuario_id)

    assert _executar(cuidadores.eh_cuidador("5511@c.us")) is False

    convite = _executar(cuidadores.gerar_convite(usuario_id))
    codigo = convite.split("*")[1]
    _executar(cuidadores.tentar_vincular("5511@c.us", f"vincular {codigo} Maria"))

    assert _executar(cuidadores.eh_cuidador("5511@c.us")) is True


def test_remover_cuidador_desativa():
    fake = FakeSupabase()
    cuidadores.supabase = fake
    usuario_id = str(uuid.uuid4())
    _preparar_usuario(fake, usuario_id)

    convite = _executar(cuidadores.gerar_convite(usuario_id))
    codigo = convite.split("*")[1]
    _executar(cuidadores.tentar_vincular("5511@c.us", f"vincular {codigo} Maria"))

    resposta = _executar(cuidadores.remover_cuidador(usuario_id, "Maria"))
    assert "Maria" in resposta
    assert _executar(cuidadores.eh_cuidador("5511@c.us")) is False
