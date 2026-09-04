import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.services import auth_web
from tests.fake_supabase import FakeSupabase

CPF_VALIDO = "111.444.777-35"
CPF_VALIDO_2 = "529.982.247-25"


def _executar(coro):
    return asyncio.run(coro)


def _criar_usuario(fake: FakeSupabase, telefone="235299934343350@lid") -> dict:
    # telefone por padrão é um JID @lid de propósito — é o cenário real que
    # motivou o redesenho do fluxo (não dá pra "adivinhar" isso a partir de
    # um número de telefone digitado no site).
    return fake.table("usuarios").insert(
        {"id": str(uuid.uuid4()), "telefone": telefone, "nome": "Pedro", "status_cadastro": "completo"}
    ).execute().data[0]


def _inserir_codigo(fake: FakeSupabase, usuario_id: str, codigo="123456", minutos_para_expirar=10, usado_em=None):
    fake.table("codigos_login_web").insert(
        {
            "usuario_id": usuario_id,
            "codigo": codigo,
            "expira_em": (datetime.now(timezone.utc) + timedelta(minutes=minutos_para_expirar)).isoformat(),
            "usado_em": usado_em,
        }
    ).execute()


# --------------------------------------------------------------------------
# gerar_codigo_login: chamado pelo comando "criar senha" no WhatsApp —
# devolve o texto pronto, quem entrega é o roteador de comandos normal (que
# já sabe endereçar @c.us ou @lid corretamente).
# --------------------------------------------------------------------------

def test_gerar_codigo_login_cria_registro_e_devolve_texto_com_o_codigo():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)

    texto = auth_web.gerar_codigo_login(usuario["id"])

    codigos = fake.table("codigos_login_web").select("*").eq("usuario_id", usuario["id"]).execute().data
    assert len(codigos) == 1
    assert len(codigos[0]["codigo"]) == 6
    assert codigos[0]["codigo"] in texto


# --------------------------------------------------------------------------
# confirmar_codigo: identifica o usuário só pelo código (não usa telefone)
# --------------------------------------------------------------------------

def test_confirmar_codigo_com_dados_validos_cria_conta_e_sessao():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"])

    token = _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "senha-forte-123", "203.0.113.1"))

    assert token
    linha = fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data[0]
    assert linha["cpf"] == "11144477735"
    assert linha["senha_hash"] is not None
    assert linha["senha_hash"] != "senha-forte-123"  # nunca texto puro

    sessoes = fake.table("sessoes_web").select("*").eq("usuario_id", usuario["id"]).execute().data
    assert len(sessoes) == 1

    codigo_usado = fake.table("codigos_login_web").select("*").eq("usuario_id", usuario["id"]).execute().data[0]
    assert codigo_usado["usado_em"] is not None


def test_confirmar_codigo_funciona_pra_conta_vinculada_via_lid():
    """
    Reproduz literalmente o bug real relatado: conta cujo telefone é um JID
    @lid (sem relação nenhuma com o número de telefone real) — como o fluxo
    não depende mais de telefone nenhum, funciona igual a uma conta @c.us.
    """
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake, telefone="235299934343350@lid")
    _inserir_codigo(fake, usuario["id"])

    token = _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "senha-forte-123", "203.0.113.1"))
    assert token


def test_confirmar_codigo_invalido_rejeita():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"], codigo="123456")

    try:
        _executar(auth_web.confirmar_codigo("000000", CPF_VALIDO, "senha-forte-123", "203.0.113.1"))
        assert False, "devia ter levantado ErroAutenticacao"
    except auth_web.ErroAutenticacao as erro:
        assert "inválido" in str(erro).lower() or "expirado" in str(erro).lower()


def test_confirmar_codigo_expirado_rejeita():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"], minutos_para_expirar=-5)

    try:
        _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "senha-forte-123", "203.0.113.1"))
        assert False, "devia ter levantado ErroAutenticacao"
    except auth_web.ErroAutenticacao:
        pass


def test_confirmar_codigo_ja_usado_rejeita():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"], usado_em=datetime.now(timezone.utc).isoformat())

    try:
        _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "senha-forte-123", "203.0.113.1"))
        assert False, "devia ter levantado ErroAutenticacao"
    except auth_web.ErroAutenticacao:
        pass


def test_confirmar_codigo_com_cpf_invalido_rejeita():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"])

    try:
        _executar(auth_web.confirmar_codigo("123456", "11111111111", "senha-forte-123", "203.0.113.1"))
        assert False, "devia ter levantado ErroAutenticacao"
    except auth_web.ErroAutenticacao as erro:
        assert "cpf" in str(erro).lower()


def test_confirmar_codigo_com_senha_curta_rejeita():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"])

    try:
        _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "123", "203.0.113.1"))
        assert False, "devia ter levantado ErroAutenticacao"
    except auth_web.ErroAutenticacao as erro:
        assert "senha" in str(erro).lower()


def test_confirmar_codigo_com_cpf_ja_usado_por_outra_conta_rejeita():
    fake = FakeSupabase()
    auth_web.supabase = fake
    outro_usuario = _criar_usuario(fake, telefone="5511888888888@c.us")
    fake.table("usuarios").update({"cpf": "11144477735"}).eq("id", outro_usuario["id"]).execute()

    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"])

    try:
        _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "senha-forte-123", "203.0.113.1"))
        assert False, "devia ter levantado ErroAutenticacao"
    except auth_web.ErroAutenticacao as erro:
        assert "cpf" in str(erro).lower()


# --------------------------------------------------------------------------
# login: CPF + senha
# --------------------------------------------------------------------------

def test_login_com_credenciais_corretas_cria_sessao():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"])
    _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "senha-forte-123", "203.0.113.1"))

    token = _executar(auth_web.login(CPF_VALIDO, "senha-forte-123", "203.0.113.1"))
    assert token


def test_login_com_senha_errada_rejeita():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"])
    _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "senha-forte-123", "203.0.113.1"))

    try:
        _executar(auth_web.login(CPF_VALIDO, "senha-errada", "203.0.113.1"))
        assert False, "devia ter levantado ErroAutenticacao"
    except auth_web.ErroAutenticacao as erro:
        assert "inválidos" in str(erro).lower()


def test_login_com_cpf_desconhecido_rejeita():
    fake = FakeSupabase()
    auth_web.supabase = fake

    try:
        _executar(auth_web.login(CPF_VALIDO_2, "qualquer-senha", "203.0.113.1"))
        assert False, "devia ter levantado ErroAutenticacao"
    except auth_web.ErroAutenticacao:
        pass


# --------------------------------------------------------------------------
# sessão: validar e revogar
# --------------------------------------------------------------------------

def test_validar_sessao_com_token_valido_retorna_usuario():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)

    token = _executar(auth_web.criar_sessao(usuario["id"]))
    validado = _executar(auth_web.validar_sessao(token))

    assert validado is not None
    assert validado["id"] == usuario["id"]


def test_validar_sessao_com_token_invalido_retorna_none():
    fake = FakeSupabase()
    auth_web.supabase = fake

    assert _executar(auth_web.validar_sessao("token-que-nao-existe")) is None
    assert _executar(auth_web.validar_sessao(None)) is None


def test_validar_sessao_expirada_retorna_none():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    token = "token-fixo-de-teste"
    fake.table("sessoes_web").insert(
        {
            "usuario_id": usuario["id"],
            "token_hash": auth_web._hash_token(token),
            "expira_em": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        }
    ).execute()

    assert _executar(auth_web.validar_sessao(token)) is None


def test_logout_revoga_a_sessao():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    token = _executar(auth_web.criar_sessao(usuario["id"]))

    assert _executar(auth_web.validar_sessao(token)) is not None
    _executar(auth_web.logout(token))
    assert _executar(auth_web.validar_sessao(token)) is None


# --------------------------------------------------------------------------
# rate limiting: bloqueia por IP depois de tentativas falhas repetidas —
# proteção contra força bruta no código de 6 dígitos / senha.
# --------------------------------------------------------------------------

def test_login_bloqueia_apos_muitas_tentativas_falhas_do_mesmo_ip():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"])
    _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "senha-forte-123", "198.51.100.9"))

    ip_atacante = "198.51.100.50"
    for _ in range(auth_web.MAX_TENTATIVAS):
        try:
            _executar(auth_web.login(CPF_VALIDO, "senha-errada", ip_atacante))
        except auth_web.ErroAutenticacao:
            pass

    try:
        _executar(auth_web.login(CPF_VALIDO, "senha-forte-123", ip_atacante))  # senha certa dessa vez
        assert False, "devia estar bloqueado, mesmo com a senha certa"
    except auth_web.ErroAutenticacao as erro:
        assert "tentativas" in str(erro).lower()


def test_login_de_ip_diferente_nao_e_afetado_pelo_bloqueio_de_outro():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"])
    _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "senha-forte-123", "198.51.100.9"))

    for _ in range(auth_web.MAX_TENTATIVAS):
        try:
            _executar(auth_web.login(CPF_VALIDO, "senha-errada", "198.51.100.50"))
        except auth_web.ErroAutenticacao:
            pass

    # IP diferente, nunca tentou antes — não deve estar bloqueado.
    token = _executar(auth_web.login(CPF_VALIDO, "senha-forte-123", "198.51.100.99"))
    assert token


def test_confirmar_codigo_bloqueia_apos_muitas_tentativas_falhas_do_mesmo_ip():
    fake = FakeSupabase()
    auth_web.supabase = fake
    usuario = _criar_usuario(fake)
    _inserir_codigo(fake, usuario["id"])

    ip_atacante = "198.51.100.60"
    for _ in range(auth_web.MAX_TENTATIVAS):
        try:
            _executar(auth_web.confirmar_codigo("000000", CPF_VALIDO, "senha-forte-123", ip_atacante))
        except auth_web.ErroAutenticacao:
            pass

    try:
        _executar(auth_web.confirmar_codigo("123456", CPF_VALIDO, "senha-forte-123", ip_atacante))  # código certo
        assert False, "devia estar bloqueado, mesmo com o código certo"
    except auth_web.ErroAutenticacao as erro:
        assert "tentativas" in str(erro).lower()
