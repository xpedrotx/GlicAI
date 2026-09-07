import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from app.services import alertas, auth_web, bolus, comandos, confirmacoes, estoque, remedicao
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def _criar_usuario(fake: FakeSupabase, **overrides) -> dict:
    usuario = {
        "id": str(uuid.uuid4()),
        "telefone": "5545999999999@c.us",
        "nome": "Pedro",
        "status_cadastro": "completo",
    }
    usuario.update(overrides)
    return fake.table("usuarios").insert(usuario).execute().data[0]


# --------------------------------------------------------------------------
# editar: aliases com espaço ("limite baixo" / "limite alto")
# --------------------------------------------------------------------------

def test_editar_aceita_limite_baixo_com_espaco():
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    resposta = _executar(comandos.processar_comando(usuario, "editar limite baixo 65"))

    assert "limite baixo" in resposta
    assert "65" in resposta
    perfil = fake.table("perfil_glicemico").select("*").eq("usuario_id", usuario["id"]).execute().data[0]
    assert perfil["limite_baixo"] == 65


def test_editar_campo_nao_reconhecido():
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(fake)

    resposta = _executar(comandos.processar_comando(usuario, "editar xyz 10"))
    assert "não reconhecido" in resposta.lower()


# --------------------------------------------------------------------------
# tempo insulina ativa: alias com espaço
# --------------------------------------------------------------------------

def test_tempo_insulina_ativa_aceita_forma_com_espaco():
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {"usuario_id": usuario["id"], "meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180}
    ).execute()

    resposta = _executar(comandos.processar_comando(usuario, "tempo insulina ativa 4"))
    assert "4.0h" in resposta

    perfil = fake.table("perfil_glicemico").select("*").eq("usuario_id", usuario["id"]).execute().data[0]
    assert perfil["tempo_insulina_ativa_horas"] == 4.0


# --------------------------------------------------------------------------
# fallback de IA: sugestão + confirmação
# --------------------------------------------------------------------------

def test_comando_nao_reconhecido_sem_ia_configurada_pede_ajuda():
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(fake)

    with patch.object(comandos.ia, "sugerir_comando", new=AsyncMock(return_value=None)):
        resposta = _executar(comandos.processar_comando(usuario, "blablabla comando estranho"))

    assert "Não entendi" in resposta


def test_fallback_ia_comando_seguro_executa_direto_sem_confirmar():
    """Comando só de leitura (ex: 'ajuda') a IA já executa na hora — errar
    aqui não tem custo real, então não precisa perguntar sim/não."""
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(fake)

    sugestao = AsyncMock(return_value={"comando": "ajuda", "confianca": "alta"})
    with patch.object(comandos.ia, "sugerir_comando", new=sugestao):
        resposta = _executar(comandos.processar_comando(usuario, "me ajuda por favor"))

    assert "Aqui está tudo o que eu sei fazer" in resposta
    linha = fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data[0]
    assert linha.get("sugestao_pendente") is None


def test_fallback_ia_comando_critico_pede_confirmacao_com_frase_humana():
    """Comando que grava dado clínico (ex: 'apliquei') continua pedindo
    confirmação — e a frase mostrada é em português normal, não o comando
    técnico cru."""
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(fake)

    sugestao = AsyncMock(return_value={"comando": "apliquei 4.5", "confianca": "alta"})
    with patch.object(comandos.ia, "sugerir_comando", new=sugestao):
        resposta = _executar(comandos.processar_comando(usuario, "acabei de tomar 4.5 unidades"))

    assert "apliquei 4.5" not in resposta  # nunca mostra o comando técnico cru
    assert "aplicou 4.5" in resposta.lower()
    assert "sim" in resposta.lower() and "não" in resposta.lower()

    linha = fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data[0]
    assert linha["sugestao_pendente"]["comando"] == "apliquei 4.5"


def test_confirmar_sugestao_com_sim_executa_o_comando():
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(
        fake,
        sugestao_pendente={
            "comando": "ajuda",
            "criado_em": datetime.now(timezone.utc).isoformat(),
        },
    )

    resposta = _executar(comandos.processar_comando(usuario, "sim"))

    assert "Aqui está tudo o que eu sei fazer" in resposta
    # sugestão consumida — some do banco
    linha = fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data[0]
    assert linha["sugestao_pendente"] is None


def test_recusar_sugestao_com_nao_cancela():
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(
        fake,
        sugestao_pendente={
            "comando": "apliquei 100",
            "criado_em": datetime.now(timezone.utc).isoformat(),
        },
    )

    resposta = _executar(comandos.processar_comando(usuario, "não"))

    assert "deixa pra lá" in resposta.lower()
    linha = fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data[0]
    assert linha["sugestao_pendente"] is None


# --------------------------------------------------------------------------
# glicemia: cuidadores só são avisados na hora quando NÃO precisa de ação do
# paciente (dose 0 / leitura normal). Quando precisa (correção ou hipo),
# fica pendente de confirmação e o aviso só sai no *apliquei*/*tratei* ou no
# escalonamento — não mais na hora, junto com o resultado.
# --------------------------------------------------------------------------

def _ligar_supabase_glicemia(fake: FakeSupabase):
    comandos.supabase = fake
    alertas.supabase = fake
    bolus.supabase = fake
    confirmacoes.supabase = fake
    estoque.supabase = fake
    remedicao.supabase = fake


def _mockar_dicas_ia():
    """
    Evita que os testes de glicemia hiper/hipo cheguem a chamar a API real
    da IA (ia.gerar_dicas) — sem isso, cada teste desses ficava
    lento (~2s) e dependente de rede/chave configurada no .env local.
    """
    return patch.object(comandos.ia, "gerar_dicas", new=AsyncMock(return_value=["Beba água", "Descanse um pouco"]))


# --------------------------------------------------------------------------
# glicemia hiper/hipo: cartão de alerta bonito com dicas geradas por IA
# --------------------------------------------------------------------------

def test_glicemia_hiperglicemia_mostra_cartao_com_dicas_na_primeira_leitura():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    dicas_mock = AsyncMock(return_value=["Beba bastante água", "Evite exercícios intensos"])
    with patch.object(comandos.ia, "gerar_dicas", new=dicas_mock), patch.object(
        comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()
    ):
        resposta = _executar(comandos.processar_comando(usuario, "glicemia 201"))

    assert "Glicemia alta! Ação necessária" in resposta
    assert "• Beba bastante água" in resposta
    assert "• Evite exercícios intensos" in resposta
    assert "apliquei" in resposta.lower()
    dicas_mock.assert_awaited_once_with("hiperglicemia", 201)


def test_glicemia_hiperglicemia_repetida_na_janela_de_throttle_nao_repete_cartao():
    """
    Duas leituras altas em menos de 15 min: a primeira mostra o cartão
    completo com dicas de IA; a segunda (dentro da janela de throttle de
    alertas.py) não deve chamar a IA de novo nem repetir o cartão — só o
    texto simples de sempre.
    """
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    dicas_mock = AsyncMock(return_value=["Beba água"])
    with patch.object(comandos.ia, "gerar_dicas", new=dicas_mock), patch.object(
        comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()
    ):
        _executar(comandos.processar_comando(usuario, "glicemia 201"))
        resposta2 = _executar(comandos.processar_comando(usuario, "glicemia 205"))

    assert "Glicemia alta! Ação necessária" not in resposta2
    assert "apliquei" in resposta2.lower()
    dicas_mock.assert_awaited_once()  # só a primeira leitura chamou a IA


def test_glicemia_hipoglicemia_mostra_cartao_com_dicas_na_primeira_leitura():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    dicas_mock = AsyncMock(return_value=["Evite exercícios até estabilizar", "Meça de novo em 15 min"])
    with patch.object(comandos.ia, "gerar_dicas", new=dicas_mock), patch.object(
        comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()
    ):
        resposta = _executar(comandos.processar_comando(usuario, "glicemia 55"))

    assert "Glicemia baixa! Ação necessária" in resposta
    assert "abaixo do seu limite de 70 mg/dL" in resposta
    assert "• Evite exercícios até estabilizar" in resposta
    assert "não aplique insulina" in resposta.lower()
    assert "meça de novo em 15 minutos" in resposta.lower()
    assert "tratei" in resposta.lower()
    dicas_mock.assert_awaited_once_with("hipoglicemia", 55.0)

    lembretes = fake.table("lembretes_remedicao").select("*").eq("usuario_id", usuario["id"]).execute().data
    assert len(lembretes) == 1


# --------------------------------------------------------------------------
# glicemia/bolus: emergência de hipoglicemia grave (< LIMITE_EMERGENCIA_BAIXO)
# — mesma urgência já existente pro lado alto (> LIMITE_EMERGENCIA), mas
# pro lado baixo, que é tão ou mais perigoso.
# --------------------------------------------------------------------------

def test_glicemia_hipoglicemia_grave_dispara_emergencia_e_avisa_cuidadores_na_hora():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        resposta = _executar(comandos.processar_comando(usuario, "glicemia 40"))

    assert "emergência" in resposta.lower()
    assert "hipoglicemia grave" in resposta.lower()
    assert "192" in resposta  # SAMU
    mock_notificar.assert_awaited_once()
    assert "40" in mock_notificar.await_args.args[1]

    registros = fake.table("registros_glicemia").select("*").eq("usuario_id", usuario["id"]).execute().data
    assert len(registros) == 1
    assert registros[0]["valor"] == 40


def test_glicemia_hipoglicemia_nao_grave_nao_dispara_emergencia():
    """55 mg/dL é hipoglicemia, mas não grave o suficiente (acima de
    LIMITE_EMERGENCIA_BAIXO) — continua o fluxo normal de hipo, sem
    emergência nem aviso imediato aos cuidadores."""
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    with _mockar_dicas_ia(), patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        resposta = _executar(comandos.processar_comando(usuario, "glicemia 55"))

    assert "emergência" not in resposta.lower()
    mock_notificar.assert_not_awaited()


def test_bolus_com_glicemia_hipoglicemia_grave_dispara_emergencia():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        resposta = _executar(comandos.processar_comando(usuario, "bolus 40g 30"))

    assert "emergência" in resposta.lower()
    assert "hipoglicemia grave" in resposta.lower()
    mock_notificar.assert_awaited_once()


def test_glicemia_hiperglicemia_extrema_ainda_dispara_emergencia_do_lado_alto():
    """Confirma que a emergência pré-existente do lado alto (LIMITE_EMERGENCIA)
    continua funcionando junto com a nova do lado baixo."""
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        resposta = _executar(comandos.processar_comando(usuario, "glicemia 650"))

    assert "emergência" in resposta.lower()
    assert "hipoglicemia" not in resposta.lower()
    mock_notificar.assert_awaited_once()


def test_glicemia_com_correcao_pendente_nao_avisa_cuidadores_na_hora():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    with _mockar_dicas_ia(), patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        resposta = _executar(comandos.processar_comando(usuario, "glicemia 201"))

    assert "apliquei" in resposta.lower()
    mock_notificar.assert_not_awaited()

    pendencias = fake.table("confirmacoes_glicemia").select("*").eq("usuario_id", usuario["id"]).execute().data
    assert len(pendencias) == 1
    assert pendencias[0]["tipo"] == "hiperglicemia"
    assert pendencias[0]["confirmado_em"] is None


def test_glicemia_hipoglicemia_nao_avisa_cuidadores_na_hora():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    with _mockar_dicas_ia(), patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        resposta = _executar(comandos.processar_comando(usuario, "glicemia 55"))

    assert "tratei" in resposta.lower()
    mock_notificar.assert_not_awaited()


def test_glicemia_sem_necessidade_de_correcao_avisa_cuidadores_na_hora():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        # 121 é só 1 acima da meta -> (121-120)/30 = 0.03 -> arredonda pra 0
        _executar(comandos.processar_comando(usuario, "glicemia 121"))

    mock_notificar.assert_awaited_once()
    texto = mock_notificar.await_args.args[1]
    assert "121" in texto

    pendencias = fake.table("confirmacoes_glicemia").select("*").eq("usuario_id", usuario["id"]).execute().data
    assert len(pendencias) == 0


def test_apliquei_notifica_cuidadores_da_dose_confirmada_apos_glicemia_pendente():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    with _mockar_dicas_ia(), patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()):
        _executar(comandos.processar_comando(usuario, "glicemia 201"))

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        _executar(comandos.processar_comando(usuario, "apliquei 2"))

    mock_notificar.assert_awaited_once()
    texto = mock_notificar.await_args.args[1]
    assert "aplicou" in texto.lower()

    pendencia = fake.table("confirmacoes_glicemia").select("*").eq("usuario_id", usuario["id"]).execute().data[0]
    assert pendencia["confirmado_em"] is not None


# --------------------------------------------------------------------------
# apliquei/tratei: cartão estruturado com horário local (pro paciente e
# pros cuidadores), pedido explícito do usuário depois de ver a versão
# antiga simples demais.
# --------------------------------------------------------------------------

def test_apliquei_mostra_cartao_com_horario_glicemia_e_insulina_ativa():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake, timezone="America/Sao_Paulo")
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
            "tempo_insulina_ativa_horas": 4.0,
        }
    ).execute()

    with _mockar_dicas_ia(), patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()):
        _executar(comandos.processar_comando(usuario, "glicemia 201"))

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        resposta = _executar(comandos.processar_comando(usuario, "apliquei 2"))

    assert "Dose aplicada" in resposta
    assert "🕐" in resposta
    assert "*2.0U*" in resposta
    assert "Referente à glicemia de *201 mg/dL*" in resposta
    assert "Insulina ativa" in resposta

    texto_cuidador = mock_notificar.await_args.args[1]
    assert "aplicou insulina" in texto_cuidador.lower()
    assert "🕐" in texto_cuidador
    assert "*2.0U*" in texto_cuidador
    assert "Referente à glicemia de *201 mg/dL*" in texto_cuidador


def test_apliquei_avulso_sem_glicemia_de_referencia_omite_a_linha():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        resposta = _executar(comandos.processar_comando(usuario, "apliquei 3"))

    assert "Referente à glicemia" not in resposta
    texto_cuidador = mock_notificar.await_args.args[1]
    assert "Referente à glicemia" not in texto_cuidador


# --------------------------------------------------------------------------
# apliquei retroativo: "esqueci de registrar, tomei 6u às 12:20" — pedido
# real do usuário, pra IOB decair a partir do horário real, não de agora.
# --------------------------------------------------------------------------

_AGORA_LOCAL_TESTE = datetime(2026, 8, 7, 13, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_apliquei_retroativo_registra_horario_passado_e_marca_retroativa():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake, timezone="America/Sao_Paulo")

    with patch.object(comandos, "agora_usuario", return_value=_AGORA_LOCAL_TESTE), patch.object(
        comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()
    ) as mock_notificar:
        resposta = _executar(comandos.processar_comando(usuario, "apliquei 6 12:20"))

    assert "retroativa" in resposta.lower()
    assert "🕐 12:20" in resposta
    assert "*6.0U*" in resposta

    texto_cuidador = mock_notificar.await_args.args[1]
    assert "retroativa" in texto_cuidador.lower()
    assert "12:20" in texto_cuidador

    registro = fake.table("registros_bolus").select("*").eq("usuario_id", usuario["id"]).execute().data[0]
    esperado = _AGORA_LOCAL_TESTE.replace(hour=12, minute=20, second=0, microsecond=0)
    assert registro["horario_aplicacao"] == esperado.astimezone(timezone.utc).isoformat()


def test_apliquei_retroativo_aceita_conector_as():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake, timezone="America/Sao_Paulo")

    with patch.object(comandos, "agora_usuario", return_value=_AGORA_LOCAL_TESTE), patch.object(
        comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()
    ):
        resposta = _executar(comandos.processar_comando(usuario, "apliquei 6 as 12:20"))

    assert "🕐 12:20" in resposta


def test_apliquei_horario_futuro_e_rejeitado():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake, timezone="America/Sao_Paulo")

    with patch.object(comandos, "agora_usuario", return_value=_AGORA_LOCAL_TESTE):
        resposta = _executar(comandos.processar_comando(usuario, "apliquei 6 14:00"))

    assert "ainda não chegou" in resposta.lower()
    assert fake.store.get("registros_bolus", []) == []


def test_apliquei_horario_invalido_pede_formato():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)

    resposta = _executar(comandos.processar_comando(usuario, "apliquei 6 25:99"))

    assert "hh:mm" in resposta.lower() or "horário" in resposta.lower()
    assert fake.store.get("registros_bolus", []) == []


def test_tratei_mostra_cartao_com_horario_e_valor():
    fake = FakeSupabase()
    _ligar_supabase_glicemia(fake)
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    with _mockar_dicas_ia(), patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()):
        _executar(comandos.processar_comando(usuario, "glicemia 55"))

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()) as mock_notificar:
        resposta = _executar(comandos.processar_comando(usuario, "tratei"))

    assert "Hipoglicemia tratada" in resposta
    assert "🕐" in resposta
    assert "Estava em *55 mg/dL*" in resposta

    texto_cuidador = mock_notificar.await_args.args[1]
    assert "tratou a hipoglicemia" in texto_cuidador.lower()
    assert "Estava em *55 mg/dL*" in texto_cuidador


def test_sugestao_expirada_nao_e_confirmada():
    fake = FakeSupabase()
    comandos.supabase = fake
    criado_em_antigo = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    usuario = _criar_usuario(
        fake,
        sugestao_pendente={"comando": "apliquei 100", "criado_em": criado_em_antigo},
    )

    # "sim" chega tarde demais — não deve rodar o "apliquei 100" antigo.
    # Como "sim" também não é um comando válido, cai no fallback de IA de novo.
    with patch.object(comandos.ia, "sugerir_comando", new=AsyncMock(return_value=None)):
        resposta = _executar(comandos.processar_comando(usuario, "sim"))

    assert "Não entendi" in resposta
    linha = fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data[0]
    assert linha["sugestao_pendente"] is None


# --------------------------------------------------------------------------
# estoque: comando + desconto automático em apliquei/glicemia
# --------------------------------------------------------------------------

def test_estoque_sem_configuracao_orienta_como_configurar():
    fake = FakeSupabase()
    comandos.supabase = fake
    estoque.supabase = fake
    usuario = _criar_usuario(fake)

    resposta = _executar(comandos.processar_comando(usuario, "estoque"))
    assert "configurar" in resposta.lower()


def test_estoque_configurar_com_alias_fita():
    fake = FakeSupabase()
    comandos.supabase = fake
    estoque.supabase = fake
    usuario = _criar_usuario(fake)

    resposta = _executar(comandos.processar_comando(usuario, "estoque configurar fita 50"))
    assert "Fitas de dextro" in resposta
    assert "50" in resposta

    linha = _executar(estoque.buscar(usuario["id"], "fita_dextro"))
    assert linha["quantidade_atual"] == 50
    assert linha["limite_alerta"] == 10  # 20% padrão


def test_estoque_listar_mostra_niveis_configurados():
    fake = FakeSupabase()
    comandos.supabase = fake
    estoque.supabase = fake
    usuario = _criar_usuario(fake)

    _executar(comandos.processar_comando(usuario, "estoque configurar insulina 300 60"))
    resposta = _executar(comandos.processar_comando(usuario, "estoque"))

    assert "Insulina" in resposta
    assert "300" in resposta


def test_apliquei_desconta_estoque_de_insulina_e_avisa_quando_baixo():
    fake = FakeSupabase()
    comandos.supabase = fake
    bolus.supabase = fake
    confirmacoes.supabase = fake
    estoque.supabase = fake
    usuario = _criar_usuario(fake)

    _executar(estoque.configurar(usuario["id"], "insulina", 10, 8))

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()):
        resposta = _executar(comandos.processar_comando(usuario, "apliquei 4"))

    assert "estoque de insulina baixo" in resposta.lower()
    linha = _executar(estoque.buscar(usuario["id"], "insulina"))
    assert linha["quantidade_atual"] == 6


def test_glicemia_desconta_fita_dextro():
    fake = FakeSupabase()
    comandos.supabase = fake
    alertas.supabase = fake
    bolus.supabase = fake
    confirmacoes.supabase = fake
    estoque.supabase = fake
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario["id"],
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()
    _executar(estoque.configurar(usuario["id"], "fita_dextro", 5, 4))

    with patch.object(comandos.cuidadores, "notificar_cuidadores", new=AsyncMock()):
        _executar(comandos.processar_comando(usuario, "glicemia 100"))

    linha = _executar(estoque.buscar(usuario["id"], "fita_dextro"))
    assert linha["quantidade_atual"] == 4


# --------------------------------------------------------------------------
# criar senha: comando iniciado pelo WhatsApp (não pelo site) — ver
# auth_web.py pra entender por que (JIDs @lid não têm relação com o
# telefone real, então o site não pode "adivinhar" a conta a partir de um
# número digitado).
# --------------------------------------------------------------------------

def test_criar_senha_gera_codigo_via_comando():
    fake = FakeSupabase()
    comandos.supabase = fake
    auth_web.supabase = fake
    usuario = _criar_usuario(fake, telefone="235299934343350@lid")

    resposta = _executar(comandos.processar_comando(usuario, "criar senha"))

    assert "Código de acesso ao site" in resposta
    codigos = fake.table("codigos_login_web").select("*").eq("usuario_id", usuario["id"]).execute().data
    assert len(codigos) == 1
    assert codigos[0]["codigo"] in resposta


# --------------------------------------------------------------------------
# excluir conta: direito de eliminação (LGPD) — exige confirmação explícita
# separada, igual ao fluxo de sugestão da IA (sim/não).
# --------------------------------------------------------------------------

def test_excluir_conta_pede_confirmacao_e_nao_apaga_ainda():
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(fake)

    resposta = _executar(comandos.processar_comando(usuario, "excluir conta"))

    assert "apaga permanentemente" in resposta.lower()
    assert "sim" in resposta.lower() and "não" in resposta.lower()
    linha = fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data[0]
    assert linha["sugestao_pendente"]["comando"] == "confirmar_exclusao_conta"


def test_excluir_conta_confirmado_com_sim_apaga_tudo():
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(fake)
    fake.table("perfil_glicemico").insert({"usuario_id": usuario["id"], "meta_glicemia": 120}).execute()
    fake.table("registros_glicemia").insert({"usuario_id": usuario["id"], "valor": 110}).execute()

    _executar(comandos.processar_comando(usuario, "excluir conta"))
    usuario_atualizado = fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data[0]
    resposta = _executar(comandos.processar_comando(usuario_atualizado, "sim"))

    assert "apagados" in resposta.lower()
    assert fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data == []
    # FakeSupabase não simula ON DELETE CASCADE — o que importa aqui é que
    # a linha em "usuarios" (a fonte de verdade) some; no Postgres real, a
    # cascata cuida do resto (ver comentário em _excluir_conta).


def test_excluir_conta_recusado_com_nao_mantem_dados():
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(fake)

    _executar(comandos.processar_comando(usuario, "excluir conta"))
    usuario_atualizado = fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data[0]
    resposta = _executar(comandos.processar_comando(usuario_atualizado, "não"))

    assert "deixa pra lá" in resposta.lower()
    assert fake.table("usuarios").select("*").eq("id", usuario["id"]).execute().data != []


def test_apagar_meus_dados_e_alias_de_excluir_conta():
    fake = FakeSupabase()
    comandos.supabase = fake
    usuario = _criar_usuario(fake)

    resposta = _executar(comandos.processar_comando(usuario, "apagar meus dados"))

    assert "apaga permanentemente" in resposta.lower()


# --------------------------------------------------------------------------
# classificação seguro/crítico e descrição em português dos comandos que a
# IA sugere — o paciente nunca deveria ver o token técnico cru.
# --------------------------------------------------------------------------

def test_comando_e_seguro_classifica_leitura_como_seguro():
    for comando in ("ajuda", "oi", "perfil", "basal", "relatorio semana", "exportar", "hba1c", "padroes", "criar_senha"):
        assert comandos._comando_e_seguro(comando), f"{comando!r} devia ser seguro"


def test_comando_e_seguro_classifica_escrita_como_critico():
    for comando in (
        "glicemia 110", "bolus 40 130", "apliquei 4", "tratei", "editar meta 110",
        "modificador ativar exercicio", "tempo_insulina_ativa 4", "excluir_conta",
        "confirmar_exclusao_conta",
    ):
        assert not comandos._comando_e_seguro(comando), f"{comando!r} devia ser crítico"


def test_comando_e_seguro_diferencia_subacao_de_leitura_e_escrita():
    assert comandos._comando_e_seguro("cuidador listar")
    assert not comandos._comando_e_seguro("cuidador convidar")
    assert not comandos._comando_e_seguro("cuidador remover Maria")
    assert comandos._comando_e_seguro("lembrete listar")
    assert not comandos._comando_e_seguro("lembrete adicionar 08:00")
    assert comandos._comando_e_seguro("estoque")
    assert not comandos._comando_e_seguro("estoque configurar insulina 300")


def test_descrever_comando_traduz_pra_portugues_sem_underscore():
    assert "_" not in comandos._descrever_comando("tempo_insulina_ativa 4")
    assert "4 horas" in comandos._descrever_comando("tempo_insulina_ativa 4")
    assert "40" in comandos._descrever_comando("bolus 40 130") and "130" in comandos._descrever_comando("bolus 40 130")
    assert "4.5" in comandos._descrever_comando("apliquei 4.5")
