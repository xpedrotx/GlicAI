/**
 * Cliente HTTP fino pra API do backend. Sempre chama caminhos relativos
 * (`/api/...`) — em produção o Caddy roteia isso direto pro backend-python
 * na mesma origem (sem CORS); em dev local, `next.config.ts` faz o proxy
 * pro backend rodando em BACKEND_URL. `credentials: "include"` garante que
 * o cookie httpOnly de sessão (glicai_sessao) seja enviado nas chamadas.
 */

import type { Convite, Cuidador, HbA1c, Historico, ItemEstoque, Padroes, PerfilCompleto, MedicoEu, MedicoVinculado, Plano, Relatorio, ResultadoAssinatura, ResultadoVinculo, ResumoPaciente } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function chamar<T>(caminho: string, opcoes: RequestInit = {}): Promise<T> {
  const resposta = await fetch(`/api${caminho}`, {
    ...opcoes,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...opcoes.headers },
  });

  const corpo = await resposta.json().catch(() => null);

  if (!resposta.ok) {
    const mensagem = corpo?.detail ?? "Algo deu errado. Tenta de novo.";
    throw new ApiError(resposta.status, mensagem);
  }

  return corpo as T;
}

export const api = {
  confirmarCodigo: (dados: { codigo: string; cpf: string; senha: string }) =>
    chamar<{ status: string }>("/auth/confirmar-codigo", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  login: (cpf: string, senha: string) =>
    chamar<{ status: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ cpf, senha }),
    }),

  logout: () => chamar<{ status: string }>("/auth/logout", { method: "POST" }),

  eu: () => chamar<{ nome: string | null; telefone: string }>("/auth/me"),

  historico: (dias: number) => chamar<Historico>(`/dashboard/historico?dias=${dias}`),

  perfil: () => chamar<PerfilCompleto>("/dashboard/perfil"),

  atualizarPerfil: (campo: string, valor: string) =>
    chamar<{ status: string }>("/dashboard/perfil", {
      method: "PUT",
      body: JSON.stringify({ campo, valor }),
    }),

  relatorio: (periodo: "semana" | "mes") => chamar<Relatorio>(`/dashboard/relatorio?periodo=${periodo}`),

  hba1c: (dias: number) => chamar<HbA1c>(`/dashboard/hba1c?dias=${dias}`),

  padroes: (dias: number) => chamar<Padroes>(`/dashboard/padroes?dias=${dias}`),

  cuidadores: () => chamar<{ cuidadores: Cuidador[] }>("/dashboard/cuidadores"),

  gerarConvite: () => chamar<Convite>("/dashboard/cuidadores/convite", { method: "POST" }),

  removerCuidador: (nome: string) =>
    chamar<{ status: string }>(`/dashboard/cuidadores/${encodeURIComponent(nome)}`, { method: "DELETE" }),

  estoque: () => chamar<{ itens: ItemEstoque[] }>("/dashboard/estoque"),

  configurarEstoque: (tipo: string, quantidadePorReposicao: number, limiteAlerta: number | null) =>
    chamar<{ status: string }>("/dashboard/estoque/configurar", {
      method: "POST",
      body: JSON.stringify({
        tipo,
        quantidade_por_reposicao: quantidadePorReposicao,
        limite_alerta: limiteAlerta,
      }),
    }),

  reabastecerEstoque: (tipo: string, quantidade: number) =>
    chamar<{ status: string }>("/dashboard/estoque/reabastecer", {
      method: "POST",
      body: JSON.stringify({ tipo, quantidade }),
    }),

  plano: () => chamar<Plano>("/dashboard/plano"),

  assinar: (metodoPagamentoId: string) =>
    chamar<ResultadoAssinatura>("/dashboard/plano/assinar", {
      method: "POST",
      body: JSON.stringify({ metodo_pagamento_id: metodoPagamentoId }),
    }),

  confirmarAssinatura: (assinaturaId: string) =>
    chamar<Plano & { status: string }>("/dashboard/plano/confirmar", {
      method: "POST",
      body: JSON.stringify({ assinatura_id: assinaturaId }),
    }),

  abrirPortal: () => chamar<{ url: string }>("/dashboard/plano/portal", { method: "POST" }),
  // --- Lado do paciente: médicos que acompanham ---
  medicosVinculados: () => chamar<{ medicos: MedicoVinculado[] }>("/dashboard/medicos"),

  vincularMedico: (codigo: string, confirmar: boolean) =>
    chamar<ResultadoVinculo>("/dashboard/medicos/vincular", {
      method: "POST",
      body: JSON.stringify({ codigo, confirmar }),
    }),

  removerMedico: (id: string) => chamar<{ status: string }>(`/dashboard/medicos/${id}`, { method: "DELETE" }),

  // --- Painel do médico ---
  /** 1ª etapa: manda o código de 6 dígitos por e-mail (a conta só nasce em medicoConfirmarEmail). */
  medicoCadastro: (dados: { nome: string; email: string; crm: string; uf: string; senha: string }) =>
    chamar<{ status: string; email: string }>("/medico/cadastro", { method: "POST", body: JSON.stringify(dados) }),

  medicoConfirmarEmail: (email: string, codigo: string) =>
    chamar<{ status: string }>("/medico/confirmar-email", { method: "POST", body: JSON.stringify({ email, codigo }) }),

  medicoReenviarCodigo: (email: string) =>
    chamar<{ status: string }>("/medico/reenviar-codigo", { method: "POST", body: JSON.stringify({ email }) }),

  medicoLogin: (email: string, senha: string) =>
    chamar<{ status: string }>("/medico/login", { method: "POST", body: JSON.stringify({ email, senha }) }),

  medicoLogout: () => chamar<{ status: string }>("/medico/logout", { method: "POST" }),

  medicoEu: () => chamar<MedicoEu>("/medico/me"),

  medicoPacientes: () => chamar<{ pacientes: ResumoPaciente[] }>("/medico/pacientes"),

  medicoPaciente: (id: string) => chamar<ResumoPaciente>(`/medico/pacientes/${id}`),

  medicoDesvincular: (id: string) => chamar<{ status: string }>(`/medico/pacientes/${id}`, { method: "DELETE" }),

  medicoHistorico: (id: string, dias: number) => chamar<Historico>(`/medico/pacientes/${id}/historico?dias=${dias}`),

  medicoPerfil: (id: string) => chamar<PerfilCompleto>(`/medico/pacientes/${id}/perfil`),

  medicoRelatorio: (id: string, periodo: "semana" | "mes") =>
    chamar<Relatorio>(`/medico/pacientes/${id}/relatorio?periodo=${periodo}`),

  medicoHba1c: (id: string, dias: number) => chamar<HbA1c>(`/medico/pacientes/${id}/hba1c?dias=${dias}`),

  medicoPadroes: (id: string, dias: number) => chamar<Padroes>(`/medico/pacientes/${id}/padroes?dias=${dias}`),
};