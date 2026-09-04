import asyncio
import uuid

from app.services import perfil
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def _criar_perfil(fake: FakeSupabase, usuario_id: str, **overrides) -> dict:
    base = {
        "usuario_id": usuario_id,
        "meta_glicemia": 120,
        "limite_baixo": 70,
        "limite_alto": 180,
        "fator_sensibilidade": 30,
    }
    base.update(overrides)
    return fake.table("perfil_glicemico").insert(base).execute().data[0]


# --------------------------------------------------------------------------
# buscar_perfil_completo
# --------------------------------------------------------------------------

def test_buscar_perfil_completo_traz_perfil_e_listas_relacionadas():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute()
    _criar_perfil(fake, usuario_id)
    fake.table("relacao_ic").insert(
        {"usuario_id": usuario_id, "periodo": "café", "hora_inicio": "06:00", "hora_fim": "10:00", "gramas_por_unidade": 15}
    ).execute()
    fake.table("basal").insert(
        {"usuario_id": usuario_id, "horario": "22:00", "dose": 10, "tipo_insulina": "Lantus"}
    ).execute()
    fake.table("modificadores_bolus").insert(
        {"usuario_id": usuario_id, "nome": "Exercício", "tipo_ajuste": "percentual", "valor_ajuste": -20, "ativo": True}
    ).execute()

    dados = _executar(perfil.buscar_perfil_completo(usuario_id))

    assert dados["nome"] == "Pedro"
    assert dados["perfil"]["meta_glicemia"] == 120
    assert len(dados["relacoes_ic"]) == 1
    assert len(dados["basal"]) == 1
    assert len(dados["modificadores"]) == 1


def test_buscar_perfil_completo_sem_cadastro_retorna_none():
    fake = FakeSupabase()
    perfil.supabase = fake

    assert _executar(perfil.buscar_perfil_completo(str(uuid.uuid4()))) is None


# --------------------------------------------------------------------------
# atualizar_nome
# --------------------------------------------------------------------------

def test_atualizar_nome_com_sucesso():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute()

    _executar(perfil.atualizar_nome(usuario_id, "Pedro Lisboa"))

    linha = fake.table("usuarios").select("*").eq("id", usuario_id).execute().data[0]
    assert linha["nome"] == "Pedro Lisboa"


def test_atualizar_nome_vazio_rejeita():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())

    try:
        _executar(perfil.atualizar_nome(usuario_id, "   "))
        assert False, "devia ter levantado ErroValidacaoPerfil"
    except perfil.ErroValidacaoPerfil:
        pass


# --------------------------------------------------------------------------
# atualizar_campo_perfil — mesmas regras de comandos.py::_editar
# --------------------------------------------------------------------------

def test_atualizar_meta_valida():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    _criar_perfil(fake, usuario_id)

    _executar(perfil.atualizar_campo_perfil(usuario_id, "meta_glicemia", 110))

    linha = fake.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data[0]
    assert linha["meta_glicemia"] == 110


def test_atualizar_meta_fora_da_faixa_absoluta_rejeita():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    _criar_perfil(fake, usuario_id)

    try:
        _executar(perfil.atualizar_campo_perfil(usuario_id, "meta_glicemia", 500))
        assert False
    except perfil.ErroValidacaoPerfil as erro:
        assert "40 e 300" in str(erro)


def test_atualizar_meta_incompativel_com_limites_rejeita():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    _criar_perfil(fake, usuario_id)  # limite_baixo=70, limite_alto=180

    try:
        _executar(perfil.atualizar_campo_perfil(usuario_id, "meta_glicemia", 200))
        assert False
    except perfil.ErroValidacaoPerfil as erro:
        assert "limites atuais" in str(erro)


def test_atualizar_limite_baixo_maior_que_meta_rejeita():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    _criar_perfil(fake, usuario_id)

    try:
        _executar(perfil.atualizar_campo_perfil(usuario_id, "limite_baixo", 150))
        assert False
    except perfil.ErroValidacaoPerfil as erro:
        assert "menor que sua meta" in str(erro)


def test_atualizar_limite_alto_menor_que_meta_rejeita():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    _criar_perfil(fake, usuario_id)

    try:
        _executar(perfil.atualizar_campo_perfil(usuario_id, "limite_alto", 50))
        assert False
    except perfil.ErroValidacaoPerfil as erro:
        assert "maior que sua meta" in str(erro)


def test_atualizar_fator_zero_ou_negativo_rejeita():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    _criar_perfil(fake, usuario_id)

    try:
        _executar(perfil.atualizar_campo_perfil(usuario_id, "fator_sensibilidade", 0))
        assert False
    except perfil.ErroValidacaoPerfil as erro:
        assert "maior que zero" in str(erro)


def test_atualizar_tempo_insulina_ativa_fora_da_faixa_rejeita():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    _criar_perfil(fake, usuario_id)

    try:
        _executar(perfil.atualizar_campo_perfil(usuario_id, "tempo_insulina_ativa_horas", 12))
        assert False
    except perfil.ErroValidacaoPerfil as erro:
        assert "1 e 8" in str(erro)


def test_atualizar_tempo_insulina_ativa_valido_mantem_casa_decimal():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    _criar_perfil(fake, usuario_id)

    _executar(perfil.atualizar_campo_perfil(usuario_id, "tempo_insulina_ativa_horas", 4.5))

    linha = fake.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data[0]
    assert linha["tempo_insulina_ativa_horas"] == 4.5


def test_atualizar_campo_nao_reconhecido_rejeita():
    fake = FakeSupabase()
    perfil.supabase = fake
    usuario_id = str(uuid.uuid4())
    _criar_perfil(fake, usuario_id)

    try:
        _executar(perfil.atualizar_campo_perfil(usuario_id, "campo_invalido", 10))
        assert False
    except perfil.ErroValidacaoPerfil as erro:
        assert "não reconhecido" in str(erro).lower()


def test_atualizar_campo_sem_perfil_rejeita():
    fake = FakeSupabase()
    perfil.supabase = fake

    try:
        _executar(perfil.atualizar_campo_perfil(str(uuid.uuid4()), "meta_glicemia", 110))
        assert False
    except perfil.ErroValidacaoPerfil as erro:
        assert "não encontrado" in str(erro).lower()
