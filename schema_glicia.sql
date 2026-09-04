-- =========================================================
-- GlicAI — Schema do banco (Supabase / Postgres)
-- Rode este script no SQL Editor do Supabase (Project > SQL Editor)
-- =========================================================

-- Extensão para gerar UUIDs
create extension if not exists "pgcrypto";

-- ---------------------------------------------------------
-- Função utilitária para manter updated_at sempre atualizado
-- ---------------------------------------------------------
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- =========================================================
-- 1. usuarios
-- =========================================================
create table usuarios (
  id uuid primary key default gen_random_uuid(),
  telefone text not null unique,          -- número do WhatsApp, formato E.164 (ex: 5545999999999)
  nome text,
  timezone text not null default 'America/Sao_Paulo',
  status_cadastro text not null default 'incompleto'
    check (status_cadastro in ('incompleto', 'completo', 'pausado')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger trg_usuarios_updated_at
  before update on usuarios
  for each row execute function set_updated_at();

-- =========================================================
-- 2. perfil_glicemico (1 para 1 com usuarios)
-- =========================================================
create table perfil_glicemico (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null unique references usuarios(id) on delete cascade,
  meta_glicemia int not null,             -- alvo de glicemia (mg/dL)
  limite_baixo int not null,              -- abaixo disso = hipoglicemia
  limite_alto int not null,               -- acima disso = hiperglicemia
  fator_sensibilidade int not null,       -- quanto 1U de insulina reduz a glicemia (mg/dL)
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (limite_baixo < meta_glicemia and meta_glicemia < limite_alto)
);

create trigger trg_perfil_glicemico_updated_at
  before update on perfil_glicemico
  for each row execute function set_updated_at();

-- =========================================================
-- 3. relacao_ic (relação insulina:carboidrato, pode variar por período)
-- =========================================================
create table relacao_ic (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  periodo text not null,                  -- ex: 'café da manhã', 'almoço', 'jantar', 'livre'
  hora_inicio time not null,
  hora_fim time not null,
  gramas_por_unidade numeric(5,1) not null, -- gramas de carboidrato cobertos por 1U de insulina
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_relacao_ic_usuario on relacao_ic(usuario_id);

create trigger trg_relacao_ic_updated_at
  before update on relacao_ic
  for each row execute function set_updated_at();

-- =========================================================
-- 4. basal (horários e doses de insulina basal)
-- =========================================================
create table basal (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  horario time not null,
  dose numeric(4,1) not null,
  tipo_insulina text,                     -- ex: 'Lantus', 'Tresiba', 'Levemir'
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_basal_usuario on basal(usuario_id);

create trigger trg_basal_updated_at
  before update on basal
  for each row execute function set_updated_at();

-- =========================================================
-- 5. modificadores_bolus (regras variáveis cadastradas pelo paciente)
-- =========================================================
create table modificadores_bolus (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  nome text not null,                     -- ex: 'Exercício físico', 'Doença', 'Período menstrual'
  tipo_ajuste text not null check (tipo_ajuste in ('percentual', 'fixo')),
  valor_ajuste numeric(5,2) not null,     -- ex: -20 (percentual) ou -2 (unidades fixas)
  ativo boolean not null default true,    -- permite desativar sem apagar o histórico
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_modificadores_usuario on modificadores_bolus(usuario_id);

create trigger trg_modificadores_updated_at
  before update on modificadores_bolus
  for each row execute function set_updated_at();

-- =========================================================
-- 6. registros_glicemia (histórico de medições)
-- =========================================================
create table registros_glicemia (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  valor int not null,
  horario timestamptz not null default now(),
  contexto text check (contexto in ('jejum', 'pre_refeicao', 'pos_prandial', 'correcao', 'outro')),
  created_at timestamptz not null default now()
);

create index idx_registros_glicemia_usuario_horario on registros_glicemia(usuario_id, horario desc);

-- =========================================================
-- 7. registros_bolus (histórico de doses calculadas/aplicadas)
-- =========================================================
create table registros_bolus (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  carboidratos_g int,
  glicemia_referencia int,
  dose_calculada numeric(4,1) not null,
  dose_aplicada numeric(4,1),             -- pode ser diferente da calculada, se o paciente ajustar manualmente
  horario timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index idx_registros_bolus_usuario_horario on registros_bolus(usuario_id, horario desc);

-- Tabela de junção N:N — quais modificadores foram aplicados em cada bolus
create table registros_bolus_modificadores (
  registro_bolus_id uuid not null references registros_bolus(id) on delete cascade,
  modificador_id uuid not null references modificadores_bolus(id) on delete cascade,
  primary key (registro_bolus_id, modificador_id)
);

-- =========================================================
-- 8. lembretes (configuração de lembretes de medição/aplicação)
-- =========================================================
create table lembretes (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  tipo text not null check (tipo in ('medir_glicemia', 'aplicar_basal', 'aplicar_bolus', 'outro')),
  horario time not null,
  dias_semana int[] not null default '{0,1,2,3,4,5,6}', -- 0=domingo ... 6=sábado
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_lembretes_usuario on lembretes(usuario_id);

create trigger trg_lembretes_updated_at
  before update on lembretes
  for each row execute function set_updated_at();

-- =========================================================
-- 9. alertas_enviados (log de alertas de hipo/hiperglicemia)
-- =========================================================
create table alertas_enviados (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  tipo text not null check (tipo in ('hipoglicemia', 'hiperglicemia')),
  valor_glicemia int not null,
  horario_envio timestamptz not null default now()
);

create index idx_alertas_usuario_horario on alertas_enviados(usuario_id, horario_envio desc);

-- =========================================================
-- Observação sobre segurança (RLS)
-- =========================================================
-- Como o backend Python vai acessar o Supabase usando a service_role key,
-- o Row Level Security (RLS) é automaticamente ignorado por essa chave.
-- Ainda assim, é boa prática deixar o RLS habilitado em todas as tabelas,
-- para que, se algum dia você expuser uma API pública (ex: app do paciente
-- acessando direto o Supabase com a anon key), os dados fiquem protegidos
-- por padrão até que políticas explícitas sejam criadas.

alter table usuarios enable row level security;
alter table perfil_glicemico enable row level security;
alter table relacao_ic enable row level security;
alter table basal enable row level security;
alter table modificadores_bolus enable row level security;
alter table registros_glicemia enable row level security;
alter table registros_bolus enable row level security;
alter table registros_bolus_modificadores enable row level security;
alter table lembretes enable row level security;
alter table alertas_enviados enable row level security;

-- Nenhuma policy é criada aqui de propósito: sem policies, apenas a
-- service_role (usada pelo backend) consegue ler/escrever. Se depois você
-- criar um app do paciente com login (Supabase Auth), crie policies do tipo
-- "usuario só vê seus próprios dados" usando auth.uid() = usuario_id.
