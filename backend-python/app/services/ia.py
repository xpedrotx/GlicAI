"""Fallback de IA pra interpretar comandos que o roteador não reconheceu.

Nunca executa nada sozinha — só *sugere* um comando, e quem chama
(comandos.py) sempre pede confirmação explícita antes de rodar. Sem
ANTHROPIC_API_KEY (ou se a chamada falhar), sugerir_comando() retorna None
e o bot cai na mensagem padrão "não entendi esse comando".
"""
import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

_COMANDOS_DISPONIVEIS = """
- ajuda / oi — mostra o menu de ajuda
- glicemia <valor> [jejum|pre_refeicao|pos_prandial|correcao] — registra uma medição de glicemia. Ex: "glicemia 110 jejum"
- bolus <carboidratos_g> <glicemia_atual> — calcula dose de insulina pra uma refeição. Ex: "bolus 40 130"
- apliquei <dose> — registra a dose de insulina que o paciente realmente aplicou. Ex: "apliquei 4.5"
- tratei — confirma que tratou uma hipoglicemia (comeu carboidrato de ação rápida)
- perfil — mostra os dados cadastrados do paciente
- editar <meta|limite_baixo|limite_alto|fator|nome> <valor> — muda um dado do perfil. Ex: "editar meta 110"
- basal — mostra os horários de insulina basal
- modificador <ativar|desativar> <nome> — liga/desliga um modificador de bolus
- tempo_insulina_ativa <horas> — configura o tempo de insulina ativa (IOB). Ex: "tempo_insulina_ativa 4"
- lembrete <listar|adicionar|remover> [horario] [tipo] — gerencia lembretes. Ex: "lembrete adicionar 08:00 basal"
- relatorio <semana|mes> — resumo do período
- exportar [dias] — exporta um PDF com o histórico
- hba1c [dias] — estimativa de HbA1c/GMI
- padroes [dias] — detecta padrões de glicemia por dia da semana/período
- cuidador <convidar|listar|remover> [nome] — gerencia quem acompanha o paciente
""".strip()

_SISTEMA = (
    "Você ajuda a interpretar mensagens de um paciente de diabetes tipo 1 que "
    "digitou algo que um bot baseado em comandos de texto não reconheceu — "
    "provavelmente um erro de digitação, acento faltando, ou uma frase em "
    "linguagem natural em vez do comando exato.\n\n"
    "Comandos disponíveis (formato exato esperado pelo bot):\n"
    f"{_COMANDOS_DISPONIVEIS}\n\n"
    "Sua tarefa: olhar a mensagem do paciente e, se conseguir identificar com "
    "razoável confiança qual comando ele quis usar, devolver esse comando "
    "reescrito no formato exato acima, usando os valores que ele mencionou.\n\n"
    "Se a mensagem for ambígua, vaga, ou não tiver nenhuma relação com os "
    "comandos disponíveis, não invente — devolva confiança baixa e comando "
    "vazio.\n\n"
    "Nunca invente valores numéricos que o paciente não mencionou (dose, "
    "glicemia, carboidratos, horário). Se o comando mais provável precisar de "
    "um número que não está na mensagem, prefira confiança baixa a chutar o "
    "valor — isso é sobre insulina, e um valor errado é perigoso."
)

_TOOLS = [
    {
        "name": "sugerir_comando",
        "description": "Sugere qual comando do bot o paciente provavelmente quis mandar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "comando": {
                    "type": "string",
                    "description": (
                        "O comando completo, no formato exato esperado pelo bot "
                        "(ex: 'glicemia 110 jejum', 'apliquei 4.5'). String vazia "
                        "se não conseguir determinar com confiança."
                    ),
                },
                "confianca": {
                    "type": "string",
                    "enum": ["alta", "media", "baixa"],
                    "description": "Quão confiante você está de que esse é o comando certo.",
                },
            },
            "required": ["comando", "confianca"],
        },
    }
]

_client: "anthropic.AsyncAnthropic | None" = None


def _get_client() -> "anthropic.AsyncAnthropic | None":
    global _client
    if not settings.anthropic_api_key:
        return None
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def sugerir_comando(mensagem: str) -> dict | None:
    """Pede pra IA sugerir um comando pra uma mensagem não reconhecida.

    Retorna None se a IA estiver desativada (sem chave configurada), a
    chamada falhar, ou a IA não tiver confiança suficiente pra sugerir nada.
    Nunca levanta exceção — um erro aqui não pode derrubar o fluxo normal do
    bot, só faz ele cair de volta na mensagem padrão "não entendi".
    """
    client = _get_client()
    if client is None:
        return None

    try:
        resposta = await client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=_SISTEMA,
            tools=_TOOLS,
            tool_choice={"type": "tool", "name": "sugerir_comando"},
            messages=[{"role": "user", "content": mensagem}],
        )
    except Exception:
        logger.exception("Falha ao chamar a IA de fallback de comandos")
        return None

    for bloco in resposta.content:
        if bloco.type == "tool_use" and bloco.name == "sugerir_comando":
            entrada = bloco.input or {}
            comando = (entrada.get("comando") or "").strip()
            confianca = entrada.get("confianca")
            if not comando or confianca == "baixa":
                return None
            return {"comando": comando, "confianca": confianca}

    return None


# --------------------------------------------------------------------------
# Dicas de autocuidado pra acompanhar um alerta de hiper/hipoglicemia — só
# dicas de apoio (hidratação, repouso, quando remedir), NUNCA sobre dose de
# insulina: a dose é sempre calculada de forma determinística em bolus.py,
# a IA nunca tem palavra sobre isso.
# --------------------------------------------------------------------------

_TIMEOUT_DICAS_SEGUNDOS = 8.0

_SISTEMA_DICAS = (
    "Você gera dicas curtas de autocuidado pra um paciente de diabetes tipo 1 "
    "que acabou de registrar uma glicemia fora da meta. As dicas são de apoio "
    "geral (hidratação, repouso, quando medir de novo, sinais de alerta) — "
    "NUNCA sobre dose de insulina ou qualquer medicação: a dose já foi "
    "calculada por outro sistema, de forma determinística, e você não opina "
    "sobre ela nem a menciona.\n\n"
    "Gere de 2 a 4 dicas curtas (até ~8 palavras cada), em português do "
    "Brasil, tom acolhedor e direto, sem emoji (quem exibe a mensagem já "
    "adiciona os emojis)."
)

_TOOLS_DICAS = [
    {
        "name": "dar_dicas",
        "description": "Devolve uma lista curta de dicas de autocuidado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dicas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 4,
                    "description": "Dicas curtas, cada uma até ~8 palavras, sem emoji.",
                }
            },
            "required": ["dicas"],
        },
    }
]

# Fallback fixo — usado quando a IA está desativada (sem chave), a chamada
# falha, ou demora demais. O alerta em si é tempo-sensível (paciente com
# glicemia crítica), então nunca pode esperar a IA indefinidamente nem
# deixar de mandar as dicas por causa de um erro de rede.
DICAS_PADRAO = {
    "hiperglicemia": [
        "Beba bastante água",
        "Evite exercícios intensos",
        "Meça novamente em 2 horas",
    ],
    "hipoglicemia": [
        "Evite exercícios até estabilizar",
        "Meça novamente em 15 minutos",
        "Se não melhorar, procure ajuda",
    ],
}


async def gerar_dicas(tipo: str, valor: float) -> list[str]:
    """
    Gera dicas de autocuidado via IA pra acompanhar um alerta de hiper/hipo.
    Nunca levanta exceção nem bloqueia o fluxo — cai pra DICAS_PADRAO se a IA
    estiver desativada, a chamada falhar, ou passar de _TIMEOUT_DICAS_SEGUNDOS.
    """
    client = _get_client()
    if client is None:
        return DICAS_PADRAO[tipo]

    mensagem = f"Tipo: {tipo}. Glicemia: {valor:.0f} mg/dL."
    try:
        resposta = await client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=_SISTEMA_DICAS,
            tools=_TOOLS_DICAS,
            tool_choice={"type": "tool", "name": "dar_dicas"},
            messages=[{"role": "user", "content": mensagem}],
            timeout=_TIMEOUT_DICAS_SEGUNDOS,
        )
    except Exception:
        logger.exception("Falha ao gerar dicas de correção via IA")
        return DICAS_PADRAO[tipo]

    for bloco in resposta.content:
        if bloco.type == "tool_use" and bloco.name == "dar_dicas":
            dicas = (bloco.input or {}).get("dicas") or []
            dicas = [d.strip() for d in dicas if isinstance(d, str) and d.strip()]
            if dicas:
                return dicas[:4]

    return DICAS_PADRAO[tipo]
