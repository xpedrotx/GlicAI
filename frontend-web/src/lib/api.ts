/**
 * Cliente HTTP fino pra API do backend. Sempre chama caminhos relativos
 * (`/api/...`) — em produção o Caddy roteia isso direto pro backend-python
 * na mesma origem (sem CORS); em dev local, `next.config.ts` faz o proxy
 * pro backend rodando em BACKEND_URL. `credentials: "include"` garante que
 * o cookie httpOnly de sessão (glicai_sessao) seja enviado nas chamadas.
 */

import type { Convite, Cuidador, HbA1c, Historico, ItemEstoque, Padroes, PerfilCompleto, Relatorio } from "./types";

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
};
