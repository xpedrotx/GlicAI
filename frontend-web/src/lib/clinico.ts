/**
 * Mesma classificação clínica de 4 faixas usada no PDF de exportação
 * (_cor_e_seta_glicemia em exportacao.py) e nas mensagens do WhatsApp —
 * mantém consistência entre os três canais. Verde/vermelho só aparecem
 * aqui, nunca decorativos em outro lugar da UI.
 */
export type CorClinica = "vermelho" | "verde" | "neutro";

export function classificarGlicemia(
  valor: number,
  limiteBaixo: number,
  meta: number,
  limiteAlto: number
): { cor: CorClinica; seta: "" | "↓" | "↑" } {
  if (valor < limiteBaixo) return { cor: "vermelho", seta: "↓" };
  if (valor > limiteAlto) return { cor: "vermelho", seta: "↑" };
  if (valor < meta) return { cor: "verde", seta: "" };
  return { cor: "neutro", seta: "" };
}

export function corParaCss(cor: CorClinica): string {
  if (cor === "vermelho") return "var(--vermelho)";
  if (cor === "verde") return "var(--verde)";
  return "var(--foreground)";
}

const CONTEXTO_LABEL: Record<string, string> = {
  jejum: "Em jejum",
  pre_refeicao: "Antes da refeição",
  pos_prandial: "Depois da refeição",
  correcao: "Correção",
};

export function formatarContexto(contexto: string | null): string {
  if (!contexto || contexto === "outro") return "-";
  return CONTEXTO_LABEL[contexto] ?? contexto;
}

export function formatarHorario(iso: string, timezone: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    timeZone: timezone,
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatarData(iso: string, timezone: string): string {
  return new Date(iso).toLocaleString("pt-BR", { timeZone: timezone, day: "2-digit", month: "2-digit" });
}
