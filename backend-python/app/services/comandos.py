"""Roteador de comandos de texto usado depois que o cadastro está completo."""
from datetime import datetime, timedelta, timezone

from app.services import auth_web, confirmacoes, cuidadores, estoque, ia, remedicao
from app.services.alertas import checar_alerta_glicemia
from app.services.bolus import (
    calcular_correcao,
    calcular_e_registrar_bolus,
    calcular_insulina_ativa,
    registrar_dose_aplicada,
)
from app.services.exportacao import DIAS_MAXIMO as EXPORTAR_DIAS_MAXIMO
from app.services.exportacao import DIAS_PADRAO as EXPORTAR_DIAS_PADRAO
from app.services.exportacao import gerar_pdf_historico
from app.services.hba1c import DIAS_PADRAO as HBA1C_DIAS_PADRAO
from app.services.hba1c import formatar_estimativa, gerar_estimativa
from app.services.padroes import DIAS_PADRAO as PADROES_DIAS_PADRAO
from app.services.padroes import detectar_padroes, formatar_padroes
from app.services.relatorios import gerar_relatorio
from app.services.supabase_client import supabase
from app.services.whatsapp_sender import enviar_arquivo
from app.utils import agora_usuario, formatar_hora_local, parse_hora, parse_numero, remover_acentos

LIMITE_EMERGENCIA = 600
# Nível 2 de hipoglicemia (ADA/EASD): abaixo disso já é "clinicamente
# significativo, requer ação imediata" — risco real de confusão mental,
# convulsão ou perda de consciência, não só "trate e meça de novo depois".
# Limite fixo e absoluto, igual LIMITE_EMERGENCIA — não depende do
# limite_baixo pessoal do perfil (que é só o gatilho do aviso normal).
LIMITE_EMERGENCIA_BAIXO = 54


async def _bloco_hiperglicemia(valor: float, correcao: dict) -> str:
    """Cartão de alerta de hiperglicemia: dose sugerida + dicas de IA (nunca sobre dose)."""
    dicas = await ia.gerar_dicas("hiperglicemia", valor)
    linhas = [
        "🚨 *Glicemia alta! Ação necessária.*",
        "",
        f"💉 Sugestão: aplicar *{correcao['dose_final']:.0f}U* de insulina",
    ]
    if correcao["dose_exata"] - correcao["dose_final"] >= 0.05:
        linhas.append(f"ℹ️ _Valor exato seria {correcao['dose_exata']:.1f}U, arredondado pra baixo._")
    linhas.append("")
    linhas.extend(f"• {dica}" for dica in dicas)
    linhas.append("")
    linhas.append("> " + correcao["explicacao"].replace("\n", "\n> "))
    linhas.append("")
    linhas.append("Depois que aplicar, me conta com *apliquei <dose>*.")
    return "\n".join(linhas)


async def _bloco_hipoglicemia(valor: float, limite_baixo: int) -> str:
    """Cartão de alerta de hipoglicemia — título, valor, dicas de autocuidado geradas por IA."""
    dicas = await ia.gerar_dicas("hipoglicemia", valor)
    linhas = [
        "🍬 *Glicemia baixa! Ação necessária.*",
        "",
        f"🔴 {valor:.0f} mg/dL — abaixo do seu limite de {limite_baixo} mg/dL",
        "",
    ]
    linhas.extend(f"• {dica}" for dica in dicas)
    linhas.append("")
    linhas.append("⚠️ Não aplique insulina agora. Trate com carboidrato de ação rápida e meça de novo em 15 minutos.")
    linhas.append("Quando tratar, me conta com *tratei*.")
    return "\n".join(linhas)


def _mensagem_emergencia(valor: float) -> str:
    return (
        f"🚨 *Emergência — {valor:.0f} mg/dL*\n\n"
        "Isso está fora do que eu consigo te ajudar a resolver por aqui.\n\n"
        "Procure atendimento médico agora."
    )


def _mensagem_emergencia_baixa(valor: float) -> str:
    return (
        f"🚨 *Emergência — hipoglicemia grave, {valor:.0f} mg/dL*\n\n"
        "⚠️ Trate AGORA com carboidrato de ação rápida (ex: suco, mel, "
        "tablete de glicose) — não espere.\n\n"
        "Se estiver confuso(a), muito fraco(a) ou não conseguir se tratar "
        "sozinho(a), peça ajuda a alguém perto de você AGORA ou ligue *192* (SAMU)."
    )


_CONTEXTOS = {
    "jejum": "jejum",
    "pre_refeicao": "pre_refeicao",
    "prerefeicao": "pre_refeicao",
    "antes": "pre_refeicao",
    "pos_prandial": "pos_prandial",
    "posprandial": "pos_prandial",
    "depois": "pos_prandial",
    "correcao": "correcao",
    "outro": "outro",
}

_CONTEXTO_LABEL = {
    "jejum": "em jejum",
    "pre_refeicao": "antes da refeição",
    "pos_prandial": "depois da refeição",
    "correcao": "correção",
}


def _normalizar_contexto(texto: str) -> str | None:
    chave = remover_acentos(texto.strip().lower()).replace(" ", "_").replace("-", "_")
    return _CONTEXTOS.get(chave)


# Alguns comandos aparecem no texto de ajuda com espaço em vez de "_"
# (ex: "tempo insulina ativa" em vez de "tempo_insulina_ativa") pra ficar
# mais natural de ler — isso reescreve pro token único que o roteador espera.
_ALIASES_COMANDO_MULTIPALAVRA = {
    "tempo insulina ativa": "tempo_insulina_ativa",
    "criar senha": "criar_senha",
    "excluir conta": "excluir_conta",
    "excluir minha conta": "excluir_conta",
    "apagar meus dados": "excluir_conta",
    "apagar minha conta": "excluir_conta",
}


def _normalizar_prefixo_multipalavra(mensagem: str) -> str:
    normalizado = remover_acentos(mensagem.strip().lower())
    for alias, comando in _ALIASES_COMANDO_MULTIPALAVRA.items():
        if normalizado == alias or normalizado.startswith(alias + " "):
            resto = mensagem.strip()[len(alias):].strip()
            return f"{comando} {resto}".strip()
    return mensagem


# Quanto tempo uma sugestão da IA fica válida esperando confirmação do
# paciente — depois disso, um "sim" avulso não deve reexecutar um comando
# de insulina antigo por engano.
_SUGESTAO_VALIDADE_MINUTOS = 5


def _sim_ou_nao(texto: str) -> bool | None:
    normalizado = remover_acentos(texto.strip().lower())
    if normalizado in ("sim", "s", "isso", "correto", "confirma", "confirmar", "yes", "y"):
        return True
    if normalizado in ("nao", "n", "cancela", "cancelar", "errado", "no"):
        return False
    return None


async def _limpar_sugestao_pendente(usuario_id: str) -> None:
    supabase.table("usuarios").update({"sugestao_pendente": None}).eq("id", usuario_id).execute()


async def _tratar_sugestao_pendente(usuario: dict, mensagem: str, pendente: dict) -> str | None:
    """Se `usuario` tem uma sugestão da IA aguardando confirmação, tenta
    interpretar `mensagem` como a resposta (sim/não). Retorna None quando a
    mensagem não é uma confirmação (ou a sugestão expirou) — nesse caso o
    chamador segue o fluxo normal de roteamento com a mesma mensagem."""
    criado_em_texto = pendente.get("criado_em")
    if criado_em_texto:
        try:
            criado_em = datetime.fromisoformat(criado_em_texto)
            if datetime.now(timezone.utc) - criado_em > timedelta(minutes=_SUGESTAO_VALIDADE_MINUTOS):
                await _limpar_sugestao_pendente(usuario["id"])
                usuario["sugestao_pendente"] = None
                return None
        except ValueError:
            pass

    decisao = _sim_ou_nao(mensagem)
    if decisao is None:
        return None

    await _limpar_sugestao_pendente(usuario["id"])
    usuario["sugestao_pendente"] = None

    if decisao is False:
        return "Ok, deixa pra lá. Manda *ajuda* pra ver os comandos disponíveis."

    comando_sugerido = pendente.get("comando") or ""
    if not comando_sugerido:
        return "Ok, deixa pra lá. Manda *ajuda* pra ver os comandos disponíveis."
    return await processar_comando(usuario, comando_sugerido)


# Comandos que só leem/informam (nunca registram glicemia, dose, mudam
# perfil/cuidadores/lembretes nem apagam nada) — a IA pode executar direto,
# sem pedir confirmação, porque errar aqui não tem custo real: na pior das
# hipóteses mostra a informação errada e o paciente pede de novo. Qualquer
# coisa que grava dado clínico ou é destrutiva continua pedindo *sim/não*.
_COMANDOS_SEGUROS_SEM_SUBACAO = {
    "ajuda", "menu", "help", "oi", "ola", "oii", "oie", "eae", "hey", "hello",
    "perfil", "basal", "relatorio", "exportar", "hba1c", "gmi", "padroes", "padrao",
    "criar_senha",
}


def _comando_e_seguro(comando_texto: str) -> bool:
    partes = _normalizar_prefixo_multipalavra(comando_texto).strip().split()
    if not partes:
        return True  # mensagem vazia cai no _ajuda(), sem risco
    comando = remover_acentos(partes[0].lower())

    if comando in _COMANDOS_SEGUROS_SEM_SUBACAO:
        return True
    # "cuidador"/"estoque"/"lembrete" sem sub-ação (ou só "listar") são
    # leitura; qualquer outra sub-ação (convidar, remover, configurar,
    # reabastecer, adicionar) muda dado e continua exigindo confirmação.
    if comando in ("cuidador", "lembrete") and len(partes) > 1 and partes[1].lower() == "listar":
        return True
    if comando == "estoque" and len(partes) == 1:
        return True
    return False


def _descrever_comando(comando_texto: str) -> str:
    """Traduz o comando técnico (o que a IA devolve, ex: 'tempo_insulina_ativa 4')
    pra uma frase em português normal, pra mostrar na confirmação — o
    paciente nunca deveria ver um nome de comando com underscore."""
    partes = _normalizar_prefixo_multipalavra(comando_texto).strip().split()
    if not partes:
        return comando_texto
    comando = remover_acentos(partes[0].lower())
    args = partes[1:]

    if comando == "glicemia" and args:
        resto = " ".join(args[1:])
        return f"registrar sua glicemia em {args[0]}" + (f" ({resto})" if resto else "")
    if comando == "bolus" and len(args) >= 2:
        return f"calcular o bolus pra {args[0]} de carboidrato com glicemia {args[1]}"
    if comando == "apliquei" and args:
        return f"registrar que você aplicou {args[0]} de insulina"
    if comando == "tratei":
        return "confirmar que você tratou a hipoglicemia"
    if comando == "editar" and len(args) >= 2:
        return f"mudar seu(sua) {args[0]} pra {args[1]}"
    if comando == "modificador" and len(args) >= 2:
        return f"{args[0]} o modificador \"{' '.join(args[1:])}\""
    if comando == "tempo_insulina_ativa" and args:
        return f"configurar seu tempo de insulina ativa pra {args[0]} horas"
    if comando == "lembrete" and args:
        return f"{args[0]} lembrete" + (f" ({' '.join(args[1:])})" if len(args) > 1 else "")
    if comando == "cuidador" and args:
        return f"{args[0]} cuidador" + (f" ({' '.join(args[1:])})" if len(args) > 1 else "")
    if comando == "estoque" and args:
        return f"{args[0]} o estoque" + (f" ({' '.join(args[1:])})" if len(args) > 1 else "")
    return comando_texto


async def _tentar_sugestao_ia(usuario: dict, mensagem: str) -> str:
    """Último recurso quando nenhum comando bate: pede pra IA interpretar a
    mensagem em linguagem natural e traduzir pro comando certo. Comando
    seguro (só leitura) executa na hora; qualquer coisa que grava dado
    clínico ou é destrutiva ainda pede confirmação explícita antes."""
    sugestao = await ia.sugerir_comando(mensagem)
    if sugestao is None:
        return 'Não entendi. Pode falar do seu jeito (ex: "minha glicose deu 110") ou mandar *ajuda* pra ver a lista de comandos.'

    comando_sugerido = sugestao["comando"]

    if _comando_e_seguro(comando_sugerido):
        return await processar_comando(usuario, comando_sugerido)

    supabase.table("usuarios").update(
        {
            "sugestao_pendente": {
                "comando": comando_sugerido,
                "criado_em": datetime.now(timezone.utc).isoformat(),
            }
        }
    ).eq("id", usuario["id"]).execute()

    return (
        f"Você quis dizer: *{_descrever_comando(comando_sugerido)}*?\n"
        "Responde *sim* pra confirmar, ou *não* pra cancelar."
    )


async def _pedir_confirmacao_exclusao(usuario: dict) -> str:
    """Exclusão de conta (direito de eliminação da LGPD) exige confirmação
    explícita separada — apagar tudo por engano (ex: digitou o comando sem
    querer) não tem volta. Reaproveita o mesmo mecanismo de sugestão
    pendente + sim/não usado pra confirmar sugestão da IA."""
    supabase.table("usuarios").update(
        {
            "sugestao_pendente": {
                "comando": "confirmar_exclusao_conta",
                "criado_em": datetime.now(timezone.utc).isoformat(),
            }
        }
    ).eq("id", usuario["id"]).execute()

    return (
        "⚠️ *Isso apaga permanentemente todos os seus dados* — glicemias, "
        "doses, perfil, cuidadores, tudo. Não tem como desfazer.\n\n"
        "Responde *sim* pra confirmar, ou *não* pra cancelar."
    )


async def _excluir_conta(usuario: dict) -> str:
    """Apaga a conta de verdade — todas as tabelas referenciam usuarios com
    ON DELETE CASCADE, então um delete só aqui já limpa tudo (glicemias,
    bolus, perfil, cuidadores, sessões web, lembretes etc)."""
    supabase.table("usuarios").delete().eq("id", usuario["id"]).execute()
    return (
        "✅ Pronto — todos os seus dados foram apagados. Se quiser voltar a "
        "usar o bot, é só mandar uma mensagem que o cadastro começa de novo."
    )


class _SintaxeNaoReconhecida(Exception):
    """Levantada por um handler quando o primeiro token bate com um comando
    conhecido (ex: "apliquei"), mas o resto da frase não bate com o formato
    rígido esperado (ex: "apliquei 8 unidades" — "unidades" não é um
    horário válido). Em vez de mostrar um erro técnico de sintaxe, cai pra
    IA reinterpretar a frase inteira em linguagem natural — mais fácil pro
    paciente que só queria dizer "apliquei 8 unidades de insulina"."""


async def processar_comando(usuario: dict, mensagem: str) -> str:
    pendente = usuario.get("sugestao_pendente")
    if pendente:
        resposta_pendente = await _tratar_sugestao_pendente(usuario, mensagem, pendente)
        if resposta_pendente is not None:
            return resposta_pendente
        # não era confirmação (nem sugestão expirada) — segue o fluxo normal

    mensagem = _normalizar_prefixo_multipalavra(mensagem)
    partes = mensagem.strip().split()
    if not partes:
        return _ajuda()

    comando = remover_acentos(partes[0].lower())

    try:
        if comando in ("ajuda", "menu", "help"):
            return _ajuda()
        if comando in ("oi", "ola", "oii", "oie", "eae", "hey", "hello"):
            return _saudacao(usuario)
        if comando == "perfil":
            return await _perfil(usuario)
        if comando == "basal":
            return await _basal(usuario)
        if comando == "bolus":
            return await _bolus(usuario, partes[1:])
        if comando == "apliquei":
            return await _apliquei(usuario, partes[1:])
        if comando == "modificador":
            return await _modificador(usuario, partes[1:])
        if comando == "glicemia":
            return await _glicemia(usuario, partes[1:])
        if comando == "tratei":
            return await _tratei(usuario)
        if comando == "cuidador":
            return await _cuidador(usuario, partes[1:])
        if comando == "tempo_insulina_ativa":
            return await _tempo_insulina_ativa(usuario, partes[1:])
        if comando == "lembrete":
            return await _lembrete(usuario, partes[1:])
        if comando == "relatorio":
            return await _relatorio(usuario, partes[1:])
        if comando == "exportar":
            return await _exportar(usuario, partes[1:])
        if comando in ("hba1c", "gmi"):
            return await _hba1c(usuario, partes[1:])
        if comando == "editar":
            return await _editar(usuario, partes[1:])
        if comando in ("padroes", "padrao"):
            return await _padroes(usuario, partes[1:])
        if comando == "estoque":
            return await _estoque(usuario, partes[1:])
        if comando == "criar_senha":
            return auth_web.gerar_codigo_login(usuario["id"])
        if comando == "excluir_conta":
            return await _pedir_confirmacao_exclusao(usuario)
        if comando == "confirmar_exclusao_conta":
            return await _excluir_conta(usuario)

        # atalho: mandar só um número vale como registro de glicemia
        if len(partes) == 1 and parse_numero(comando) is not None:
            return await _glicemia(usuario, partes)
    except _SintaxeNaoReconhecida:
        return await _tentar_sugestao_ia(usuario, mensagem)

    return await _tentar_sugestao_ia(usuario, mensagem)


async def _glicemia(usuario: dict, args: list[str]) -> str:
    if not args:
        return "Manda o valor da sua glicemia. Tipo: *glicemia 110*"

    valor = parse_numero(args[0])
    if valor is None or valor <= 0:
        raise _SintaxeNaoReconhecida()

    contexto = "outro"
    if len(args) > 1:
        contexto = _normalizar_contexto(" ".join(args[1:]))
        if contexto is None:
            raise _SintaxeNaoReconhecida()

    nome = usuario.get("nome") or "Ele(a)"
    label_contexto = _CONTEXTO_LABEL.get(contexto)
    sufixo_contexto = f" ({label_contexto})" if label_contexto else ""
    linha_iob = await _linha_insulina_ativa(usuario["id"])

    if valor > LIMITE_EMERGENCIA:
        # Registra mesmo sendo emergência — e nesse caso os cuidadores
        # precisam saber IMEDIATAMENTE, sem esperar o ciclo normal de aviso.
        supabase.table("registros_glicemia").insert(
            {"usuario_id": usuario["id"], "valor": int(valor), "contexto": contexto}
        ).execute()
        await cuidadores.notificar_cuidadores(
            usuario["id"],
            f"🚨🚨 *Emergência* — a glicemia de {nome} está em *{valor:.0f} mg/dL*. "
            f"Procure ajuda imediatamente.{linha_iob}",
        )
        aviso_estoque_emergencia = await estoque.consumir(usuario["id"], "fita_dextro", 1)
        return _mensagem_emergencia(valor) + linha_iob + (aviso_estoque_emergencia or "")

    if valor < LIMITE_EMERGENCIA_BAIXO:
        # Mesma urgência do lado alto — hipoglicemia grave é tão ou mais
        # perigosa que hiperglicemia extrema, e matava mais rápido: registra,
        # avisa os cuidadores na hora, sem esperar o ciclo normal de aviso.
        supabase.table("registros_glicemia").insert(
            {"usuario_id": usuario["id"], "valor": int(valor), "contexto": contexto}
        ).execute()
        await cuidadores.notificar_cuidadores(
            usuario["id"],
            f"🚨🚨 *Emergência* — a glicemia de {nome} está em *{valor:.0f} mg/dL* "
            f"(hipoglicemia grave). Ajude a tratar agora.{linha_iob}",
        )
        aviso_estoque_emergencia = await estoque.consumir(usuario["id"], "fita_dextro", 1)
        return _mensagem_emergencia_baixa(valor) + linha_iob + (aviso_estoque_emergencia or "")

    supabase.table("registros_glicemia").insert(
        {"usuario_id": usuario["id"], "valor": int(valor), "contexto": contexto}
    ).execute()
    aviso_estoque = await estoque.consumir(usuario["id"], "fita_dextro", 1)

    resposta = f"🩸 Glicemia registrada: *{valor:.0f} mg/dL*{sufixo_contexto}.{linha_iob}"

    alerta = await checar_alerta_glicemia(usuario, valor)

    # Se depende de confirmação do paciente (tratar hipo / aplicar correção),
    # só avisa os cuidadores na confirmação ou no escalonamento
    # (confirmacoes.verificar_pendentes) — nunca na hora, pra não avisar duas vezes.
    aguardando_confirmacao = False

    if alerta and alerta["tipo"] == "hipoglicemia":
        if alerta["novo"]:
            resposta += "\n\n" + await _bloco_hipoglicemia(valor, alerta["limite"])
            await remedicao.agendar(usuario["id"], "hipoglicemia")
        else:
            # Dentro da janela de throttle (15min) — já mostrou o cartão
            # completo com dicas na leitura anterior, não repete de novo.
            resposta += "\n\nQuando tratar, me conta com *tratei*."
        await confirmacoes.criar_confirmacao(usuario["id"], "hipoglicemia", valor)
        aguardando_confirmacao = True
    else:
        if alerta and alerta["tipo"] == "hiperglicemia" and alerta["novo"]:
            # Mesma ideia da hipoglicemia: agenda um lembrete de remedir mais
            # à frente (60min, não 15 — ver remedicao.py) pra ver a
            # tendência, independente de ter sugerido dose de correção.
            await remedicao.agendar(usuario["id"], "hiperglicemia")
        # Sugere correção sempre que estiver acima da meta, não só acima do
        # limite alto/crítico.
        correcao = await calcular_correcao(usuario["id"], valor)
        if correcao and correcao["dose_final"] > 0:
            if alerta and alerta["novo"]:
                resposta += "\n\n" + await _bloco_hiperglicemia(valor, correcao)
            else:
                resposta += (
                    f"\n\n💉 *Correção sugerida*\n\n"
                    f"> {correcao['explicacao'].replace(chr(10), chr(10) + '> ')}\n\n"
                    "Depois que aplicar, me conta com *apliquei <dose>*."
                )
            await confirmacoes.criar_confirmacao(
                usuario["id"], "hiperglicemia", valor,
                dose_sugerida=correcao["dose_final"], registro_bolus_id=correcao.get("registro_id"),
            )
            aguardando_confirmacao = True
        elif correcao:
            resposta += (
                f"\n\n💉 *Correção sugerida*\n\n"
                f"> {correcao['explicacao'].replace(chr(10), chr(10) + '> ')}\n\n"
                "Sua insulina ativa ainda cobre a correção — não precisa aplicar mais agora."
            )

    if not aguardando_confirmacao:
        await cuidadores.notificar_cuidadores(
            usuario["id"], f"📊 Glicemia de {nome}: *{valor:.0f} mg/dL*{sufixo_contexto}.{linha_iob}"
        )

    return resposta + (aviso_estoque or "")


async def _linha_insulina_ativa(usuario_id: str) -> str:
    """Retorna '\\n💧 Insulina ativa: X.XU' se o paciente configurou tempo_insulina_ativa, senão ''."""
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data
    if not perfis or not perfis[0].get("tempo_insulina_ativa_horas"):
        return ""

    insulina_ativa = await calcular_insulina_ativa(usuario_id, perfis[0]["tempo_insulina_ativa_horas"])
    return f"\n💧 Insulina ativa: {insulina_ativa:.1f}U"


async def _bolus(usuario: dict, args: list[str]) -> str:
    if len(args) < 2:
        return "Manda os carboidratos e a glicemia atual. Tipo: *bolus 40g 130*"

    carboidratos = parse_numero(args[0])
    glicemia = parse_numero(args[1])

    if carboidratos is None or carboidratos < 0:
        return "Não entendi a quantidade de carboidratos. Tipo: *bolus 40g 130*"
    if glicemia is None or glicemia <= 0:
        return "Não entendi o valor da glicemia. Tipo: *bolus 40g 130*"
    if glicemia > LIMITE_EMERGENCIA:
        return _mensagem_emergencia(glicemia)
    if glicemia < LIMITE_EMERGENCIA_BAIXO:
        nome = usuario.get("nome") or "Ele(a)"
        await cuidadores.notificar_cuidadores(
            usuario["id"],
            f"🚨🚨 *Emergência* — a glicemia de {nome} está em *{glicemia:.0f} mg/dL* "
            "(hipoglicemia grave). Ajude a tratar agora.",
        )
        return _mensagem_emergencia_baixa(glicemia)

    agora = agora_usuario(usuario.get("timezone") or "America/Sao_Paulo")
    resultado = await calcular_e_registrar_bolus(usuario["id"], carboidratos, glicemia, agora)

    if "erro" in resultado:
        return resultado["erro"]
    if resultado["hipo"]:
        return resultado["explicacao"]

    quote = "> " + resultado["explicacao"].replace("\n", "\n> ")

    if resultado["dose_final"] <= 0:
        return f"💉 *Cálculo de bolus*\n\n{quote}\n\nNão precisa aplicar nada agora."

    return f"💉 *Cálculo de bolus*\n\n{quote}\n\nDepois que aplicar, me conta com *apliquei <dose>*."


_CONECTORES_HORARIO = ("as", "às", "hs")

# Palavras que um paciente naturalmente adiciona depois da dose (ex:
# "apliquei 8 unidades", "apliquei 8 unidades de insulina") e que não mudam
# o sentido do comando — ignoradas antes de tentar interpretar o resto como
# horário.
_PALAVRAS_IGNORAVEIS_DOSE = ("unidade", "unidades", "u", "de", "insulina")


async def _apliquei(usuario: dict, args: list[str]) -> str:
    if not args:
        return (
            "Manda quantas unidades você aplicou. Tipo: *apliquei 4u*\n"
            "Esqueceu de avisar na hora? Manda o horário junto: *apliquei 6u 12:20*"
        )

    dose = parse_numero(args[0])
    if dose is None or dose < 0:
        raise _SintaxeNaoReconhecida()

    tz = usuario.get("timezone") or "America/Sao_Paulo"
    # Ignora palavras soltas comuns que não mudam o sentido (ex: "apliquei 8
    # unidades", "apliquei 8 unidades de insulina") — só o que sobra depois
    # disso é candidato a horário.
    resto = [
        t for t in args[1:]
        if remover_acentos(t.lower()) not in _CONECTORES_HORARIO
        and remover_acentos(t.lower()) not in _PALAVRAS_IGNORAVEIS_DOSE
    ]

    # Retroativo: sem o horário real, o IOB contaria o decaimento a partir de agora.
    horario_aplicacao = None
    retroativo = False
    if resto:
        hora = parse_hora(resto[0])
        if hora is None:
            raise _SintaxeNaoReconhecida()
        agora_local = agora_usuario(tz)
        candidato_local = agora_local.replace(hour=hora.hour, minute=hora.minute, second=0, microsecond=0)
        if candidato_local > agora_local:
            return "Esse horário ainda não chegou hoje — só dá pra registrar retroativo um horário que já passou."
        horario_aplicacao = candidato_local.astimezone(timezone.utc)
        retroativo = True

    registro = await registrar_dose_aplicada(usuario["id"], dose, horario_aplicacao)

    # Resolve o ciclo de confirmação pendente, se houver, pra não escalar pros cuidadores depois.
    confirmado = await confirmacoes.confirmar_por_registro_bolus(registro["id"])
    if confirmado and not confirmado["cuidadores_notificados"]:
        await confirmacoes.marcar_cuidadores_notificados(confirmado["id"])

    nome = usuario.get("nome") or "Ele(a)"
    hora = formatar_hora_local(registro["horario_aplicacao"], tz)
    sufixo_titulo = " (retroativa)" if retroativo else ""
    # Sem cálculo prévio do bot (dose avulsa), não tem glicemia de
    # referência — omite a linha em vez de mostrar "None".
    linha_glicemia = (
        f"🩸 Referente à glicemia de *{registro['glicemia_referencia']} mg/dL*\n"
        if registro.get("glicemia_referencia") is not None
        else ""
    )
    linha_iob = await _linha_insulina_ativa(usuario["id"])

    # Manda pra cuidadores sempre, não só nos casos críticos.
    texto_cuidadores = (
        f"✅ *{nome} aplicou insulina{sufixo_titulo}*\n\n"
        f"🕐 {hora}\n"
        f"💉 *{dose:.1f}U*\n"
        f"{linha_glicemia}"
    ).rstrip()
    await cuidadores.notificar_cuidadores(usuario["id"], texto_cuidadores)

    aviso_estoque = await estoque.consumir(usuario["id"], "insulina", dose)
    resposta = (
        f"✅ *Dose aplicada{sufixo_titulo}*\n\n"
        f"🕐 {hora}\n"
        f"💉 *{dose:.1f}U* de insulina\n"
        f"{linha_glicemia}"
    ).rstrip()
    return resposta + linha_iob + (aviso_estoque or "")


async def _tratei(usuario: dict) -> str:
    confirmado = await confirmacoes.confirmar_hipoglicemia(usuario["id"])
    if confirmado is None:
        return "Não achei nenhuma hipoglicemia pendente de confirmação."

    nome = usuario.get("nome") or "Ele(a)"
    tz = usuario.get("timezone") or "America/Sao_Paulo"
    hora = formatar_hora_local(datetime.now(timezone.utc).isoformat(), tz)

    if not confirmado["cuidadores_notificados"]:
        await confirmacoes.marcar_cuidadores_notificados(confirmado["id"])
        texto = (
            f"💙 *{nome} tratou a hipoglicemia*\n\n"
            f"🕐 {hora}\n"
            f"🩸 Estava em *{confirmado['valor_glicemia']} mg/dL*"
        )
        await cuidadores.notificar_cuidadores(usuario["id"], texto)

    return (
        f"💙 *Hipoglicemia tratada*\n\n"
        f"🕐 {hora}\n"
        f"🩸 Estava em *{confirmado['valor_glicemia']} mg/dL*\n\n"
        "Fico tranquilo. 👍"
    )


async def _perfil(usuario: dict) -> str:
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario["id"]).execute().data
    if not perfis:
        return "Ainda não achei seu perfil glicêmico — algo deu errado no cadastro."
    perfil = perfis[0]

    relacoes = supabase.table("relacao_ic").select("*").eq("usuario_id", usuario["id"]).execute().data

    tempo_iob = (
        f"• Tempo de insulina ativa: *{perfil['tempo_insulina_ativa_horas']:.1f}h*"
        if perfil.get("tempo_insulina_ativa_horas")
        else "• Tempo de insulina ativa: _não configurado_ (*tempo_insulina_ativa <horas>*)"
    )
    linhas = [
        f"📋 *Perfil de {usuario.get('nome') or 'você'}*",
        "",
        f"• Meta: *{perfil['meta_glicemia']} mg/dL*",
        f"• Faixa alvo: *{perfil['limite_baixo']}–{perfil['limite_alto']} mg/dL*",
        f"• Fator de sensibilidade: *{perfil['fator_sensibilidade']} mg/dL por U*",
        tempo_iob,
        "",
        "*Relação insulina:carboidrato*",
    ]
    for r in relacoes:
        linhas.append(
            f"• {r['periodo']} ({str(r['hora_inicio'])[:5]}–{str(r['hora_fim'])[:5]}): "
            f"*{r['gramas_por_unidade']}g/U*"
        )

    modificadores = (
        supabase.table("modificadores_bolus").select("*").eq("usuario_id", usuario["id"]).execute().data
    )
    if modificadores:
        linhas.append("")
        linhas.append("*Modificadores*")
        for m in modificadores:
            status = "ativo" if m["ativo"] else "inativo"
            sinal = "+" if m["valor_ajuste"] >= 0 else ""
            unidade = "%" if m["tipo_ajuste"] == "percentual" else "U"
            linhas.append(f"• {m['nome']}: *{sinal}{m['valor_ajuste']}{unidade}* ({status})")

    return "\n".join(linhas)


async def _basal(usuario: dict) -> str:
    registros = (
        supabase.table("basal")
        .select("*")
        .eq("usuario_id", usuario["id"])
        .eq("ativo", True)
        .order("horario")
        .execute()
        .data
    )
    if not registros:
        return "⏰ Você ainda não tem horários de basal cadastrados."

    linhas = ["⏰ *Insulina basal*", ""]
    for b in registros:
        tipo = f" ({b['tipo_insulina']})" if b["tipo_insulina"] else ""
        linhas.append(f"• {str(b['horario'])[:5]} — *{b['dose']}U*{tipo}")
    return "\n".join(linhas)


async def _modificador(usuario: dict, args: list[str]) -> str:
    if len(args) < 2 or remover_acentos(args[0].lower()) not in ("ativar", "desativar"):
        return "Manda assim: *modificador ativar <nome>* ou *modificador desativar <nome>*"

    acao = remover_acentos(args[0].lower())
    nome = " ".join(args[1:])

    modificadores = (
        supabase.table("modificadores_bolus").select("*").eq("usuario_id", usuario["id"]).execute().data
    )
    alvo = next((m for m in modificadores if m["nome"].lower() == nome.lower()), None)
    if alvo is None:
        nomes = ", ".join(m["nome"] for m in modificadores) or "nenhum cadastrado ainda"
        return f'Não achei o modificador "{nome}". Cadastrados: {nomes}'

    novo_status = acao == "ativar"
    supabase.table("modificadores_bolus").update({"ativo": novo_status}).eq("id", alvo["id"]).execute()
    return f"✅ *{alvo['nome']}* {'ativado' if novo_status else 'desativado'}."


async def _cuidador(usuario: dict, args: list[str]) -> str:
    if not args:
        return "Manda: *cuidador convidar*, *cuidador listar* ou *cuidador remover <nome>*"

    acao = remover_acentos(args[0].lower())

    if acao in ("convidar", "adicionar"):
        return await cuidadores.gerar_convite(usuario["id"])
    if acao == "listar":
        return await cuidadores.listar_cuidadores(usuario["id"])
    if acao == "remover" and len(args) > 1:
        return await cuidadores.remover_cuidador(usuario["id"], " ".join(args[1:]))

    return "Manda: *cuidador convidar*, *cuidador listar* ou *cuidador remover <nome>*"


_CAMPOS_EDITAVEIS = {"meta": "meta_glicemia", "limite_baixo": "limite_baixo", "limite_alto": "limite_alto", "fator": "fator_sensibilidade"}

# aceita tanto "limite_baixo" (uma palavra) quanto "limite baixo" (duas
# palavras, como aparece no texto de ajuda)
_ALIASES_CAMPO_EDITAVEL = {
    "limite baixo": "limite_baixo",
    "limite alto": "limite_alto",
}


def _resolver_campo_editar(args: list[str]) -> tuple[str | None, list[str]]:
    primeiro = remover_acentos(args[0].lower())
    if primeiro == "nome":
        return "nome", args[1:]
    if primeiro in _CAMPOS_EDITAVEIS:
        return primeiro, args[1:]
    if len(args) >= 2:
        duas_palavras = f"{primeiro} {remover_acentos(args[1].lower())}"
        if duas_palavras in _ALIASES_CAMPO_EDITAVEL:
            return _ALIASES_CAMPO_EDITAVEL[duas_palavras], args[2:]
    return None, args


async def _editar(usuario: dict, args: list[str]) -> str:
    if len(args) < 2:
        return (
            "Manda: *editar <campo> <valor>*\n"
            "Campos: *meta*, *limite baixo*, *limite alto*, *fator*, *nome*\n"
            "Tipo: *editar meta 110*"
        )

    campo, resto = _resolver_campo_editar(args)
    if campo is None:
        return "Campo não reconhecido. Use: *meta*, *limite baixo*, *limite alto*, *fator* ou *nome*."
    if not resto:
        return "Manda o novo valor também. Tipo: *editar meta 110*"
    valor_texto = " ".join(resto)

    if campo == "nome":
        novo_nome = valor_texto.strip()
        if not novo_nome:
            return "Manda o novo nome. Tipo: *editar nome João Silva*"
        supabase.table("usuarios").update({"nome": novo_nome}).eq("id", usuario["id"]).execute()
        return f"✅ Nome atualizado pra *{novo_nome}*."

    valor = parse_numero(valor_texto)
    if valor is None:
        return f"Manda um número válido. Tipo: *editar {campo.replace('_', ' ')} 110*"

    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario["id"]).execute().data
    if not perfis:
        return "Ainda não achei seu perfil glicêmico — algo deu errado no cadastro."
    perfil = perfis[0]
    meta_atual = perfil["meta_glicemia"]

    if campo == "meta":
        if not (40 <= valor <= 300):
            return "A meta precisa estar entre 40 e 300 mg/dL."
        if not (perfil["limite_baixo"] < valor < perfil["limite_alto"]):
            return (
                f"Essa meta não é compatível com seus limites atuais "
                f"({perfil['limite_baixo']}-{perfil['limite_alto']} mg/dL). "
                "Ajusta os limites primeiro (*editar limite baixo* / *editar limite alto*), "
                "ou escolhe uma meta entre eles."
            )
    elif campo == "limite_baixo":
        if not (0 < valor < meta_atual):
            return f"O limite baixo precisa ser um número menor que sua meta ({meta_atual} mg/dL)."
    elif campo == "limite_alto":
        if valor <= meta_atual:
            return f"O limite alto precisa ser um número maior que sua meta ({meta_atual} mg/dL)."
    elif campo == "fator":
        if valor <= 0:
            return "O fator de sensibilidade precisa ser maior que zero."

    coluna = _CAMPOS_EDITAVEIS[campo]
    supabase.table("perfil_glicemico").update({coluna: int(valor)}).eq("id", perfil["id"]).execute()
    return f"✅ *{campo.replace('_', ' ')}* atualizado pra *{int(valor)}*."


async def _tempo_insulina_ativa(usuario: dict, args: list[str]) -> str:
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario["id"]).execute().data
    if not perfis:
        return "Ainda não achei seu perfil glicêmico — algo deu errado no cadastro."
    perfil = perfis[0]

    if not args:
        atual = perfil.get("tempo_insulina_ativa_horas")
        if atual:
            return f"Seu tempo de insulina ativa está em *{atual:.1f}h*. Pra mudar: *tempo insulina ativa 4*"
        return (
            "Você ainda não configurou o tempo de insulina ativa — enquanto isso, "
            "o cálculo de bolus não desconta insulina residual. Pra configurar: "
            "*tempo insulina ativa 4* (pergunte pro seu médico quantas horas usar)."
        )

    valor = parse_numero(args[0])
    if valor is None or not (1 <= valor <= 8):
        return "Manda um número de horas entre 1 e 8. Tipo *tempo insulina ativa 4*"

    supabase.table("perfil_glicemico").update({"tempo_insulina_ativa_horas": valor}).eq("id", perfil["id"]).execute()
    return f"✅ Tempo de insulina ativa atualizado pra *{valor:.1f}h*."


_TIPOS_LEMBRETE = {
    "medir_glicemia": "medir glicemia",
    "aplicar_basal": "aplicar basal",
    "aplicar_bolus": "aplicar bolus",
    "outro": "outro",
}

_TIPOS_LEMBRETE_ENTRADA = {
    "glicemia": "medir_glicemia",
    "medir": "medir_glicemia",
    "medir_glicemia": "medir_glicemia",
    "basal": "aplicar_basal",
    "aplicar_basal": "aplicar_basal",
    "bolus": "aplicar_bolus",
    "aplicar_bolus": "aplicar_bolus",
    "outro": "outro",
}


async def _lembrete(usuario: dict, args: list[str]) -> str:
    uso = "Manda: *lembrete listar*, *lembrete adicionar <horario> [glicemia|basal|bolus]* ou *lembrete remover <horario>*"
    if not args:
        return uso

    acao = remover_acentos(args[0].lower())

    if acao == "listar":
        return await _lembrete_listar(usuario)
    if acao == "adicionar" and len(args) > 1:
        tipo_texto = args[2] if len(args) > 2 else None
        return await _lembrete_adicionar(usuario, args[1], tipo_texto)
    if acao == "remover" and len(args) > 1:
        return await _lembrete_remover(usuario, args[1])

    return uso


async def _lembrete_listar(usuario: dict) -> str:
    lembretes = (
        supabase.table("lembretes")
        .select("*")
        .eq("usuario_id", usuario["id"])
        .eq("ativo", True)
        .order("horario")
        .execute()
        .data
    )
    if not lembretes:
        return "⏰ Você não tem lembretes ativos. Manda *lembrete adicionar <horario>* pra criar um."

    linhas = ["⏰ *Seus lembretes*", ""]
    for l in lembretes:
        tipo = _TIPOS_LEMBRETE.get(l["tipo"], l["tipo"])
        linhas.append(f"• {str(l['horario'])[:5]} — {tipo}")
    return "\n".join(linhas)


async def _lembrete_adicionar(usuario: dict, horario_texto: str, tipo_texto: str | None) -> str:
    hora = parse_hora(horario_texto)
    if hora is None:
        return "Manda o horário no formato HH:MM. Tipo *lembrete adicionar 08:00*"

    tipo = "medir_glicemia"
    if tipo_texto:
        chave = remover_acentos(tipo_texto.lower())
        if chave not in _TIPOS_LEMBRETE_ENTRADA:
            return "Tipo não reconhecido. Use *glicemia*, *basal*, *bolus* ou *outro*."
        tipo = _TIPOS_LEMBRETE_ENTRADA[chave]

    supabase.table("lembretes").insert(
        {"usuario_id": usuario["id"], "tipo": tipo, "horario": hora.isoformat()}
    ).execute()
    label = _TIPOS_LEMBRETE.get(tipo, tipo)
    return f"✅ Lembrete de *{label}* criado pras *{hora.strftime('%H:%M')}*."


async def _lembrete_remover(usuario: dict, horario_texto: str) -> str:
    hora = parse_hora(horario_texto)
    if hora is None:
        return "Manda o horário no formato HH:MM. Tipo *lembrete remover 08:00*"

    lembretes = (
        supabase.table("lembretes").select("*").eq("usuario_id", usuario["id"]).eq("ativo", True).execute().data
    )
    alvo = next((l for l in lembretes if str(l["horario"])[:5] == hora.strftime("%H:%M")), None)
    if alvo is None:
        return f"Não achei nenhum lembrete ativo às {hora.strftime('%H:%M')}."

    supabase.table("lembretes").update({"ativo": False}).eq("id", alvo["id"]).execute()
    return f"✅ Lembrete das *{hora.strftime('%H:%M')}* removido."


async def _relatorio(usuario: dict, args: list[str]) -> str:
    periodo = "semana"
    if args:
        arg = remover_acentos(args[0].lower())
        if arg in ("semana", "semanal"):
            periodo = "semana"
        elif arg in ("mes", "mensal"):
            periodo = "mes"
        else:
            return "Manda *relatorio semana* ou *relatorio mes*."

    relatorio = await gerar_relatorio(usuario["id"], periodo)
    if relatorio is None:
        return "Ainda não achei seu perfil glicêmico — algo deu errado no cadastro."
    return relatorio


async def _exportar(usuario: dict, args: list[str]) -> str:
    dias = EXPORTAR_DIAS_PADRAO
    if args:
        valor = parse_numero(args[0])
        if valor is None or valor <= 0:
            return (
                f"Manda o número de dias. Tipo: *exportar 90* "
                f"(padrão é {EXPORTAR_DIAS_PADRAO}, máximo {EXPORTAR_DIAS_MAXIMO})"
            )
        dias = min(int(valor), EXPORTAR_DIAS_MAXIMO)

    pdf_bytes = await gerar_pdf_historico(usuario["id"], dias)
    if pdf_bytes is None:
        return "Ainda não achei seu perfil glicêmico — algo deu errado no cadastro."

    nome_arquivo = f"glicia_historico_{dias}dias.pdf"
    await enviar_arquivo(usuario["telefone"], nome_arquivo, "application/pdf", pdf_bytes)
    return f"📄 Prontinho — mandei o PDF com seu histórico dos últimos *{dias} dias*."


async def _hba1c(usuario: dict, args: list[str]) -> str:
    dias = HBA1C_DIAS_PADRAO
    if args:
        valor = parse_numero(args[0])
        if valor is None or valor <= 0:
            return f"Manda o número de dias. Tipo: *hba1c 90* (padrão é {HBA1C_DIAS_PADRAO})"
        dias = int(valor)

    estimativa = await gerar_estimativa(usuario["id"], dias)
    if estimativa is None:
        return (
            f"Ainda não tenho medições suficientes nos últimos {dias} dias pra "
            "uma estimativa confiável. Continue registrando suas glicemias."
        )
    return formatar_estimativa(estimativa)


async def _padroes(usuario: dict, args: list[str]) -> str:
    dias = PADROES_DIAS_PADRAO
    if args:
        valor = parse_numero(args[0])
        if valor is None or valor <= 0:
            return f"Manda o número de dias. Tipo: *padroes 60* (padrão é {PADROES_DIAS_PADRAO})"
        dias = int(valor)

    padroes = await detectar_padroes(usuario["id"], dias)
    return formatar_padroes(padroes, dias)


async def _estoque(usuario: dict, args: list[str]) -> str:
    uso = (
        "Manda: *estoque* (ver níveis), *estoque configurar <tipo> <quantidade> [limite]* "
        "ou *estoque reabastecer <tipo> [quantidade]*.\nTipos: *insulina*, *fita* (dextro)."
    )
    if not args:
        return await _estoque_listar(usuario)

    acao = remover_acentos(args[0].lower())
    if acao == "configurar" and len(args) >= 2:
        return await _estoque_configurar(args[1], args[2:], usuario)
    if acao in ("reabastecer", "repor") and len(args) >= 2:
        return await _estoque_reabastecer(args[1], args[2:], usuario)

    return uso


async def _estoque_listar(usuario: dict) -> str:
    linhas = await estoque.listar(usuario["id"])
    if not linhas:
        return (
            "💊 Você ainda não configurou nenhum estoque.\n"
            "Tipo: *estoque configurar insulina 300* ou *estoque configurar fita 50*."
        )

    partes = ["💊 *Seu estoque*", ""]
    for linha in linhas:
        label = estoque.TIPOS.get(linha["tipo"], linha["tipo"])
        atual = max(0.0, float(linha["quantidade_atual"]))
        emoji = "🔴" if atual <= linha["limite_alerta"] else "🟢"
        partes.append(f"{emoji} {label}: *{atual:.0f} / {linha['quantidade_por_reposicao']:.0f}*")
    return "\n".join(partes)


async def _estoque_configurar(tipo_texto: str, resto: list[str], usuario: dict) -> str:
    tipo = estoque.TIPOS_ENTRADA.get(remover_acentos(tipo_texto.lower()))
    if tipo is None:
        return "Tipo não reconhecido. Use *insulina* ou *fita* (dextro)."

    quantidade = parse_numero(resto[0]) if resto else None
    if quantidade is None or quantidade <= 0:
        return f"Manda a quantidade por reposição. Tipo: *estoque configurar {tipo_texto} 300*"

    limite = parse_numero(resto[1]) if len(resto) > 1 else None
    if limite is None or limite < 0:
        limite = round(quantidade * estoque.FRACAO_LIMITE_PADRAO, 1)

    await estoque.configurar(usuario["id"], tipo, quantidade, limite)

    label = estoque.TIPOS[tipo]
    gatilho = "dose aplicada (*apliquei*)" if tipo == "insulina" else "glicemia registrada"
    return (
        f"✅ *{label}* configurado\n\n"
        f"• Quantidade por reposição: *{quantidade:.0f}*\n"
        f"• Aviso quando restar menos de: *{limite:.0f}*\n\n"
        f"A partir de agora eu desconto automaticamente a cada {gatilho}."
    )


async def _estoque_reabastecer(tipo_texto: str, resto: list[str], usuario: dict) -> str:
    tipo = estoque.TIPOS_ENTRADA.get(remover_acentos(tipo_texto.lower()))
    if tipo is None:
        return "Tipo não reconhecido. Use *insulina* ou *fita* (dextro)."

    linha = await estoque.buscar(usuario["id"], tipo)
    if linha is None:
        return (
            f"Você ainda não configurou o estoque de {estoque.TIPOS[tipo].lower()}. "
            f"Tipo: *estoque configurar {tipo_texto} 300*"
        )

    quantidade = parse_numero(resto[0]) if resto else linha["quantidade_por_reposicao"]
    if quantidade is None or quantidade <= 0:
        return "Manda uma quantidade válida."

    await estoque.reabastecer(usuario["id"], tipo, quantidade)
    return f"✅ *{estoque.TIPOS[tipo]}* reabastecido: *{quantidade:.0f}* disponíveis."


def _saudacao(usuario: dict) -> str:
    primeiro_nome = usuario["nome"].split()[0] if usuario.get("nome") else None
    abertura = f"👋 *Oi, {primeiro_nome}!*" if primeiro_nome else "👋 *Oi!*"
    return f"{abertura}\n\n{_ajuda()}"


def _ajuda() -> str:
    return (
        "📖 *Aqui está tudo o que eu sei fazer:*\n\n"
        "Pode falar do seu jeito, tipo _\"minha glicose deu 110 em jejum\"_ ou "
        "_\"tomei 4 unidades\"_ — eu entendo. Se preferir os comandos certinhos, "
        "aqui está a lista:\n\n"
        "*Registro do dia a dia*\n"
        "🩸 *glicemia 110* — registra uma medição (pode incluir o contexto: "
        "jejum, pre_refeicao, pos_prandial, correcao). Se estiver fora da sua "
        "faixa, eu aviso e, se for alta, já sugiro a dose de correção.\n"
        "💉 *bolus 40g 130* — calcula a dose de bolus (carboidratos em gramas e glicemia atual)\n"
        "✅ *apliquei 4u* — registra a dose que você realmente aplicou (esqueceu de avisar na "
        "hora? manda o horário junto: *apliquei 4u 12:20*)\n"
        "🍬 *tratei* — confirma que tratou uma hipoglicemia\n\n"
        "*Perfil e ajustes*\n"
        "📋 *perfil* — mostra seus dados cadastrados\n"
        "✏️ *editar <campo> <valor>* — muda meta, limite baixo, limite alto, fator ou "
        "nome sem precisar refazer o cadastro (tipo *editar meta 110*)\n"
        "⏰ *basal* — mostra seus horários de basal\n"
        "🔁 *modificador ativar/desativar <nome>* — liga ou desliga um modificador de bolus\n"
        "⏳ *tempo insulina ativa <horas>* — configura quanto tempo a insulina ainda age no corpo\n\n"
        "*Lembretes e relatórios*\n"
        "⏰ *lembrete listar/adicionar/remover <horario>* — gerencia seus lembretes "
        "(pode escolher o tipo: *lembrete adicionar 08:00 basal*)\n"
        "📅 *relatorio semana/mes* — resumo de glicemia e insulina do período "
        "(também mandado automaticamente todo domingo à noite e todo dia 1)\n"
        "📄 *exportar [dias]* — manda um PDF com seu histórico completo, pra levar "
        "na consulta (padrão 90 dias, tipo *exportar 90*)\n"
        "🩺 *hba1c [dias]* — estimativa de HbA1c/GMI a partir das suas medições\n"
        "🔍 *padroes [dias]* — detecta se algum dia da semana/período costuma vir alto ou baixo\n\n"
        "💊 *estoque* — controle de insulina e fitas de dextro, com desconto automático a cada "
        "*apliquei*/*glicemia* e aviso quando tá acabando (configura com *estoque configurar "
        "insulina 300* ou *estoque configurar fita 50*)\n\n"
        "🔑 *criar senha* — gera um código pra você acessar o site de acompanhamento "
        "(glicia.pedrotx.com.br) com CPF e senha\n"
        "🗑️ *excluir conta* — apaga permanentemente todos os seus dados (pede confirmação antes)\n\n"
        "👨‍👩‍👧 *Quem acompanha sua glicemia*\n"
        "Pra convidar alguém (esposa, mãe etc): manda *cuidador convidar*, eu te dou um "
        "código de 6 dígitos válido por 30 min. Repassa esse código pra pessoa, e ela "
        "manda pra mim, nesse mesmo número: *vincular <código> <nome dela>*. A partir "
        "daí, quando precisar de correção ou tratar uma hipo, eu só aviso ela quando "
        "você confirmar (*apliquei*/*tratei*) — se você não confirmar em 15 minutos "
        "(eu te lembro 2 vezes antes disso), ela recebe um aviso automático.\n"
        "• *cuidador listar* — vê quem já acompanha você\n"
        "• *cuidador remover <nome>* — tira alguém da lista\n\n"
        "Se eu não reconhecer o que você mandou, eu tento adivinhar — pra "
        "coisa simples (ver perfil, relatório etc) eu já faço na hora; pra "
        "qualquer coisa que grava dado (glicemia, dose, perfil) ou é "
        "irreversível (excluir conta), eu sempre confirmo antes com você.\n\n"
        "Pode mandar *ajuda* ou *oi* sempre que quiser ver essa lista de novo."
    )
