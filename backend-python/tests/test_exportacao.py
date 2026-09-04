from datetime import datetime, timedelta, timezone

from app.services.exportacao import (
    AREIA_ZEBRA,
    PETROLEO,
    VERDE,
    VERMELHO,
    _cor_e_seta_glicemia,
    _formatar_contexto,
    _formatar_horario,
    _montar_pdf,
)


def test_formatar_contexto_outro_vira_traco():
    assert _formatar_contexto("outro") == "-"


def test_formatar_contexto_nenhum_vira_traco():
    assert _formatar_contexto(None) == "-"


def test_formatar_contexto_reconhecido_mostra_label():
    assert _formatar_contexto("jejum") == "Em jejum"
    assert _formatar_contexto("pre_refeicao") == "Antes da refeição"
    assert _formatar_contexto("pos_prandial") == "Depois da refeição"
    assert _formatar_contexto("correcao") == "Correção"


def test_formatar_horario_converte_de_utc_pro_fuso_local():
    """
    Reproduz o bug real relatado: horario vem do banco em UTC; sem converter
    pro fuso do paciente, a hora exibida ficava 3h à frente da hora real
    (America/Sao_Paulo é UTC-3, sem horário de verão).
    """
    # 05/08 17:03 UTC == 05/08 14:03 em São Paulo
    assert _formatar_horario("2026-08-05T17:03:00+00:00", "America/Sao_Paulo") == "05/08 14:03"
    # Também cobre virada de dia: 05/08 01:15 UTC == 04/08 22:15 em São Paulo
    assert _formatar_horario("2026-08-05T01:15:00+00:00", "America/Sao_Paulo") == "04/08 22:15"


def test_cor_e_seta_glicemia_quatro_faixas():
    # abaixo do limite baixo -> vermelho + seta pra baixo
    assert _cor_e_seta_glicemia(69, limite_baixo=70, meta=120, limite_alto=180) == (VERMELHO, "↓")
    # exatamente no limite baixo -> ainda dentro (verde), sem seta
    assert _cor_e_seta_glicemia(70, limite_baixo=70, meta=120, limite_alto=180) == (VERDE, "")
    # entre o limite baixo e a meta -> verde, sem seta
    assert _cor_e_seta_glicemia(100, limite_baixo=70, meta=120, limite_alto=180) == (VERDE, "")
    # na meta em diante (até o limite alto) -> preto/petróleo, sem seta
    assert _cor_e_seta_glicemia(120, limite_baixo=70, meta=120, limite_alto=180) == (PETROLEO, "")
    assert _cor_e_seta_glicemia(150, limite_baixo=70, meta=120, limite_alto=180) == (PETROLEO, "")
    assert _cor_e_seta_glicemia(180, limite_baixo=70, meta=120, limite_alto=180) == (PETROLEO, "")
    # acima do limite alto -> vermelho + seta pra cima
    assert _cor_e_seta_glicemia(181, limite_baixo=70, meta=120, limite_alto=180) == (VERMELHO, "↑")


def test_montar_pdf_com_grafico_gera_documento_valido():
    """
    Fumaça: com >= 2 medições o gráfico de tendência é desenhado antes da
    tabela — reproduz o cenário do bug real em que a cor de preenchimento
    deixada pelos círculos do gráfico "vazava" pro fundo das linhas da
    tabela seguinte. Não valida cor por cor (exigiria parsear o content
    stream do PDF), mas garante que a montagem inteira roda sem erro.
    """
    agora = datetime.now(timezone.utc)
    inicio = agora - timedelta(days=7)
    perfil = {
        "meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180,
        "fator_sensibilidade": 30, "tempo_insulina_ativa_horas": 4.0,
    }
    glicemias = [
        {"horario": (inicio + timedelta(hours=i * 6)).isoformat(), "valor": v, "contexto": "outro"}
        for i, v in enumerate([90, 205, 65, 130, 190])
    ]

    pdf_bytes = _montar_pdf("Paciente Teste", inicio, agora, perfil, glicemias, [], "America/Sao_Paulo")

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_montar_pdf_sem_medicao_suficiente_pula_grafico():
    """Com 0 ou 1 medição não tem "tendência" pra mostrar — a montagem não
    deve quebrar, só pula o gráfico."""
    agora = datetime.now(timezone.utc)
    inicio = agora - timedelta(days=7)
    perfil = {"meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180, "fator_sensibilidade": 30}

    pdf_bytes = _montar_pdf("Paciente Teste", inicio, agora, perfil, [], [], "America/Sao_Paulo")
    assert pdf_bytes.startswith(b"%PDF")

    glicemias = [{"horario": agora.isoformat(), "valor": 110, "contexto": "outro"}]
    pdf_bytes_um_ponto = _montar_pdf("Paciente Teste", inicio, agora, perfil, glicemias, [], "America/Sao_Paulo")
    assert pdf_bytes_um_ponto.startswith(b"%PDF")


def test_fill_color_e_resetado_antes_das_tabelas():
    """
    Reproduz literalmente o bug: depois de desenhar o gráfico (que mexe na
    cor de preenchimento pros círculos), a cor ambiente precisa estar de
    volta em AREIA_ZEBRA antes de qualquer tabela ser desenhada — checando
    o estado do objeto pdf via fpdf2 (fill_color), não só que não quebrou.
    """
    from app.services.exportacao import _GlicAIPDF, _desenhar_grafico_tendencia

    perfil = {"meta_glicemia": 120, "limite_baixo": 70, "limite_alto": 180}
    agora = datetime.now(timezone.utc)
    # ordem cronológica (a função ordena por horário): 205 -> 90 -> 65, então
    # o ÚLTIMO círculo desenhado é o mais recente (65, fora da faixa = vermelho)
    glicemias = [
        {"horario": (agora - timedelta(hours=12)).isoformat(), "valor": 205, "contexto": "outro"},
        {"horario": (agora - timedelta(hours=6)).isoformat(), "valor": 90, "contexto": "outro"},
        {"horario": agora.isoformat(), "valor": 65, "contexto": "outro"},
    ]

    pdf = _GlicAIPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    _desenhar_grafico_tendencia(pdf, glicemias, perfil, "America/Sao_Paulo")

    # o círculo do último ponto (65, fora da faixa) deixa a cor de
    # preenchimento em VERMELHO — sem o reset, a próxima tabela herdaria isso
    assert tuple(pdf.fill_color.colors255) == VERMELHO

    pdf.set_fill_color(*AREIA_ZEBRA)
    assert tuple(pdf.fill_color.colors255) == AREIA_ZEBRA
