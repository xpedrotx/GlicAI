export type Glicemia = { horario: string; valor: number; contexto: string | null };

export type BolusRegistro = {
  horario: string;
  carboidratos_g: number | null;
  glicemia_referencia: number | null;
  dose_calculada: number | null;
  dose_aplicada: number | null;
};

export type Perfil = { meta_glicemia: number; limite_baixo: number; limite_alto: number };

export type Historico = {
  perfil: Perfil | null;
  timezone: string | null;
  periodo: { inicio: string; fim: string } | null;
  glicemias: Glicemia[];
  bolus: BolusRegistro[];
};

export type RelacaoIC = { periodo: string; hora_inicio: string; hora_fim: string; gramas_por_unidade: number };

export type BasalItem = { horario: string; dose: number; tipo_insulina: string | null };

export type Modificador = { nome: string; tipo_ajuste: "percentual" | "fixo"; valor_ajuste: number; ativo: boolean };

export type PerfilCompleto = {
  nome: string | null;
  meta_glicemia: number;
  limite_baixo: number;
  limite_alto: number;
  fator_sensibilidade: number;
  tempo_insulina_ativa_horas: number | null;
  relacoes_ic: RelacaoIC[];
  basal: BasalItem[];
  modificadores: Modificador[];
};

export type Relatorio = {
  perfil: { limite_baixo: number; limite_alto: number } | null;
  periodo?: "semana" | "mes";
  data_inicio?: string;
  data_fim?: string;
  num_medicoes?: number;
  media_glicemia?: number | null;
  na_faixa_pct?: number | null;
  hipoglicemias?: number;
  hiperglicemias?: number;
  doses_aplicadas?: number;
  total_insulina?: number | null;
  media_insulina_dia?: number | null;
  eventos_criticos?: number;
};

export type HbA1c =
  | { disponivel: false; minimo_medicoes: number; dias: number }
  | { disponivel: true; media_glicemia: number; gmi: number; num_medicoes: number; dias: number };

export type Padrao = {
  dia_semana_label: string;
  periodo: string;
  media: number;
  tipo: "alta" | "baixa";
  n: number;
};

export type Padroes = { dias: number; padroes: Padrao[] };

export type Cuidador = { nome: string };

export type Convite = { codigo: string; expira_em: string; minutos_validade: number };

export type ItemEstoque = {
  tipo: "insulina" | "fita_dextro";
  label: string;
  quantidade_atual: number;
  quantidade_por_reposicao: number;
  limite_alerta: number;
};

export type Fatura = {
  id: string;
  data: string;
  valor: number;
  status: "paga" | "em_aberto" | "nao_paga" | "cancelada" | "outra";
  pdf: string | null;
  url: string | null;
};

export type DadosPagamento = {
  cartao: { marca: string | null; final: string | null; mes: number | null; ano: number | null } | null;
  faturas: Fatura[];
};

export type Plano = {
  plano: "trial" | "free" | "pro";
  cortesia: boolean;
  teste_termina_em: string | null;
  dias_restantes_teste: number | null;
  assinatura_status: string | null;
  renova_em: string | null;
  cancela_no_fim: boolean;
  tem_cliente_stripe: boolean;
  preco: string;
  medicoes_por_dia_free: number;
  pagamentos_disponiveis: boolean;
  publishable_key: string | null;
};

/** Resposta de POST /plano/assinar: ou já ficou Pro, ou o banco pediu autenticação (3D Secure). */
export type ResultadoAssinatura =
  | (Plano & { status: "ok" })
  | { status: "requer_acao"; assinatura_id: string; client_secret: string };

// --- Médicos ---------------------------------------------------------------

export type MedicoEu = { id: string; nome: string; email: string; crm: string; uf: string; codigo_vinculo: string };

export type ResumoPaciente = {
  id: string;
  nome: string | null;
  vinculado_em: string;
  tem_perfil: boolean;
  ultima_glicemia: { valor: number; horario: string } | null;
  medicoes: number;
  media: number | null;
  na_faixa_pct: number | null;
  hipoglicemias: number;
  hiperglicemias: number;
  ultima_fora_da_faixa: boolean;
  limite_baixo: number | null;
  limite_alto: number | null;
};

/** Médico que o paciente vinculou (lado do paciente). */
export type MedicoVinculado = { id: string; nome: string; crm: string; uf: string; vinculado_em: string };

export type PreviaMedico = { id: string; nome: string; crm: string; uf: string };

export type ResultadoVinculo =
  | { status: "confirmar"; medico: PreviaMedico }
  | { status: "vinculado" | "ja_vinculado"; medico: PreviaMedico };

