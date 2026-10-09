import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.routes import medico_api, web_api
from app.services import auth_web, comandos, exportacao, medicos
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def _ligar(fake):
    medicos.supabase = fake
    auth_web.supabase = fake
    comandos.supabase = fake
    exportacao.supabase = fake


class CaixaDeEmail:
    """Troca o envio real (Resend) por uma lista, pra o teste ler o código que iria no e-mail."""

    def __init__(self):
        self.enviados: list[dict] = []

    async def enviar(self, para, assunto, texto, html):
        self.enviados.append({"para": para, "assunto": assunto, "texto": texto, "html": html})

    @property
    def ultimo_codigo(self) -> str:
        return re.search(r"\b(\d{6})\b", self.enviados[-1]["texto"]).group(1)


@pytest.fixture
def caixa(monkeypatch):
    caixa = CaixaDeEmail()
    monkeypatch.setattr(medicos.email_envio, "enviar", caixa.enviar)
    return caixa


def _medico(fake, nome="Ana Souza", email="ana@clinica.com", ip="1.1.1.1"):
    """Cadastro completo: pede o código, lê do e-mail e confirma."""
    caixa = CaixaDeEmail()
    with patch.object(medicos.email_envio, "enviar", new=caixa.enviar):
        _executar(medicos.iniciar_cadastro(nome, email, "123456", "SP", "senha-segura", ip))
    token = _executar(medicos.confirmar_email(email, caixa.ultimo_codigo))
    return _executar(medicos.validar_sessao(token)), token


def _paciente(fake, nome="Pedro", telefone=None):
    return fake.table("usuarios").insert(
        {"id": str(uuid.uuid4()), "nome": nome, "telefone": telefone or f"{uuid.uuid4().hex[:12]}@lid",
         "status_cadastro": "completo", "timezone": "America/Sao_Paulo"}
    ).execute().data[0]


def _perfil(fake, usuario):
    fake.table("perfil_glicemico").insert(
        {"usuario_id": usuario["id"], "meta_glicemia": 110, "limite_baixo": 70, "limite_alto": 180, "fator_sensibilidade": 40}
    ).execute()


def _leitura(fake, usuario, valor, horas_atras=1):
    fake.table("registros_glicemia").insert(
        {"usuario_id": usuario["id"], "valor": valor,
         "horario": (datetime.now(timezone.utc) - timedelta(hours=horas_atras)).isoformat()}
    ).execute()


# --------------------------------------------------------------------------
# código de vinculação
# --------------------------------------------------------------------------

@pytest.mark.parametrize("texto", ["DR-K7M2QX", "dr-k7m2qx", "k7m2qx", "dr k7m2qx", " DR K7M2QX "])
def test_codigo_aceita_varias_formas_de_digitar(texto):
    assert medicos.normalizar_codigo(texto) == "DR-K7M2QX"


@pytest.mark.parametrize("texto", ["", "DR-K7M2Q", "DR-K7M2QXX", "DR-K0M2QX", "DR-KIM2QX", "oi", "123456"])
def test_codigo_invalido_e_recusado(texto):
    assert medicos.normalizar_codigo(texto) is None


def test_codigos_gerados_sao_validos_e_diferentes():
    codigos = {medicos._gerar_codigo() for _ in range(200)}
    assert len(codigos) > 190
    assert all(medicos.normalizar_codigo(c) == c for c in codigos)


# --------------------------------------------------------------------------
# conta do médico
# --------------------------------------------------------------------------

def test_cadastro_so_cria_a_conta_depois_de_confirmar_o_e_mail(caixa):
    fake = FakeSupabase()
    _ligar(fake)

    _executar(medicos.iniciar_cadastro("Ana Souza", "ANA@Clinica.com", "123456", "SP", "senha-segura", "1.1.1.1"))
    assert fake.store.get("medicos", []) == []  # ainda não existe conta
    assert caixa.enviados[0]["para"] == "ana@clinica.com"
    codigo = caixa.ultimo_codigo
    pendente = fake.store["cadastros_medico_pendentes"][0]
    assert codigo not in str(pendente)  # só o hash do código fica guardado
    assert pendente["senha_hash"].startswith("$2")

    token = _executar(medicos.confirmar_email("ana@clinica.com", codigo))
    medico = _executar(medicos.validar_sessao(token))
    assert medico["nome"] == "Ana Souza" and medico["uf"] == "SP"
    assert medico["codigo_vinculo"].startswith("DR-")
    assert medico["senha_hash"] != "senha-segura"
    assert "senha_hash" not in medicos.dados_publicos(medico)
    assert fake.store["cadastros_medico_pendentes"] == []  # pendente some depois de confirmar
    assert token not in str(fake.store["sessoes_medico"])  # só o hash da sessão fica no banco


@pytest.mark.parametrize(
    "campo,valor,mensagem",
    [
        ("nome", "A", "nome completo"),
        ("email", "sem-arroba", "E-mail inválido"),
        ("crm", "12", "CRM"),
        ("uf", "XX", "UF"),
        ("senha", "curta", "pelo menos 8"),
    ],
)
def test_cadastro_valida_os_campos(campo, valor, mensagem, caixa):
    fake = FakeSupabase()
    _ligar(fake)
    dados = {"nome": "Ana Souza", "email": "ana@clinica.com", "crm": "123456", "uf": "SP", "senha": "senha-segura"}
    dados[campo] = valor
    with pytest.raises(auth_web.ErroAutenticacao, match=mensagem):
        _executar(medicos.iniciar_cadastro(dados["nome"], dados["email"], dados["crm"], dados["uf"], dados["senha"], "1.1.1.1"))
    assert fake.store.get("medicos", []) == [] and caixa.enviados == []


def test_cadastro_recusa_email_repetido_sem_diferenciar_maiusculas(caixa):
    fake = FakeSupabase()
    _ligar(fake)
    _medico(fake)
    with pytest.raises(auth_web.ErroAutenticacao, match="Já existe"):
        _executar(medicos.iniciar_cadastro("Outro Nome", "ANA@Clinica.com", "999999", "RJ", "senha-segura", "2.2.2.2"))


def test_cadastro_em_massa_pelo_mesmo_ip_e_barrado():
    fake = FakeSupabase()
    _ligar(fake)
    for i in range(auth_web.MAX_TENTATIVAS):
        _medico(fake, nome=f"Medico {i}", email=f"m{i}@x.com", ip="9.9.9.9")
    with pytest.raises(auth_web.ErroAutenticacao, match="Muitas tentativas"):
        _medico(fake, nome="Mais Um", email="mais@x.com", ip="9.9.9.9")


def _iniciar(caixa, email="ana@clinica.com", ip="1.1.1.1"):
    return _executar(medicos.iniciar_cadastro("Ana Souza", email, "123456", "SP", "senha-segura", ip))


def test_codigo_do_email_errado_conta_tentativas_e_depois_descarta_o_cadastro(caixa):
    fake = FakeSupabase()
    _ligar(fake)
    _iniciar(caixa)
    certo = caixa.ultimo_codigo
    errado = "000000" if certo != "000000" else "111111"

    for restantes in (4, 3, 2, 1):
        with pytest.raises(auth_web.ErroAutenticacao, match=f"mais {restantes} tentativa"):
            _executar(medicos.confirmar_email("ana@clinica.com", errado))
    with pytest.raises(auth_web.ErroAutenticacao, match="Muitos erros"):
        _executar(medicos.confirmar_email("ana@clinica.com", errado))

    # depois do limite nem o código certo vale: é preciso recomeçar
    with pytest.raises(auth_web.ErroAutenticacao, match="inválido ou expirado"):
        _executar(medicos.confirmar_email("ana@clinica.com", certo))
    assert fake.store.get("medicos", []) == []


def test_codigo_do_email_expira(caixa):
    fake = FakeSupabase()
    _ligar(fake)
    _iniciar(caixa)
    fake.store["cadastros_medico_pendentes"][0]["expira_em"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

    with pytest.raises(auth_web.ErroAutenticacao, match="expirou"):
        _executar(medicos.confirmar_email("ana@clinica.com", caixa.ultimo_codigo))
    assert fake.store.get("medicos", []) == []


def test_confirmar_aceita_o_codigo_com_espacos_e_sem_cadastro_pendente_falha(caixa):
    fake = FakeSupabase()
    _ligar(fake)
    with pytest.raises(auth_web.ErroAutenticacao, match="inválido ou expirado"):
        _executar(medicos.confirmar_email("ninguem@x.com", "123456"))

    _iniciar(caixa)
    codigo = caixa.ultimo_codigo
    token = _executar(medicos.confirmar_email(" ANA@clinica.com ", f"{codigo[:3]} {codigo[3:]}"))
    assert _executar(medicos.validar_sessao(token)) is not None


def test_nao_deixa_confirmar_duas_vezes_o_mesmo_cadastro(caixa):
    fake = FakeSupabase()
    _ligar(fake)
    _iniciar(caixa)
    codigo = caixa.ultimo_codigo
    _executar(medicos.confirmar_email("ana@clinica.com", codigo))
    with pytest.raises(auth_web.ErroAutenticacao):
        _executar(medicos.confirmar_email("ana@clinica.com", codigo))
    assert len(fake.store["medicos"]) == 1


def test_falha_no_envio_do_email_nao_deixa_cadastro_pendente(monkeypatch):
    fake = FakeSupabase()
    _ligar(fake)

    async def quebrado(*_a, **_k):
        raise medicos.email_envio.EmailIndisponivel("fora do ar")

    monkeypatch.setattr(medicos.email_envio, "enviar", quebrado)
    with pytest.raises(auth_web.ErroAutenticacao, match="enviar o e-mail"):
        _executar(medicos.iniciar_cadastro("Ana Souza", "ana@clinica.com", "123456", "SP", "senha-segura", "1.1.1.1"))
    assert fake.store.get("cadastros_medico_pendentes", []) == []
    assert fake.store.get("tentativas_auth", []) == []  # nem gasta a cota de tentativas do IP


def test_recomecar_o_cadastro_substitui_o_pendente_e_invalida_o_codigo_anterior(caixa):
    fake = FakeSupabase()
    _ligar(fake)
    _iniciar(caixa)
    primeiro = caixa.ultimo_codigo
    _iniciar(caixa)
    segundo = caixa.ultimo_codigo

    assert len(fake.store["cadastros_medico_pendentes"]) == 1
    if primeiro != segundo:
        with pytest.raises(auth_web.ErroAutenticacao, match="incorreto"):
            _executar(medicos.confirmar_email("ana@clinica.com", primeiro))
    assert _executar(medicos.validar_sessao(_executar(medicos.confirmar_email("ana@clinica.com", segundo)))) is not None


def test_reenviar_codigo_tem_intervalo_e_limite(caixa):
    fake = FakeSupabase()
    _ligar(fake)
    _iniciar(caixa)

    with pytest.raises(auth_web.ErroAutenticacao, match="Aguarde um minuto"):
        _executar(medicos.reenviar_codigo("ana@clinica.com"))

    for i in range(medicos.MAX_REENVIOS):
        fake.store["cadastros_medico_pendentes"][0]["ultimo_envio_em"] = (
            datetime.now(timezone.utc) - timedelta(minutes=2)
        ).isoformat()
        _executar(medicos.reenviar_codigo("ana@clinica.com"))
    assert len(caixa.enviados) == 1 + medicos.MAX_REENVIOS

    fake.store["cadastros_medico_pendentes"][0]["ultimo_envio_em"] = (
        datetime.now(timezone.utc) - timedelta(minutes=2)
    ).isoformat()
    with pytest.raises(auth_web.ErroAutenticacao, match="Muitos reenvios"):
        _executar(medicos.reenviar_codigo("ana@clinica.com"))

    # o último código enviado é o que vale
    token = _executar(medicos.confirmar_email("ana@clinica.com", caixa.ultimo_codigo))
    assert _executar(medicos.validar_sessao(token)) is not None


def test_reenviar_sem_cadastro_pendente_falha(caixa):
    fake = FakeSupabase()
    _ligar(fake)
    with pytest.raises(auth_web.ErroAutenticacao, match="Não achei"):
        _executar(medicos.reenviar_codigo("ninguem@x.com"))


def test_email_nao_leva_html_do_nome_digitado(caixa):
    fake = FakeSupabase()
    _ligar(fake)
    _executar(medicos.iniciar_cadastro("<script>alert(1)</script> Silva", "ana@clinica.com", "123456", "SP", "senha-segura", "1.1.1.1"))
    assert "<script>" not in caixa.enviados[0]["html"]


def test_login_e_sessao_e_logout():
    fake = FakeSupabase()
    _ligar(fake)
    _medico(fake)

    token = _executar(medicos.login("ANA@clinica.com ", "senha-segura", "3.3.3.3"))
    assert _executar(medicos.validar_sessao(token))["email"] == "ana@clinica.com"

    _executar(medicos.logout(token))
    assert _executar(medicos.validar_sessao(token)) is None
    assert _executar(medicos.validar_sessao(None)) is None


def test_login_erra_com_mensagem_generica_e_bloqueia_forca_bruta():
    fake = FakeSupabase()
    _ligar(fake)
    _medico(fake)

    for senha, email in [("errada-123", "ana@clinica.com"), ("qualquer-123", "naoexiste@x.com")]:
        with pytest.raises(auth_web.ErroAutenticacao, match="E-mail ou senha inválidos"):
            _executar(medicos.login(email, senha, "4.4.4.4"))

    for _ in range(auth_web.MAX_TENTATIVAS):
        with pytest.raises(auth_web.ErroAutenticacao):
            _executar(medicos.login("ana@clinica.com", "errada-123", "5.5.5.5"))
    # bloqueado mesmo com a senha certa
    with pytest.raises(auth_web.ErroAutenticacao, match="Muitas tentativas"):
        _executar(medicos.login("ana@clinica.com", "senha-segura", "5.5.5.5"))


def test_sessao_expirada_nao_vale():
    fake = FakeSupabase()
    _ligar(fake)
    medico, token = _medico(fake)
    fake.store["sessoes_medico"][0]["expira_em"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert _executar(medicos.validar_sessao(token)) is None
    assert medico["id"]


# --------------------------------------------------------------------------
# vínculo
# --------------------------------------------------------------------------

def test_paciente_vincula_com_o_codigo_e_aparece_nas_duas_pontas():
    fake = FakeSupabase()
    _ligar(fake)
    medico, _ = _medico(fake)
    paciente = _paciente(fake)

    achado = _executar(medicos.buscar_por_codigo(medico["codigo_vinculo"].lower(), paciente["id"]))
    assert achado["id"] == medico["id"]
    assert _executar(medicos.vincular(paciente["id"], achado)) is True
    assert _executar(medicos.vincular(paciente["id"], achado)) is False  # já vinculado

    assert [m["nome"] for m in _executar(medicos.medicos_do_paciente(paciente["id"]))] == ["Ana Souza"]
    assert [p["id"] for p in _executar(medicos.pacientes_do_medico(medico["id"]))] == [paciente["id"]]


def test_codigo_errado_e_barrado_depois_de_varias_tentativas():
    fake = FakeSupabase()
    _ligar(fake)
    _medico(fake)
    paciente = _paciente(fake)

    for _ in range(auth_web.MAX_TENTATIVAS):
        with pytest.raises(medicos.ErroMedico, match="Não encontrei"):
            _executar(medicos.buscar_por_codigo("DR-AAAAAA", paciente["id"]))
    with pytest.raises(auth_web.ErroAutenticacao, match="Muitas tentativas"):
        _executar(medicos.buscar_por_codigo("DR-AAAAAA", paciente["id"]))


def test_desvincular_revoga_o_acesso_e_da_pra_vincular_de_novo():
    fake = FakeSupabase()
    _ligar(fake)
    medico, _ = _medico(fake)
    paciente = _paciente(fake)
    _executar(medicos.vincular(paciente["id"], medico))

    assert _executar(medicos.paciente_autorizado(medico["id"], paciente["id"])) is not None
    assert _executar(medicos.desvincular(medico["id"], paciente["id"])) is True
    assert _executar(medicos.desvincular(medico["id"], paciente["id"])) is False
    assert _executar(medicos.paciente_autorizado(medico["id"], paciente["id"])) is None
    assert _executar(medicos.medicos_do_paciente(paciente["id"])) == []

    assert _executar(medicos.vincular(paciente["id"], medico)) is True  # reativa
    assert _executar(medicos.paciente_autorizado(medico["id"], paciente["id"])) is not None
    assert len(fake.store["medico_pacientes"]) == 1  # reaproveita a mesma linha


# --------------------------------------------------------------------------
# o que o médico enxerga (e o que NÃO)
# --------------------------------------------------------------------------

def test_medico_so_ve_paciente_vinculado_a_ele():
    fake = FakeSupabase()
    _ligar(fake)
    ana, _ = _medico(fake)
    beto, _ = _medico(fake, nome="Beto Lima", email="beto@clinica.com", ip="2.2.2.2")
    paciente = _paciente(fake)
    _executar(medicos.vincular(paciente["id"], ana))

    assert _executar(medico_api.paciente_do_medico(paciente["id"], ana))["id"] == paciente["id"]
    with pytest.raises(HTTPException) as erro:
        _executar(medico_api.paciente_do_medico(paciente["id"], beto))
    assert erro.value.status_code == 404  # 404, não 403: não confirma que o paciente existe
    assert _executar(medicos.pacientes_do_medico(beto["id"])) == []
    assert _executar(medicos.resumo_do_paciente(beto["id"], paciente["id"])) is None


def test_historico_do_paciente_via_medico_tem_os_mesmos_dados_do_paciente():
    fake = FakeSupabase()
    _ligar(fake)
    medico, _ = _medico(fake)
    paciente = _paciente(fake)
    _perfil(fake, paciente)
    _leitura(fake, paciente, 130)
    _executar(medicos.vincular(paciente["id"], medico))

    pelo_medico = _executar(medico_api.historico_paciente(dias=30, paciente=paciente))
    pelo_paciente = _executar(web_api.historico(dias=30, usuario=paciente))
    # (o "periodo" leva o carimbo do instante da consulta, que difere em microssegundos)
    for campo in ("perfil", "timezone", "glicemias", "bolus"):
        assert pelo_medico[campo] == pelo_paciente[campo]
    assert [g["valor"] for g in pelo_medico["glicemias"]] == [130]


def test_dados_do_paciente_nunca_expõem_telefone_nem_cpf():
    fake = FakeSupabase()
    _ligar(fake)
    medico, _ = _medico(fake)
    paciente = _paciente(fake, telefone="5545999990000@c.us")
    fake.table("usuarios").update({"cpf": "11144477735"}).eq("id", paciente["id"]).execute()
    _perfil(fake, paciente)
    _leitura(fake, paciente, 120)
    _executar(medicos.vincular(paciente["id"], medico))

    texto = str(_executar(medicos.pacientes_do_medico(medico["id"]))) + str(
        _executar(medico_api.resumo_paciente(paciente["id"], medico))
    )
    assert "5545999990000" not in texto and "11144477735" not in texto and "telefone" not in texto


def test_resumo_calcula_media_tempo_no_alvo_e_ultima_leitura():
    fake = FakeSupabase()
    _ligar(fake)
    medico, _ = _medico(fake)
    paciente = _paciente(fake)
    _perfil(fake, paciente)
    for valor, horas in [(100, 50), (60, 40), (200, 30), (120, 20), (250, 1)]:
        _leitura(fake, paciente, valor, horas)
    _leitura(fake, paciente, 999, horas_atras=24 * 30)  # fora da janela de 14 dias
    _executar(medicos.vincular(paciente["id"], medico))

    resumo = _executar(medicos.pacientes_do_medico(medico["id"]))[0]
    assert resumo["medicoes"] == 5
    assert resumo["media"] == 146
    assert resumo["na_faixa_pct"] == 40
    assert (resumo["hipoglicemias"], resumo["hiperglicemias"]) == (1, 2)
    assert resumo["ultima_glicemia"]["valor"] == 250
    assert resumo["ultima_fora_da_faixa"] is True


def test_resumo_de_paciente_sem_dados_nao_quebra():
    fake = FakeSupabase()
    _ligar(fake)
    medico, _ = _medico(fake)
    paciente = _paciente(fake, nome=None)
    _executar(medicos.vincular(paciente["id"], medico))

    resumo = _executar(medicos.pacientes_do_medico(medico["id"]))[0]
    assert resumo["ultima_glicemia"] is None and resumo["media"] is None and resumo["tem_perfil"] is False


# --------------------------------------------------------------------------
# rotas do paciente (site)
# --------------------------------------------------------------------------

def test_site_do_paciente_vincula_em_dois_passos():
    fake = FakeSupabase()
    _ligar(fake)
    medico, _ = _medico(fake)
    paciente = _paciente(fake)

    previa = _executar(web_api.vincular_medico_dashboard(
        web_api.VincularMedicoBody(codigo=medico["codigo_vinculo"]), usuario=paciente))
    assert previa["status"] == "confirmar" and previa["medico"]["crm"] == "123456"
    assert _executar(medicos.medicos_do_paciente(paciente["id"])) == []  # só olhar não libera nada

    ok = _executar(web_api.vincular_medico_dashboard(
        web_api.VincularMedicoBody(codigo=medico["codigo_vinculo"], confirmar=True), usuario=paciente))
    assert ok["status"] == "vinculado"
    assert len(_executar(web_api.listar_medicos_dashboard(usuario=paciente))["medicos"]) == 1

    _executar(web_api.remover_medico_dashboard(medico["id"], usuario=paciente))
    assert _executar(medicos.medicos_do_paciente(paciente["id"])) == []
    with pytest.raises(HTTPException) as erro:
        _executar(web_api.remover_medico_dashboard(medico["id"], usuario=paciente))
    assert erro.value.status_code == 404


def test_site_recusa_codigo_inexistente():
    fake = FakeSupabase()
    _ligar(fake)
    paciente = _paciente(fake)
    with pytest.raises(HTTPException) as erro:
        _executar(web_api.vincular_medico_dashboard(web_api.VincularMedicoBody(codigo="DR-ZZZZZZ"), usuario=paciente))
    assert erro.value.status_code == 400


# --------------------------------------------------------------------------
# WhatsApp
# --------------------------------------------------------------------------

def test_whatsapp_vincula_so_depois_do_sim():
    fake = FakeSupabase()
    _ligar(fake)
    medico, _ = _medico(fake)
    paciente = _paciente(fake)

    pergunta = _executar(comandos.processar_comando(paciente, f"medico {medico['codigo_vinculo']}"))
    assert "Ana Souza" in pergunta and "CRM 123456/SP" in pergunta and "sim" in pergunta
    assert _executar(medicos.medicos_do_paciente(paciente["id"])) == []  # ainda não liberou

    paciente = fake.table("usuarios").select("*").eq("id", paciente["id"]).execute().data[0]
    resposta = _executar(comandos.processar_comando(paciente, "sim"))
    assert "Vinculado" in resposta
    assert len(_executar(medicos.medicos_do_paciente(paciente["id"]))) == 1


def test_whatsapp_nao_vincula_se_responder_nao():
    fake = FakeSupabase()
    _ligar(fake)
    medico, _ = _medico(fake)
    paciente = _paciente(fake)

    _executar(comandos.processar_comando(paciente, f"medico {medico['codigo_vinculo']}"))
    paciente = fake.table("usuarios").select("*").eq("id", paciente["id"]).execute().data[0]
    _executar(comandos.processar_comando(paciente, "não"))
    assert _executar(medicos.medicos_do_paciente(paciente["id"])) == []


def test_whatsapp_listar_remover_e_codigo_errado():
    fake = FakeSupabase()
    _ligar(fake)
    medico, _ = _medico(fake)
    paciente = _paciente(fake)

    assert "ainda não vinculou" in _executar(comandos.processar_comando(paciente, "medico"))
    assert "Não encontrei" in _executar(comandos.processar_comando(paciente, "medico DR-AAAAAA"))

    _executar(medicos.vincular(paciente["id"], medico))
    assert "Ana Souza" in _executar(comandos.processar_comando(paciente, "medico listar"))
    assert "Não achei" in _executar(comandos.processar_comando(paciente, "medico remover zé"))

    assert "não vê mais" in _executar(comandos.processar_comando(paciente, "medico remover ana"))
    assert _executar(medicos.medicos_do_paciente(paciente["id"])) == []


def test_ia_nao_vincula_medico_sem_confirmacao():
    # frase em linguagem natural: a IA sugere o comando, mas vincular é ação sensível
    assert comandos._comando_e_seguro("medico listar") is True
    assert comandos._comando_e_seguro("medico") is True
    assert comandos._comando_e_seguro("medico DR-K7M2QX") is False
    assert comandos._comando_e_seguro("medico remover ana") is False
    assert "vincular seu médico" in comandos._descrever_comando("medico DR-K7M2QX")
