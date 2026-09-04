"""Exportação do histórico de glicemia/bolus em PDF — pra levar na consulta.

Segue a identidade visual do GlicAI: Âmbar Glic + Coral Vida como cores
primárias (energia/acolhimento), Azul Petróleo pra texto (confiança), Areia
de fundo, e Verde/Vermelho reservados só pro significado clínico real
(leitura dentro ou fora da faixa) — nunca decorativos. Tipografia: Fraunces
(serifada, quente) pra marca e títulos, Inter pro corpo e pros números
(legibilidade numérica é importante pra leituras de glicose).
"""
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fpdf import FPDF
from fpdf.enums import TableBordersLayout, TableCellFillMode
from fpdf.fonts import FontFace

from app.services.supabase_client import supabase

DIAS_PADRAO = 90
DIAS_MAXIMO = 365

# --- Identidade visual ---------------------------------------------------
AMBAR = (245, 166, 35)      # #F5A623 — energia/acolhimento
CORAL = (255, 111, 94)      # #FF6F5E — energia/acolhimento
PETROLEO = (27, 58, 75)     # #1B3A4B — texto/confiança
AREIA = (251, 246, 239)     # #FBF6EF — fundo neutro
AREIA_ZEBRA = (245, 232, 210)  # tom levemente mais quente, só pra zebra das tabelas
VERDE = (76, 175, 125)      # #4CAF7D — só significado clínico (leitura normal)
VERMELHO = (232, 93, 93)    # #E85D5D — só significado clínico (fora da faixa)

_FONTS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts"))

# Mesmo texto usado nas mensagens do WhatsApp (ver comandos.py) — duplicado
# aqui pra evitar import circular (comandos.py importa esse módulo, não o
# contrário).
_CONTEXTO_LABEL = {
    "jejum": "Em jejum",
    "pre_refeicao": "Antes da refeição",
    "pos_prandial": "Depois da refeição",
    "correcao": "Correção",
}


def _formatar_horario(horario_iso: str, tz: str) -> str:
    # horario vem do banco em UTC — converte pro fuso do paciente antes de
    # formatar, senão a hora mostrada não bate com a hora real da medição.
    dt = datetime.fromisoformat(horario_iso).astimezone(ZoneInfo(tz))
    return dt.strftime("%d/%m %H:%M")


def _formatar_contexto(contexto: str | None) -> str:
    # "outro" é o padrão quando o paciente não informa contexto nenhum (ex:
    # só "glicemia 110") — não é informação de verdade, então mostra "-" em
    # vez do rótulo literal, igual já acontece no chat do WhatsApp.
    if not contexto or contexto == "outro":
        return "-"
    return _CONTEXTO_LABEL.get(contexto, contexto)


def _cor_e_seta_glicemia(
    valor: int, limite_baixo: int, meta: int, limite_alto: int
) -> tuple[tuple[int, int, int], str]:
    """
    Classifica a leitura em 4 faixas (cor + seta indicando a direção do
    problema, quando há um):
    - abaixo do limite baixo: vermelho + seta pra baixo (hipoglicemia)
    - entre o limite baixo e a meta: verde (na faixa boa)
    - entre a meta e o limite alto: petróleo/preto (elevado, mas não crítico)
    - acima do limite alto: vermelho + seta pra cima (hiperglicemia)
    Verde e vermelho são as únicas cores com significado clínico — nunca
    usadas fora desse contexto.
    """
    if valor < limite_baixo:
        return VERMELHO, "↓"
    if valor > limite_alto:
        return VERMELHO, "↑"
    if valor < meta:
        return VERDE, ""
    return PETROLEO, ""


class _GlicAIPDF(FPDF):
    """FPDF com a identidade visual do GlicAI aplicada via header()/footer()
    — repete em toda página nova, inclusive as adicionadas automaticamente
    pelo auto_page_break."""

    def __init__(self):
        super().__init__()
        self.add_font("Fraunces", "", os.path.join(_FONTS_DIR, "Fraunces-Regular.ttf"))
        self.add_font("Fraunces", "B", os.path.join(_FONTS_DIR, "Fraunces-Bold.ttf"))
        self.add_font("Inter", "", os.path.join(_FONTS_DIR, "Inter-Regular.ttf"))
        self.add_font("Inter", "B", os.path.join(_FONTS_DIR, "Inter-Bold.ttf"))

    def header(self):
        # fundo areia em toda a página
        self.set_fill_color(*AREIA)
        self.rect(0, 0, self.w, self.h, style="F")

        # faixa azul petróleo com a marca — mais alta só na primeira página
        primeira_pagina = self.page_no() == 1
        altura_faixa = 24 if primeira_pagina else 14
        self.set_fill_color(*PETROLEO)
        self.rect(0, 0, self.w, altura_faixa, style="F")

        self.set_xy(10, 4 if primeira_pagina else 2.5)
        self.set_font("Fraunces", "B", 18 if primeira_pagina else 12)
        self.set_text_color(*AREIA)
        self.cell(0, 10, "GlicAI", new_x="LMARGIN", new_y="NEXT")

        if primeira_pagina:
            self.set_x(10)
            self.set_font("Inter", "", 9)
            self.set_text_color(210, 197, 178)  # areia mais discreto, só pra tagline
            self.cell(0, 6, "Acompanhamento de glicemia pelo WhatsApp", new_x="LMARGIN", new_y="NEXT")

        # faixa dupla âmbar/coral por baixo — o toque de cor da marca
        self.set_fill_color(*AMBAR)
        self.rect(0, altura_faixa, self.w / 2, 1.5, style="F")
        self.set_fill_color(*CORAL)
        self.rect(self.w / 2, altura_faixa, self.w / 2, 1.5, style="F")

        self.set_y(altura_faixa + 6)
        self.set_text_color(*PETROLEO)

    def footer(self):
        self.set_y(-12)
        self.set_font("Inter", "", 8)
        self.set_text_color(150, 140, 125)
        self.cell(0, 8, f"GlicAI  ·  página {self.page_no()}", align="C")


def _desenhar_grafico_tendencia(pdf: FPDF, glicemias: list[dict], perfil: dict, tz: str) -> None:
    """Gráfico de tendência desenhado com as primitivas do próprio fpdf2 (sem matplotlib)."""
    if len(glicemias) < 2:
        return  # não dá pra falar de "tendência" com 0 ou 1 ponto

    limite_baixo = perfil["limite_baixo"]
    limite_alto = perfil["limite_alto"]
    meta = perfil["meta_glicemia"]

    pontos = sorted(
        (datetime.fromisoformat(g["horario"]).astimezone(ZoneInfo(tz)), g["valor"]) for g in glicemias
    )

    largura, altura = 160, 50
    espaco_necessario = altura + 16
    if pdf.get_y() + espaco_necessario > pdf.h - 15:
        pdf.add_page()

    _secao(pdf, "Tendência do período")
    x0, y0 = 15, pdf.get_y() + 2

    tempo_min, tempo_max = pontos[0][0], pontos[-1][0]
    span_segundos = max(1.0, (tempo_max - tempo_min).total_seconds())
    valores = [v for _, v in pontos]
    valor_min = min(min(valores), limite_baixo) - 10
    valor_max = max(max(valores), limite_alto) + 10
    span_valor = max(1.0, valor_max - valor_min)

    def px(dt: datetime) -> float:
        return x0 + (dt - tempo_min).total_seconds() / span_segundos * largura

    def py(valor: float) -> float:
        return y0 + altura - (valor - valor_min) / span_valor * altura

    # linhas de referência tracejadas (baixo/meta/alto), com o rótulo à direita
    pdf.set_font("Inter", "", 7)
    for rotulo, valor_ref, cor in (
        (f"Alto {limite_alto:.0f}", limite_alto, VERMELHO),
        (f"Meta {meta:.0f}", meta, PETROLEO),
        (f"Baixo {limite_baixo:.0f}", limite_baixo, VERMELHO),
    ):
        y_ref = py(valor_ref)
        pdf.set_draw_color(*cor)
        pdf.set_line_width(0.2)
        pdf.set_dash_pattern(dash=1, gap=1)
        pdf.line(x0, y_ref, x0 + largura, y_ref)
        pdf.set_dash_pattern()
        pdf.set_text_color(*cor)
        pdf.text(x0 + largura + 2, y_ref + 1.5, rotulo)

    # linha conectando as medições, na ordem cronológica
    pdf.set_draw_color(*PETROLEO)
    pdf.set_line_width(0.3)
    for (dt1, v1), (dt2, v2) in zip(pontos, pontos[1:]):
        pdf.line(px(dt1), py(v1), px(dt2), py(v2))

    # pontos coloridos pela mesma regra clínica da tabela
    for dt, valor in pontos:
        cor, _ = _cor_e_seta_glicemia(valor, limite_baixo, meta, limite_alto)
        pdf.set_fill_color(*cor)
        pdf.circle(px(dt), py(valor), 0.9, style="F")

    # datas de início/fim no eixo X
    pdf.set_font("Inter", "", 7)
    pdf.set_text_color(*PETROLEO)
    pdf.text(x0, y0 + altura + 5, tempo_min.strftime("%d/%m"))
    pdf.text(x0 + largura - 8, y0 + altura + 5, tempo_max.strftime("%d/%m"))

    pdf.set_y(y0 + altura + 10)
    pdf.set_text_color(*PETROLEO)


def _secao(pdf: FPDF, titulo: str) -> None:
    pdf.set_font("Fraunces", "B", 13)
    pdf.set_text_color(*PETROLEO)
    pdf.cell(0, 8, titulo, new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.set_draw_color(*AMBAR)
    pdf.set_line_width(0.7)
    pdf.line(10, y, 32, y)
    pdf.ln(3)


def _montar_pdf(
    nome: str, data_inicio: datetime, data_fim: datetime, perfil: dict,
    glicemias: list[dict], bolus: list[dict], tz: str,
) -> bytes:
    data_inicio_local = data_inicio.astimezone(ZoneInfo(tz))
    data_fim_local = data_fim.astimezone(ZoneInfo(tz))

    pdf = _GlicAIPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()  # dispara header() automaticamente

    # --- Cabeçalho do documento (nome, período, geração) ---
    pdf.set_font("Inter", "B", 11)
    pdf.set_text_color(*PETROLEO)
    pdf.cell(0, 6, f"{nome} — Histórico do paciente", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Inter", "", 9)
    periodo = f"{data_inicio_local.strftime('%d/%m/%Y')} a {data_fim_local.strftime('%d/%m/%Y')}"
    gerado_em = data_fim_local.strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 5, f"Período: {periodo}   ·   Gerado em {gerado_em}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # --- Perfil ---
    _secao(pdf, "Perfil glicêmico")
    pdf.set_font("Inter", "", 10)
    pdf.cell(
        0, 6,
        f"Meta: {perfil['meta_glicemia']} mg/dL   |   Faixa alvo: {perfil['limite_baixo']}-{perfil['limite_alto']} mg/dL",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(0, 6, f"Fator de sensibilidade: {perfil['fator_sensibilidade']} mg/dL por U", new_x="LMARGIN", new_y="NEXT")
    if perfil.get("tempo_insulina_ativa_horas"):
        pdf.cell(0, 6, f"Tempo de insulina ativa: {perfil['tempo_insulina_ativa_horas']}h", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # --- Resumo do período ---
    if glicemias:
        valores = [g["valor"] for g in glicemias]
        media = sum(valores) / len(valores)
        limite_baixo = perfil["limite_baixo"]
        limite_alto = perfil["limite_alto"]
        na_faixa = sum(1 for v in valores if limite_baixo <= v <= limite_alto)
        hipos = sum(1 for v in valores if v < limite_baixo)
        hipers = sum(1 for v in valores if v > limite_alto)
        pct_faixa = round(100 * na_faixa / len(valores))

        _secao(pdf, "Resumo do período")
        pdf.set_font("Inter", "B", 10)
        pdf.set_text_color(*PETROLEO)
        pdf.cell(
            0, 6,
            f"{len(valores)} medições   ·   Média: {media:.0f} mg/dL   ·   Na faixa: {pct_faixa}%",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.set_font("Inter", "", 10)
        # verde/vermelho aqui têm significado clínico real — não decoração
        pdf.set_text_color(*(VERMELHO if hipos > 0 else PETROLEO))
        pdf.cell(0, 6, f"Hipoglicemias: {hipos}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*(VERMELHO if hipers > 0 else PETROLEO))
        pdf.cell(0, 6, f"Hiperglicemias: {hipers}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*PETROLEO)
        pdf.ln(4)

        _desenhar_grafico_tendencia(pdf, glicemias, perfil, tz)

    # --- Tabela de glicemia ---
    _secao(pdf, "Histórico de glicemia")
    if not glicemias:
        pdf.set_font("Inter", "", 10)
        pdf.cell(0, 6, "Sem registros no período.", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Inter", "", 9)
        pdf.set_draw_color(220, 208, 190)
        # reseta a cor de preenchimento — sem isso, o estado deixado pelos
        # círculos coloridos do gráfico (verde/vermelho) "vaza" pro fundo
        # das linhas da tabela, deixando texto verde em cima de fundo verde.
        pdf.set_fill_color(*AREIA_ZEBRA)
        limite_baixo = perfil["limite_baixo"]
        limite_alto = perfil["limite_alto"]
        meta = perfil["meta_glicemia"]
        with pdf.table(
            col_widths=(45, 25, 40),
            text_align="LEFT",
            borders_layout=TableBordersLayout.HORIZONTAL_LINES,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=AREIA_ZEBRA,
            headings_style=FontFace(family="Inter", emphasis="BOLD", color=AREIA, fill_color=PETROLEO),
        ) as table:
            cabecalho = table.row()
            for titulo in ("Data/hora", "mg/dL", "Contexto"):
                cabecalho.cell(titulo)
            for g in glicemias:
                linha = table.row()
                linha.cell(_formatar_horario(g["horario"], tz))
                valor = g["valor"]
                cor, seta = _cor_e_seta_glicemia(valor, limite_baixo, meta, limite_alto)
                texto_valor = f"{valor} {seta}" if seta else str(valor)
                linha.cell(texto_valor, style=FontFace(emphasis="BOLD", color=cor))
                linha.cell(_formatar_contexto(g.get("contexto")))
    pdf.ln(4)

    # --- Tabela de bolus ---
    _secao(pdf, "Histórico de bolus")
    if not bolus:
        pdf.set_font("Inter", "", 10)
        pdf.cell(0, 6, "Sem registros no período.", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Inter", "", 9)
        pdf.set_draw_color(220, 208, 190)
        pdf.set_fill_color(*AREIA_ZEBRA)
        with pdf.table(
            col_widths=(35, 25, 25, 25, 25),
            text_align="LEFT",
            borders_layout=TableBordersLayout.HORIZONTAL_LINES,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=AREIA_ZEBRA,
            headings_style=FontFace(family="Inter", emphasis="BOLD", color=AREIA, fill_color=PETROLEO),
        ) as table:
            cabecalho = table.row()
            for titulo in ("Data/hora", "Carb (g)", "Glic. ref", "Calculada", "Aplicada"):
                cabecalho.cell(titulo)
            for b in bolus:
                linha = table.row()
                linha.cell(_formatar_horario(b["horario"], tz))
                linha.cell(str(b["carboidratos_g"]) if b.get("carboidratos_g") is not None else "-")
                linha.cell(str(b["glicemia_referencia"]) if b.get("glicemia_referencia") is not None else "-")
                linha.cell(f"{b['dose_calculada']:.1f}U" if b.get("dose_calculada") is not None else "-")
                linha.cell(f"{b['dose_aplicada']:.1f}U" if b.get("dose_aplicada") is not None else "-")

    return bytes(pdf.output())


async def buscar_dados_historico(usuario_id: str, dias: int) -> dict | None:
    """
    Busca os dados brutos do período (usuário, perfil, glicemias, bolus) —
    usado tanto pela exportação em PDF quanto pela API JSON do site de
    acompanhamento (web_api.py), pra não duplicar as mesmas consultas.
    Retorna None se o paciente não tiver perfil glicêmico completo.
    """
    usuarios = supabase.table("usuarios").select("*").eq("id", usuario_id).execute().data
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data
    if not usuarios or not perfis:
        return None

    usuario = usuarios[0]
    perfil = perfis[0]

    data_fim = datetime.now(timezone.utc)
    data_inicio = data_fim - timedelta(days=dias)
    inicio_iso = data_inicio.isoformat()

    glicemias = (
        supabase.table("registros_glicemia")
        .select("*")
        .eq("usuario_id", usuario_id)
        .gte("horario", inicio_iso)
        .order("horario")
        .execute()
        .data
    )
    bolus = (
        supabase.table("registros_bolus")
        .select("*")
        .eq("usuario_id", usuario_id)
        .gte("horario", inicio_iso)
        .order("horario")
        .execute()
        .data
    )

    return {
        "usuario": usuario,
        "perfil": perfil,
        "glicemias": glicemias,
        "bolus": bolus,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }


async def gerar_pdf_historico(usuario_id: str, dias: int) -> bytes | None:
    """Retorna os bytes do PDF, ou None se o perfil do paciente não estiver completo."""
    dados = await buscar_dados_historico(usuario_id, dias)
    if dados is None:
        return None

    nome = dados["usuario"].get("nome") or "Paciente"
    tz = dados["usuario"].get("timezone") or "America/Sao_Paulo"

    return _montar_pdf(
        nome, dados["data_inicio"], dados["data_fim"], dados["perfil"], dados["glicemias"], dados["bolus"], tz
    )
