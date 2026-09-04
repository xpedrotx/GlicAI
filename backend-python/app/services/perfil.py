"""
Leitura/edição de perfil pro dashboard web (site de acompanhamento) —
mesmas regras de validação do comando `editar`/`tempo_insulina_ativa` no
WhatsApp (ver comandos.py), só que devolvendo erro estruturado em vez de
texto de chat pronto. A mensagem de erro em si é a mesma — funciona bem
também como texto de validação de formulário na tela.
"""
from app.services.supabase_client import supabase

# nome do campo (igual ao usado no formulário/API) -> também é o nome da
# coluna real em perfil_glicemico, exceto "nome" que é especial (vai pra
# usuarios, não perfil_glicemico).
CAMPOS_PERFIL = {
    "meta_glicemia",
    "limite_baixo",
    "limite_alto",
    "fator_sensibilidade",
    "tempo_insulina_ativa_horas",
}


class ErroValidacaoPerfil(Exception):
    """Erro esperado (valor fora da regra) — a mensagem já é a que o usuário deve ver."""


async def buscar_perfil_completo(usuario_id: str) -> dict | None:
    """
    Perfil + listas relacionadas (relação IC, basal, modificadores) — mesmo
    dado que _perfil()/_basal() do WhatsApp mostram em texto (comandos.py),
    aqui em formato estruturado pro dashboard. None se o cadastro não
    estiver completo.
    """
    usuarios = supabase.table("usuarios").select("*").eq("id", usuario_id).execute().data
    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data
    if not usuarios or not perfis:
        return None

    relacoes = (
        supabase.table("relacao_ic").select("*").eq("usuario_id", usuario_id).order("hora_inicio").execute().data
    )
    basal = (
        supabase.table("basal")
        .select("*")
        .eq("usuario_id", usuario_id)
        .eq("ativo", True)
        .order("horario")
        .execute()
        .data
    )
    modificadores = supabase.table("modificadores_bolus").select("*").eq("usuario_id", usuario_id).execute().data

    return {
        "nome": usuarios[0].get("nome"),
        "perfil": perfis[0],
        "relacoes_ic": relacoes,
        "basal": basal,
        "modificadores": modificadores,
    }


async def atualizar_nome(usuario_id: str, novo_nome: str) -> None:
    novo_nome = novo_nome.strip()
    if not novo_nome:
        raise ErroValidacaoPerfil("Nome não pode ficar vazio.")
    supabase.table("usuarios").update({"nome": novo_nome}).eq("id", usuario_id).execute()


async def atualizar_campo_perfil(usuario_id: str, campo: str, valor: float) -> None:
    """
    Valida e atualiza um campo numérico do perfil glicêmico. Mesmas regras
    de comandos.py (_editar/_tempo_insulina_ativa): meta entre 40-300 e
    dentro dos limites atuais, limite_baixo < meta, limite_alto > meta,
    fator > 0, tempo de insulina ativa entre 1 e 8h.
    """
    if campo not in CAMPOS_PERFIL:
        raise ErroValidacaoPerfil("Campo não reconhecido.")

    perfis = supabase.table("perfil_glicemico").select("*").eq("usuario_id", usuario_id).execute().data
    if not perfis:
        raise ErroValidacaoPerfil("Perfil não encontrado.")
    perfil = perfis[0]
    meta_atual = perfil["meta_glicemia"]

    if campo == "meta_glicemia":
        if not (40 <= valor <= 300):
            raise ErroValidacaoPerfil("A meta precisa estar entre 40 e 300 mg/dL.")
        if not (perfil["limite_baixo"] < valor < perfil["limite_alto"]):
            raise ErroValidacaoPerfil(
                "Essa meta não é compatível com seus limites atuais "
                f"({perfil['limite_baixo']}-{perfil['limite_alto']} mg/dL). "
                "Ajusta os limites primeiro, ou escolhe uma meta entre eles."
            )
    elif campo == "limite_baixo":
        if not (0 < valor < meta_atual):
            raise ErroValidacaoPerfil(f"O limite baixo precisa ser um número menor que sua meta ({meta_atual} mg/dL).")
    elif campo == "limite_alto":
        if valor <= meta_atual:
            raise ErroValidacaoPerfil(f"O limite alto precisa ser um número maior que sua meta ({meta_atual} mg/dL).")
    elif campo == "fator_sensibilidade":
        if valor <= 0:
            raise ErroValidacaoPerfil("O fator de sensibilidade precisa ser maior que zero.")
    elif campo == "tempo_insulina_ativa_horas":
        if not (1 <= valor <= 8):
            raise ErroValidacaoPerfil("O tempo de insulina ativa precisa estar entre 1 e 8 horas.")

    valor_final = valor if campo == "tempo_insulina_ativa_horas" else int(valor)
    supabase.table("perfil_glicemico").update({campo: valor_final}).eq("id", perfil["id"]).execute()
