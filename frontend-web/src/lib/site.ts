/**
 * Dados comerciais da página inicial. NEXT_PUBLIC_WHATSAPP_VENDAS é o número
 * (só dígitos, com DDI, ex: 5545999999999) que recebe quem quer assinar —
 * definido no build. Sem ele, os botões de "quero assinar" levam pra seção
 * de como funciona em vez de um link quebrado.
 */
const NUMERO_VENDAS = (process.env.NEXT_PUBLIC_WHATSAPP_VENDAS ?? "").replace(/\D/g, "");

export const LINK_ASSINAR = NUMERO_VENDAS
  ? `https://wa.me/${NUMERO_VENDAS}?text=${encodeURIComponent("Oi! Quero conhecer o GlicAI.")}`
  : "#como-funciona";

export const ASSINAR_EXTERNO = Boolean(NUMERO_VENDAS);
