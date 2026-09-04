"""
Controle de estoque de insumos (insulina, fitas de dextro).

Recurso opt-in: só entra em ação depois que o paciente configura com
*estoque configurar <tipo> <quantidade>*. A partir daí, desconta
automaticamente — insulina a cada *apliquei*, fitas a cada *glicemia* — e
avisa quando o nível ficar abaixo do limite configurado.
"""
from app.services.supabase_client import supabase

TIPOS = {"insulina": "Insulina", "fita_dextro": "Fitas de dextro"}

# aceita várias formas de digitar o tipo (a segunda palavra é o alias)
TIPOS_ENTRADA = {
    "insulina": "insulina",
    "fita": "fita_dextro",
    "fitas": "fita_dextro",
    "dextro": "fita_dextro",
    "fita_dextro": "fita_dextro",
}

# se o paciente não informar um limite de alerta explícito, avisa quando
# restar menos de 20% da reposição padrão
FRACAO_LIMITE_PADRAO = 0.2


async def buscar(usuario_id: str, tipo: str) -> dict | None:
    linhas = (
        supabase.table("estoque_insumos")
        .select("*")
        .eq("usuario_id", usuario_id)
        .eq("tipo", tipo)
        .execute()
        .data
    )
    return linhas[0] if linhas else None


async def configurar(usuario_id: str, tipo: str, quantidade_por_reposicao: float, limite_alerta: float) -> None:
    """Cria ou substitui a configuração de um tipo de insumo, começando com
    o estoque cheio (assume que o paciente está configurando a partir de um
    frasco/caixa novo)."""
    existente = await buscar(usuario_id, tipo)
    dados = {
        "quantidade_atual": quantidade_por_reposicao,
        "quantidade_por_reposicao": quantidade_por_reposicao,
        "limite_alerta": limite_alerta,
    }
    if existente:
        supabase.table("estoque_insumos").update(dados).eq("id", existente["id"]).execute()
    else:
        supabase.table("estoque_insumos").insert(
            {**dados, "usuario_id": usuario_id, "tipo": tipo}
        ).execute()


async def reabastecer(usuario_id: str, tipo: str, quantidade: float) -> bool:
    """Define o estoque atual pra `quantidade` (novo frasco/caixa). Retorna
    False se esse tipo ainda não tiver sido configurado."""
    existente = await buscar(usuario_id, tipo)
    if existente is None:
        return False
    supabase.table("estoque_insumos").update({"quantidade_atual": quantidade}).eq("id", existente["id"]).execute()
    return True


async def listar(usuario_id: str) -> list[dict]:
    return supabase.table("estoque_insumos").select("*").eq("usuario_id", usuario_id).execute().data


async def consumir(usuario_id: str, tipo: str, quantidade: float) -> str | None:
    """
    Desconta `quantidade` do estoque configurado desse tipo (nunca fica
    negativo). Retorna uma linha de aviso pronta pra anexar na resposta do
    bot se o nível ficar abaixo do limite configurado depois do desconto —
    ou None se esse tipo não estiver configurado, ou se ainda tiver folga.
    """
    linha = await buscar(usuario_id, tipo)
    if linha is None:
        return None

    nova_quantidade = max(0.0, float(linha["quantidade_atual"]) - quantidade)
    supabase.table("estoque_insumos").update({"quantidade_atual": nova_quantidade}).eq("id", linha["id"]).execute()

    if nova_quantidade > linha["limite_alerta"]:
        return None

    label = TIPOS.get(tipo, tipo).lower()
    return (
        f"\n\n⚠️ Estoque de {label} baixo: restam *{nova_quantidade:.0f}*. "
        f"Considere repor (*estoque reabastecer {tipo}*)."
    )
