"""
Rede de segurança mínima contra risco à vida na mensagem do paciente —
NÃO é triagem profissional nem detecção sofisticada, é uma checagem por
palavra-chave que roda antes de qualquer outro processamento (ver
webhook.py). Existe pra nunca deixar uma mensagem de crise cair no fallback
genérico "não entendi esse comando".

Limitação real e assumida: é fácil escrever uma frase que expresse a mesma
coisa e não bata em nenhuma palavra-chave — isso é um piso, não uma solução
completa. Prioriza menos falsos negativos (detectar demais) sobre precisão,
porque o custo de um falso positivo (o bot oferecer ajuda sem precisar) é
baixo, e o custo de um falso negativo (não oferecer ajuda numa crise real) é
alto.
"""
from app.utils import remover_acentos

_SINAIS_RISCO = (
    "quero morrer",
    "quero me matar",
    "vou me matar",
    "me matar",
    "tirar minha vida",
    "tirar a propria vida",
    "acabar com minha vida",
    "acabar com a minha vida",
    "acabar com tudo",
    "nao aguento mais viver",
    "nao quero mais viver",
    "nao quero mais existir",
    "nao vejo sentido em viver",
    "nao tem mais sentido viver",
    "sem vontade de viver",
    "melhor eu nao existir",
    "seria melhor se eu nao existisse",
    "me suicidar",
    "suicidio",
    "cortar os pulsos",
    "cortando os pulsos",
    "me cortar",
)

_MENSAGEM_APOIO = (
    "💙 Percebi algo na sua mensagem que me deixou preocupado com você.\n\n"
    "Eu sou um bot de diabetes e não tenho preparo pra lidar com isso — mas "
    "existe gente preparada pra te ouvir agora, de graça e a qualquer hora:\n\n"
    "🆘 *CVV — Centro de Valorização da Vida*: ligue *188* (24h, grátis) ou "
    "acesse *cvv.org.br* pra conversar por chat\n"
    "🚑 Em risco imediato: *192* (SAMU) ou vá ao pronto-socorro mais perto\n\n"
    "Se eu entendi errado e você só tava desabafando sobre a diabetes, "
    "desculpa — pode mandar seu comando de novo."
)


def detectar_risco(mensagem: str) -> bool:
    texto = remover_acentos(mensagem.strip().lower())
    return any(sinal in texto for sinal in _SINAIS_RISCO)


def mensagem_apoio() -> str:
    return _MENSAGEM_APOIO
