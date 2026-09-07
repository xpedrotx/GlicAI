"""
Cadastro conversacional passo a passo.

Estado fica em usuarios.estado_cadastro (jsonb): {"passo": "...", "dados": {...}}.
Cada handler recebe (usuario, dados, texto), valida a resposta do passo atual,
atualiza `dados`, salva o próximo passo e retorna a próxima pergunta. Se a
resposta for inválida, retorna uma mensagem de erro sem avançar o passo.
"""
from app.services.supabase_client import supabase
from app.utils import parse_hora, parse_numero, remover_acentos

INTRO = (
    "Oi! 👋 Eu sou o GlicAI.\n\n"
    "Vou ficar por aqui te ajudando a acompanhar sua diabetes: lembro você de "
    "medir a glicemia, calculo o bolus e aviso quando alguma medida sair da faixa.\n\n"
    "Uma coisa importante antes de começar: as metas e fatores que vou te "
    "perguntar agora são os que o seu médico já definiu pra você. Eu não "
    "calculo nada disso sozinho, só uso o que você digitar.\n\n"
    "Se quiser recomeçar o cadastro em algum momento, é só mandar *cancelar*.\n\n"
    "Bora? Qual é o seu nome?"
)

_AFIRMATIVOS = {"sim", "s", "yes", "y", "ok", "okay", "certo", "beleza", "blz", "claro", "pode", "quero"}
_NEGATIVOS = {"nao", "n", "no", "negativo", "nunca", "nao quero"}


def _sim_nao(texto: str) -> bool | None:
    valor = remover_acentos(texto.strip().lower())
    if valor in _AFIRMATIVOS:
        return True
    if valor in _NEGATIVOS:
        return False
    return None


async def _salvar_estado(usuario_id: str, passo: str, dados: dict) -> None:
    supabase.table("usuarios").update(
        {"estado_cadastro": {"passo": passo, "dados": dados}}
    ).eq("id", usuario_id).execute()


async def processar_passo(usuario: dict, mensagem: str) -> str:
    estado = usuario.get("estado_cadastro")

    if not estado:
        await _salvar_estado(usuario["id"], "nome", {})
        return INTRO

    texto = mensagem.strip()

    if remover_acentos(texto.lower()) == "cancelar":
        await _salvar_estado(usuario["id"], "nome", {})
        return "Cadastro reiniciado. Qual é o seu nome?"

    passo = estado.get("passo", "nome")
    dados = estado.get("dados", {})

    handler = _HANDLERS.get(passo)
    if handler is None:
        await _salvar_estado(usuario["id"], "nome", {})
        return "Deu um problema aqui no seu cadastro e precisei reiniciar. Qual é o seu nome?"

    return await handler(usuario, dados, texto)


async def _passo_nome(usuario, dados, texto):
    if not texto:
        return "Não peguei seu nome, pode mandar de novo?"
    dados["nome"] = texto
    await _salvar_estado(usuario["id"], "meta_glicemia", dados)
    primeiro_nome = texto.split()[0]
    return (
        f"Prazer, {primeiro_nome}! Qual é a sua meta de glicemia, em mg/dL? "
        "(o número que seu médico definiu como ideal, tipo *100*)"
    )


async def _passo_meta_glicemia(usuario, dados, texto):
    valor = parse_numero(texto)
    if valor is None or not (40 <= valor <= 300):
        return "Manda só o número da meta, em mg/dL — algo entre 40 e 300. Tipo *100*."
    dados["meta_glicemia"] = valor
    await _salvar_estado(usuario["id"], "limite_baixo", dados)
    return "Show. E o limite baixo? Abaixo desse valor eu considero hipoglicemia. Tipo *70*."


async def _passo_limite_baixo(usuario, dados, texto):
    valor = parse_numero(texto)
    if valor is None or not (0 < valor < dados["meta_glicemia"]):
        return f"Precisa ser um número menor que sua meta ({dados['meta_glicemia']:.0f} mg/dL). Tipo *70*."
    dados["limite_baixo"] = valor
    await _salvar_estado(usuario["id"], "limite_alto", dados)
    return "E o limite alto? Acima desse valor eu considero hiperglicemia. Tipo *180*."


async def _passo_limite_alto(usuario, dados, texto):
    valor = parse_numero(texto)
    if valor is None or valor <= dados["meta_glicemia"]:
        return f"Precisa ser um número maior que sua meta ({dados['meta_glicemia']:.0f} mg/dL). Tipo *180*."
    dados["limite_alto"] = valor
    await _salvar_estado(usuario["id"], "fator_sensibilidade", dados)
    return (
        "Beleza. Agora o seu fator de sensibilidade: quantos mg/dL 1 unidade "
        "de insulina reduz na sua glicemia. Tipo *50*."
    )


async def _passo_fator_sensibilidade(usuario, dados, texto):
    valor = parse_numero(texto)
    if valor is None or valor <= 0:
        return "Manda só o número do fator de sensibilidade. Tipo *50*."
    dados["fator_sensibilidade"] = valor
    await _salvar_estado(usuario["id"], "tempo_insulina_ativa", dados)
    return (
        "Última coisa antes da relação insulina:carboidrato: qual o seu "
        "tempo de insulina ativa, em horas? É quanto tempo a insulina "
        "rápida continua agindo no seu corpo depois de aplicada — pergunte "
        "pro seu médico se não souber. Tipo *4*."
    )


async def _passo_tempo_insulina_ativa(usuario, dados, texto):
    valor = parse_numero(texto)
    if valor is None or not (1 <= valor <= 8):
        return "Manda um número de horas entre 1 e 8. Tipo *4*."
    dados["tempo_insulina_ativa_horas"] = valor
    await _salvar_estado(usuario["id"], "relacao_ic_periodo", dados)
    return (
        "Perfeito. Agora vamos à relação insulina:carboidrato — você pode ter "
        "uma pra cada período do dia (café da manhã, almoço, jantar) ou só "
        "uma *livre* pro dia inteiro.\n\n"
        "Como você quer chamar esse primeiro período?"
    )


async def _passo_relacao_ic_periodo(usuario, dados, texto):
    if not texto:
        return "Como você quer chamar esse período? Tipo *café da manhã* ou *livre*."
    dados["relacao_ic_atual"] = {"periodo": texto}
    await _salvar_estado(usuario["id"], "relacao_ic_inicio", dados)
    return f"E o *{texto}* começa em que horário? (formato HH:MM, tipo *06:00*)"


async def _passo_relacao_ic_inicio(usuario, dados, texto):
    hora = parse_hora(texto)
    if hora is None:
        return "Não entendi o horário, manda no formato HH:MM. Tipo *06:00*."
    dados["relacao_ic_atual"]["hora_inicio"] = hora.isoformat()
    await _salvar_estado(usuario["id"], "relacao_ic_fim", dados)
    return "E até que horas vai esse período?"


async def _passo_relacao_ic_fim(usuario, dados, texto):
    hora = parse_hora(texto)
    inicio = dados["relacao_ic_atual"]["hora_inicio"]
    if hora is None or hora.isoformat() <= inicio:
        return f"Precisa ser um horário depois de {inicio[:5]}. Tipo *10:00*."
    dados["relacao_ic_atual"]["hora_fim"] = hora.isoformat()
    await _salvar_estado(usuario["id"], "relacao_ic_gramas", dados)
    return "E quantos gramas de carboidrato 1 unidade de insulina cobre nesse período?"


async def _passo_relacao_ic_gramas(usuario, dados, texto):
    valor = parse_numero(texto)
    if valor is None or valor <= 0:
        return "Manda só o número de gramas por unidade. Tipo *15*."
    dados["relacao_ic_atual"]["gramas_por_unidade"] = valor
    dados.setdefault("relacoes_ic", []).append(dados.pop("relacao_ic_atual"))
    await _salvar_estado(usuario["id"], "relacao_ic_outro", dados)
    return "Quer cadastrar mais algum período? (sim/não)"


async def _passo_relacao_ic_outro(usuario, dados, texto):
    resposta = _sim_nao(texto)
    if resposta is None:
        return "Só *sim* ou *não* aqui 🙂"
    if resposta:
        await _salvar_estado(usuario["id"], "relacao_ic_periodo", dados)
        return "Como se chama esse novo período?"
    await _salvar_estado(usuario["id"], "basal_horario", dados)
    return "Show, relação insulina:carboidrato pronta. Agora vamos à sua basal — em que horário você aplica?"


async def _passo_basal_horario(usuario, dados, texto):
    hora = parse_hora(texto)
    if hora is None:
        return "Manda o horário no formato HH:MM. Tipo *22:00*."
    dados["basal_atual"] = {"horario": hora.isoformat()}
    await _salvar_estado(usuario["id"], "basal_dose", dados)
    return "E qual a dose, em unidades?"


async def _passo_basal_dose(usuario, dados, texto):
    valor = parse_numero(texto)
    if valor is None or valor <= 0:
        return "Manda só o número de unidades. Tipo *12*."
    dados["basal_atual"]["dose"] = valor
    await _salvar_estado(usuario["id"], "basal_tipo", dados)
    return "Qual o tipo de insulina? (Lantus, Tresiba... ou manda *pular* se preferir não informar)"


async def _passo_basal_tipo(usuario, dados, texto):
    valor = remover_acentos(texto.strip().lower())
    tipo = None if valor in ("pular", "-", "nao sei") else texto.strip()
    dados["basal_atual"]["tipo_insulina"] = tipo
    dados.setdefault("basal", []).append(dados.pop("basal_atual"))
    await _salvar_estado(usuario["id"], "basal_outro", dados)
    return "Tem outro horário de basal pra cadastrar? (sim/não)"


async def _passo_basal_outro(usuario, dados, texto):
    resposta = _sim_nao(texto)
    if resposta is None:
        return "Só *sim* ou *não* aqui 🙂"
    if resposta:
        await _salvar_estado(usuario["id"], "basal_horario", dados)
        return "Horário de aplicação?"
    await _salvar_estado(usuario["id"], "modificadores_pergunta", dados)
    return (
        "Última parte, prometo. Você usa algum modificador de bolus? São "
        "ajustes pra situações específicas, tipo exercício físico ou dia de "
        "doença, que você liga e desliga quando precisa.\n\n"
        "Quer cadastrar algum agora? (sim/não — dá pra adicionar depois também)"
    )


async def _passo_modificadores_pergunta(usuario, dados, texto):
    resposta = _sim_nao(texto)
    if resposta is None:
        return "Só *sim* ou *não* aqui 🙂"
    if resposta:
        await _salvar_estado(usuario["id"], "modificador_nome", dados)
        return "Como você quer chamar esse modificador? Tipo *exercício físico*."
    await _salvar_estado(usuario["id"], "lembretes_pergunta", dados)
    return "Quer que eu te lembre todo dia de medir a glicemia? (sim/não)"


async def _passo_modificador_nome(usuario, dados, texto):
    if not texto:
        return "Como você quer chamar esse modificador? Tipo *exercício físico*."
    dados["modificador_atual"] = {"nome": texto}
    await _salvar_estado(usuario["id"], "modificador_tipo", dados)
    return "Esse ajuste é em porcentagem ou em unidades fixas? Manda *percentual* ou *fixo*."


async def _passo_modificador_tipo(usuario, dados, texto):
    tipo = remover_acentos(texto.strip().lower())
    if tipo not in ("percentual", "fixo"):
        return "Manda *percentual* ou *fixo*."
    dados["modificador_atual"]["tipo_ajuste"] = tipo
    await _salvar_estado(usuario["id"], "modificador_valor", dados)
    if tipo == "percentual":
        return "Qual o ajuste, em %? Negativo reduz a dose, positivo aumenta. Tipo *-20*."
    return "Qual o ajuste, em unidades? Negativo reduz a dose, positivo aumenta. Tipo *-2*."


async def _passo_modificador_valor(usuario, dados, texto):
    valor = parse_numero(texto)
    if valor is None:
        return "Manda só o número (pode ser negativo). Tipo *-20*."
    dados["modificador_atual"]["valor_ajuste"] = valor
    dados.setdefault("modificadores", []).append(dados.pop("modificador_atual"))
    await _salvar_estado(usuario["id"], "modificador_outro", dados)
    return "Quer cadastrar outro modificador? (sim/não)"


async def _passo_modificador_outro(usuario, dados, texto):
    resposta = _sim_nao(texto)
    if resposta is None:
        return "Só *sim* ou *não* aqui 🙂"
    if resposta:
        await _salvar_estado(usuario["id"], "modificador_nome", dados)
        return "Como se chama esse modificador?"
    await _salvar_estado(usuario["id"], "lembretes_pergunta", dados)
    return "Quer que eu te lembre todo dia de medir a glicemia? (sim/não)"


async def _passo_lembretes_pergunta(usuario, dados, texto):
    resposta = _sim_nao(texto)
    if resposta is None:
        return "Só *sim* ou *não* aqui 🙂"
    if resposta:
        await _salvar_estado(usuario["id"], "lembrete_horario", dados)
        return "A que horas?"
    return await _finalizar(usuario, dados)


async def _passo_lembrete_horario(usuario, dados, texto):
    hora = parse_hora(texto)
    if hora is None:
        return "Manda o horário no formato HH:MM. Tipo *08:00*."
    dados.setdefault("lembretes_medir", []).append(hora.isoformat())
    await _salvar_estado(usuario["id"], "lembrete_outro", dados)
    return "Quer mais algum horário de lembrete? (sim/não)"


async def _passo_lembrete_outro(usuario, dados, texto):
    resposta = _sim_nao(texto)
    if resposta is None:
        return "Só *sim* ou *não* aqui 🙂"
    if resposta:
        await _salvar_estado(usuario["id"], "lembrete_horario", dados)
        return "A que horas?"
    return await _finalizar(usuario, dados)


async def _finalizar(usuario, dados) -> str:
    usuario_id = usuario["id"]

    supabase.table("usuarios").update(
        {"nome": dados["nome"], "status_cadastro": "completo", "estado_cadastro": None}
    ).eq("id", usuario_id).execute()

    supabase.table("perfil_glicemico").insert(
        {
            "usuario_id": usuario_id,
            "meta_glicemia": int(dados["meta_glicemia"]),
            "limite_baixo": int(dados["limite_baixo"]),
            "limite_alto": int(dados["limite_alto"]),
            "fator_sensibilidade": int(dados["fator_sensibilidade"]),
            "tempo_insulina_ativa_horas": dados["tempo_insulina_ativa_horas"],
        }
    ).execute()

    for relacao in dados.get("relacoes_ic", []):
        supabase.table("relacao_ic").insert(
            {
                "usuario_id": usuario_id,
                "periodo": relacao["periodo"],
                "hora_inicio": relacao["hora_inicio"],
                "hora_fim": relacao["hora_fim"],
                "gramas_por_unidade": relacao["gramas_por_unidade"],
            }
        ).execute()

    for basal in dados.get("basal", []):
        supabase.table("basal").insert(
            {
                "usuario_id": usuario_id,
                "horario": basal["horario"],
                "dose": basal["dose"],
                "tipo_insulina": basal["tipo_insulina"],
            }
        ).execute()

    for modificador in dados.get("modificadores", []):
        supabase.table("modificadores_bolus").insert(
            {
                "usuario_id": usuario_id,
                "nome": modificador["nome"],
                "tipo_ajuste": modificador["tipo_ajuste"],
                "valor_ajuste": modificador["valor_ajuste"],
            }
        ).execute()

    for horario in dados.get("lembretes_medir", []):
        supabase.table("lembretes").insert(
            {"usuario_id": usuario_id, "tipo": "medir_glicemia", "horario": horario}
        ).execute()

    primeiro_nome = dados["nome"].split()[0]
    return (
        f"🙌 *Prontinho, {primeiro_nome}! Seu cadastro tá completo.*\n\n"
        "Agora é só falar comigo do seu jeito, tipo:\n"
        "🩸 _\"minha glicose deu 110\"_ — registro a medição\n"
        "💉 _\"vou comer 40g de carboidrato, tá 130\"_ — calculo a dose\n"
        "✅ _\"tomei 4.5 unidades\"_ — registro o que você aplicou\n"
        "📋 _\"quais são meus dados\"_ — mostro seu perfil\n\n"
        "Se preferir os comandos certinhos, manda *ajuda* que eu te mostro a lista."
    )


_HANDLERS = {
    "nome": _passo_nome,
    "meta_glicemia": _passo_meta_glicemia,
    "limite_baixo": _passo_limite_baixo,
    "limite_alto": _passo_limite_alto,
    "fator_sensibilidade": _passo_fator_sensibilidade,
    "tempo_insulina_ativa": _passo_tempo_insulina_ativa,
    "relacao_ic_periodo": _passo_relacao_ic_periodo,
    "relacao_ic_inicio": _passo_relacao_ic_inicio,
    "relacao_ic_fim": _passo_relacao_ic_fim,
    "relacao_ic_gramas": _passo_relacao_ic_gramas,
    "relacao_ic_outro": _passo_relacao_ic_outro,
    "basal_horario": _passo_basal_horario,
    "basal_dose": _passo_basal_dose,
    "basal_tipo": _passo_basal_tipo,
    "basal_outro": _passo_basal_outro,
    "modificadores_pergunta": _passo_modificadores_pergunta,
    "modificador_nome": _passo_modificador_nome,
    "modificador_tipo": _passo_modificador_tipo,
    "modificador_valor": _passo_modificador_valor,
    "modificador_outro": _passo_modificador_outro,
    "lembretes_pergunta": _passo_lembretes_pergunta,
    "lembrete_horario": _passo_lembrete_horario,
    "lembrete_outro": _passo_lembrete_outro,
}
