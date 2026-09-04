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
