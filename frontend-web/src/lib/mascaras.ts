/** Máscaras simples de digitação — só formatam visualmente, o valor enviado pra API sempre tem os dígitos extraídos de novo. */

export function mascararCpf(valor: string): string {
  const digitos = valor.replace(/\D/g, "").slice(0, 11);
  return digitos
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

/**
 * Formata progressivamente como "+55 (45) 99999-9999" enquanto o paciente
 * digita, assumindo DDI 55 (Brasil) + DDD + número — mesmo formato que o
 * telefone chega via WhatsApp. Só cosmético: o valor real mandado pra API
 * é sempre extraído de novo com somenteDigitos().
 */
export function mascararTelefone(valor: string): string {
  const digitos = valor.replace(/\D/g, "").slice(0, 13);
  const semDdi = digitos.startsWith("55") ? digitos.slice(2) : digitos;
  const ddd = semDdi.slice(0, 2);
  const numero = semDdi.slice(2);

  if (digitos.length <= 2) return digitos;
  if (semDdi.length <= 2) return `+55 (${ddd}`;
  const numeroFormatado = numero.length > 4 ? `${numero.slice(0, -4)}-${numero.slice(-4)}` : numero;
  return `+55 (${ddd}) ${numeroFormatado}`;
}

export function somenteDigitos(valor: string): string {
  return valor.replace(/\D/g, "");
}
