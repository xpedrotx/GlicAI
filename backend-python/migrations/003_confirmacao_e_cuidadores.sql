-- =========================================================
-- GlicAI — Migration 003
-- Monitoria familiar: cuidadores + confirmação de glicemia crítica
-- Rode no SQL Editor do Supabase depois da migration 002
-- =========================================================

-- ---------------------------------------------------------
-- cuidadores (esposa, mãe etc — recebem avisos de glicemia crítica)
-- ---------------------------------------------------------
create table cuidadores (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  nome text not null,
  telefone text not null,         -- JID completo do WhatsApp (com @c.us ou @lid)
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (usuario_id, telefone)
);

create index idx_cuidadores_usuario on cuidadores(usuario_id);
create index idx_cuidadores_telefone on cuidadores(telefone);

create trigger trg_cuidadores_updated_at
  before update on cuidadores
  for each row execute function set_updated_at();

alter table cuidadores enable row level security;

-- ---------------------------------------------------------
-- convites_cuidador (código temporário pra vincular um cuidador)
-- ---------------------------------------------------------
create table convites_cuidador (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  codigo text not null,
  expira_em timestamptz not null,
  usado_em timestamptz,
  created_at timestamptz not null default now()
);

create index idx_convites_codigo on convites_cuidador(codigo);
create index idx_convites_usuario on convites_cuidador(usuario_id);

alter table convites_cuidador enable row level security;

-- ---------------------------------------------------------
-- confirmacoes_glicemia (ciclo de confirmação/lembrete/escalonamento
-- pra glicemia alta — dose de correção — e glicemia baixa — tratamento)
-- ---------------------------------------------------------
create table confirmacoes_glicemia (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  tipo text not null check (tipo in ('hiperglicemia', 'hipoglicemia')),
  valor_glicemia int not null,
  dose_sugerida numeric(4,1),                 -- só preenchido pra hiperglicemia
  registro_bolus_id uuid references registros_bolus(id) on delete set null,
  confirmado_em timestamptz,
  lembrete_enviado boolean not null default false,
  cuidadores_notificados boolean not null default false,
  horario timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index idx_confirmacoes_usuario on confirmacoes_glicemia(usuario_id);
create index idx_confirmacoes_pendentes on confirmacoes_glicemia(horario) where confirmado_em is null;

alter table confirmacoes_glicemia enable row level security;

-- Nenhuma policy criada de propósito — só a service_role (backend) acessa,
-- mesmo padrão do schema_glicia.sql original.
