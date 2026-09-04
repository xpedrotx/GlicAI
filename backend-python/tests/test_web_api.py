import asyncio
import uuid
from datetime import datetime, timezone

from app.routes import web_api
from app.services import exportacao
from tests.fake_supabase import FakeSupabase


def _executar(coro):
    return asyncio.run(coro)


def test_historico_retorna_dados_estruturados():
    fake = FakeSupabase()
    exportacao.supabase = fake
    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert(
        {"id": usuario_id, "nome": "Pedro", "telefone": "123@lid", "timezone": "America/Sao_Paulo"}
    ).execute().data[0]
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario_id,
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()
    agora = datetime.now(timezone.utc)
    fake.table("registros_glicemia").insert(
        {"usuario_id": usuario_id, "valor": 110, "horario": agora.isoformat(), "contexto": "jejum"}
    ).execute()
    fake.table("registros_bolus").insert(
        {
            "usuario_id": usuario_id,
            "carboidratos_g": 40,
            "glicemia_referencia": 130,
            "dose_calculada": 4.0,
            "dose_aplicada": 4.0,
            "horario": agora.isoformat(),
        }
    ).execute()

    resultado = _executar(web_api.historico(dias=90, usuario=usuario))

    assert resultado["perfil"] == {"meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180}
    assert resultado["timezone"] == "America/Sao_Paulo"
    assert resultado["periodo"]["inicio"] is not None
    assert len(resultado["glicemias"]) == 1
    assert resultado["glicemias"][0]["valor"] == 110
    assert resultado["glicemias"][0]["contexto"] == "jejum"
    assert len(resultado["bolus"]) == 1
    assert resultado["bolus"][0]["dose_aplicada"] == 4.0
    assert resultado["bolus"][0]["carboidratos_g"] == 40


def test_historico_sem_perfil_retorna_listas_vazias():
    fake = FakeSupabase()
    exportacao.supabase = fake
    usuario = fake.table("usuarios").insert({"id": str(uuid.uuid4()), "nome": "Pedro"}).execute().data[0]

    resultado = _executar(web_api.historico(dias=90, usuario=usuario))

    assert resultado["perfil"] is None
    assert resultado["glicemias"] == []
    assert resultado["bolus"] == []


def test_historico_usa_timezone_padrao_quando_usuario_nao_configurou():
    fake = FakeSupabase()
    exportacao.supabase = fake
    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario_id,
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
        }
    ).execute()

    resultado = _executar(web_api.historico(dias=90, usuario=usuario))

    assert resultado["timezone"] == "America/Sao_Paulo"


# --------------------------------------------------------------------------
# perfil: GET (leitura completa) e PUT (edição de um campo por vez)
# --------------------------------------------------------------------------

def test_obter_perfil_retorna_dados_estruturados():
    fake = FakeSupabase()
    exportacao.supabase = fake
    from app.services import perfil as perfil_service
    perfil_service.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    fake.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario_id,
            "meta_glicemia": 120,
            "limite_baixo": 70,
            "limite_alto": 180,
            "fator_sensibilidade": 30,
            "tempo_insulina_ativa_horas": 4.0,
        }
    ).execute()
    fake.table("relacao_ic").insert(
        {"usuario_id": usuario_id, "periodo": "café", "hora_inicio": "06:00", "hora_fim": "10:00", "gramas_por_unidade": 15}
    ).execute()

    resultado = _executar(web_api.obter_perfil(usuario=usuario))

    assert resultado["nome"] == "Pedro"
    assert resultado["meta_glicemia"] == 120
    assert resultado["tempo_insulina_ativa_horas"] == 4.0
    assert len(resultado["relacoes_ic"]) == 1
    assert resultado["relacoes_ic"][0]["hora_inicio"] == "06:00"


def test_atualizar_perfil_campo_valido():
    fake = FakeSupabase()
    exportacao.supabase = fake
    from app.services import perfil as perfil_service
    perfil_service.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    fake.table("perfil_glicemico").insert(
        {"usuario_id": usuario_id, "meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180, "fator_sensibilidade": 30}
    ).execute()

    resultado = _executar(
        web_api.atualizar_perfil(web_api.AtualizarPerfilBody(campo="meta_glicemia", valor="110"), usuario=usuario)
    )

    assert resultado == {"status": "ok"}
    linha = fake.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data[0]
    assert linha["meta_glicemia"] == 110


def test_atualizar_perfil_campo_invalido_retorna_400():
    from fastapi import HTTPException

    fake = FakeSupabase()
    exportacao.supabase = fake
    from app.services import perfil as perfil_service
    perfil_service.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    fake.table("perfil_glicemico").insert(
        {"usuario_id": usuario_id, "meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180, "fator_sensibilidade": 30}
    ).execute()

    try:
        _executar(
            web_api.atualizar_perfil(web_api.AtualizarPerfilBody(campo="meta_glicemia", valor="500"), usuario=usuario)
        )
        assert False, "devia ter levantado HTTPException"
    except HTTPException as erro:
        assert erro.status_code == 400
        assert "300" in erro.detail


# --------------------------------------------------------------------------
# relatorio: mesmo dado do resumo periódico do WhatsApp, em JSON
# --------------------------------------------------------------------------

def test_relatorio_com_dados_calcula_estatisticas():
    fake = FakeSupabase()
    from app.services import relatorios
    relatorios.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    fake.table("perfil_glicemico").insert(
        {"usuario_id": usuario_id, "meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180, "fator_sensibilidade": 30}
    ).execute()
    agora = datetime.now(timezone.utc)
    for valor in (100, 110, 90, 200, 60, 130):
        fake.table("registros_glicemia").insert(
            {"usuario_id": usuario_id, "valor": valor, "horario": agora.isoformat()}
        ).execute()
    for dose in (4.0, 5.0, 3.5):
        fake.table("registros_bolus").insert(
            {"usuario_id": usuario_id, "dose_aplicada": dose, "horario": agora.isoformat()}
        ).execute()

    resultado = _executar(web_api.relatorio(periodo="semana", usuario=usuario))

    assert resultado["num_medicoes"] == 6
    assert resultado["hipoglicemias"] == 1
    assert resultado["hiperglicemias"] == 1
    assert resultado["doses_aplicadas"] == 3
    assert resultado["total_insulina"] == 12.5


def test_relatorio_periodo_invalido_retorna_400():
    from fastapi import HTTPException

    fake = FakeSupabase()
    from app.services import relatorios
    relatorios.supabase = fake
    usuario = fake.table("usuarios").insert({"id": str(uuid.uuid4()), "nome": "Pedro"}).execute().data[0]

    try:
        _executar(web_api.relatorio(periodo="ano", usuario=usuario))
        assert False, "devia ter levantado HTTPException"
    except HTTPException as erro:
        assert erro.status_code == 400


def test_relatorio_sem_perfil_retorna_perfil_none():
    fake = FakeSupabase()
    from app.services import relatorios
    relatorios.supabase = fake
    usuario = fake.table("usuarios").insert({"id": str(uuid.uuid4()), "nome": "Pedro"}).execute().data[0]

    resultado = _executar(web_api.relatorio(periodo="semana", usuario=usuario))
    assert resultado["perfil"] is None


# --------------------------------------------------------------------------
# hba1c: reaproveita hba1c.gerar_estimativa diretamente
# --------------------------------------------------------------------------

def test_hba1c_com_medicoes_suficientes():
    fake = FakeSupabase()
    from app.services import hba1c as hba1c_service
    hba1c_service.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    agora = datetime.now(timezone.utc)
    for valor in (100, 110, 120, 130, 140, 150):
        fake.table("registros_glicemia").insert(
            {"usuario_id": usuario_id, "valor": valor, "horario": agora.isoformat()}
        ).execute()

    resultado = _executar(web_api.hba1c_estimativa(dias=90, usuario=usuario))

    assert resultado["disponivel"] is True
    assert resultado["num_medicoes"] == 6


def test_hba1c_sem_medicoes_suficientes():
    fake = FakeSupabase()
    from app.services import hba1c as hba1c_service
    hba1c_service.supabase = fake
    usuario = fake.table("usuarios").insert({"id": str(uuid.uuid4()), "nome": "Pedro"}).execute().data[0]

    resultado = _executar(web_api.hba1c_estimativa(dias=90, usuario=usuario))

    assert resultado["disponivel"] is False


# --------------------------------------------------------------------------
# padroes: reaproveita padroes.detectar_padroes diretamente
# --------------------------------------------------------------------------

def test_padroes_detectados_traz_dia_semana_label():
    fake = FakeSupabase()
    from app.services import padroes as padroes_service
    padroes_service.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    fake.table("perfil_glicemico").insert(
        {"usuario_id": usuario_id, "meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180, "fator_sensibilidade": 30}
    ).execute()
    # terça-feira (weekday=1) de manhã, 3 medições altas
    from datetime import datetime as dt
    terca_manha = dt(2026, 8, 4, 8, 0, tzinfo=timezone.utc)  # 04/08/2026 é terça
    for _ in range(3):
        fake.table("registros_glicemia").insert(
            {"usuario_id": usuario_id, "valor": 220, "horario": terca_manha.isoformat()}
        ).execute()

    resultado = _executar(web_api.padroes_detectados(dias=60, usuario=usuario))

    assert len(resultado["padroes"]) == 1
    assert resultado["padroes"][0]["dia_semana_label"] == "terça-feira"
    assert resultado["padroes"][0]["tipo"] == "alta"


# --------------------------------------------------------------------------
# cuidadores: listar, gerar convite, remover
# --------------------------------------------------------------------------

def test_listar_cuidadores_dashboard():
    fake = FakeSupabase()
    from app.services import cuidadores as cuidadores_service
    cuidadores_service.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    fake.table("cuidadores").insert(
        {"usuario_id": usuario_id, "nome": "Maria", "telefone": "5511@c.us", "ativo": True}
    ).execute()

    resultado = _executar(web_api.listar_cuidadores_dashboard(usuario=usuario))
    assert resultado == {"cuidadores": [{"nome": "Maria"}]}


def test_gerar_convite_dashboard_retorna_codigo_estruturado():
    fake = FakeSupabase()
    from app.services import cuidadores as cuidadores_service
    cuidadores_service.supabase = fake
    usuario = fake.table("usuarios").insert({"id": str(uuid.uuid4()), "nome": "Pedro"}).execute().data[0]

    resultado = _executar(web_api.gerar_convite_dashboard(usuario=usuario))

    assert len(resultado["codigo"]) == 6
    assert resultado["minutos_validade"] == cuidadores_service.MINUTOS_VALIDADE_CONVITE


def test_remover_cuidador_dashboard_com_sucesso():
    fake = FakeSupabase()
    from app.services import cuidadores as cuidadores_service
    cuidadores_service.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    fake.table("cuidadores").insert(
        {"usuario_id": usuario_id, "nome": "Maria", "telefone": "5511@c.us", "ativo": True}
    ).execute()

    resultado = _executar(web_api.remover_cuidador_dashboard(nome="Maria", usuario=usuario))
    assert resultado == {"status": "ok"}

    linha = fake.table("cuidadores").select("*").eq("usuario_id", usuario_id).execute().data[0]
    assert linha["ativo"] is False


def test_remover_cuidador_dashboard_nao_encontrado_retorna_404():
    from fastapi import HTTPException

    fake = FakeSupabase()
    from app.services import cuidadores as cuidadores_service
    cuidadores_service.supabase = fake
    usuario = fake.table("usuarios").insert({"id": str(uuid.uuid4()), "nome": "Pedro"}).execute().data[0]

    try:
        _executar(web_api.remover_cuidador_dashboard(nome="Ninguem", usuario=usuario))
        assert False, "devia ter levantado HTTPException"
    except HTTPException as erro:
        assert erro.status_code == 404


# --------------------------------------------------------------------------
# estoque: listar, configurar, reabastecer
# --------------------------------------------------------------------------

def test_listar_estoque_dashboard():
    fake = FakeSupabase()
    from app.services import estoque as estoque_service
    estoque_service.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    _executar(estoque_service.configurar(usuario_id, "insulina", 300, 60))

    resultado = _executar(web_api.listar_estoque_dashboard(usuario=usuario))

    assert len(resultado["itens"]) == 1
    assert resultado["itens"][0]["label"] == "Insulina"
    assert resultado["itens"][0]["quantidade_atual"] == 300


def test_configurar_estoque_dashboard_com_limite_padrao():
    fake = FakeSupabase()
    from app.services import estoque as estoque_service
    estoque_service.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]

    resultado = _executar(
        web_api.configurar_estoque_dashboard(
            web_api.ConfigurarEstoqueBody(tipo="fita", quantidade_por_reposicao=50, limite_alerta=None),
            usuario=usuario,
        )
    )
    assert resultado == {"status": "ok"}

    linha = _executar(estoque_service.buscar(usuario_id, "fita_dextro"))
    assert linha["quantidade_atual"] == 50
    assert linha["limite_alerta"] == 10  # 20% padrão


def test_configurar_estoque_dashboard_tipo_invalido_retorna_400():
    from fastapi import HTTPException

    fake = FakeSupabase()
    from app.services import estoque as estoque_service
    estoque_service.supabase = fake
    usuario = fake.table("usuarios").insert({"id": str(uuid.uuid4()), "nome": "Pedro"}).execute().data[0]

    try:
        _executar(
            web_api.configurar_estoque_dashboard(
                web_api.ConfigurarEstoqueBody(tipo="xyz", quantidade_por_reposicao=50, limite_alerta=None),
                usuario=usuario,
            )
        )
        assert False, "devia ter levantado HTTPException"
    except HTTPException as erro:
        assert erro.status_code == 400


def test_reabastecer_estoque_dashboard():
    fake = FakeSupabase()
    from app.services import estoque as estoque_service
    estoque_service.supabase = fake

    usuario_id = str(uuid.uuid4())
    usuario = fake.table("usuarios").insert({"id": usuario_id, "nome": "Pedro"}).execute().data[0]
    _executar(estoque_service.configurar(usuario_id, "insulina", 300, 60))
    _executar(estoque_service.consumir(usuario_id, "insulina", 250))

    resultado = _executar(
        web_api.reabastecer_estoque_dashboard(
            web_api.ReabastecerEstoqueBody(tipo="insulina", quantidade=300), usuario=usuario
        )
    )
    assert resultado == {"status": "ok"}

    linha = _executar(estoque_service.buscar(usuario_id, "insulina"))
    assert linha["quantidade_atual"] == 300


def test_reabastecer_estoque_dashboard_nao_configurado_retorna_404():
    from fastapi import HTTPException

    fake = FakeSupabase()
    from app.services import estoque as estoque_service
    estoque_service.supabase = fake
    usuario = fake.table("usuarios").insert({"id": str(uuid.uuid4()), "nome": "Pedro"}).execute().data[0]

    try:
        _executar(
            web_api.reabastecer_estoque_dashboard(
                web_api.ReabastecerEstoqueBody(tipo="insulina", quantidade=300), usuario=usuario
            )
        )
        assert False, "devia ter levantado HTTPException"
    except HTTPException as erro:
        assert erro.status_code == 404
