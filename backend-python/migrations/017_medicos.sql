-- GlicAI — Migration 017
-- Painel do médico: o médico cria conta no site, ganha um código de
-- vinculação próprio e acompanha (somente leitura) os pacientes que o
-- informaram — ver app/services/medicos.py.
-- Rode no SQL Editor do Supabase depois da migration 016.

create table if not exists medicos (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  email text not null,
  crm text not null,
  uf text not null,
  senha_hash text not null,
  -- Código que o paciente digita pra dar acesso (ex: DR-K7M2QX). Sozinho ele
  -- não dá acesso a nada: só identifica o médico — quem vincula é o paciente.
  codigo_vinculo text not null unique,
  criado_em timestamptz not null default now()
);

-- e-mail único sem diferenciar maiúsculas
create unique index if not exists idx_medicos_email on medicos (lower(email));

create table if not exists sessoes_medico (
  id uuid primary key default gen_random_uuid(),
  medico_id uuid not null references medicos(id) on delete cascade,
  token_hash text not null unique,
  criado_em timestamptz not null default now(),
  expira_em timestamptz not null
);

create index if not exists idx_sessoes_medico_token_hash on sessoes_medico(token_hash);
create index if not exists idx_sessoes_medico_medico on sessoes_medico(medico_id);

-- Quem acompanha quem. "ativo = false" é vínculo desfeito (pelo paciente ou
-- pelo médico) — guardado em vez de apagado, pra poder reativar com o mesmo
-- código sem perder o histórico de quando foi vinculado.
create table if not exists medico_pacientes (
  id uuid primary key default gen_random_uuid(),
  medico_id uuid not null references medicos(id) on delete cascade,
  usuario_id uuid not null references usuarios(id) on delete cascade,
  ativo boolean not null default true,
  vinculado_em timestamptz not null default now(),
  desvinculado_em timestamptz,
  unique (medico_id, usuario_id)
);

create index if not exists idx_medico_pacientes_usuario on medico_pacientes(usuario_id);

alter table medicos enable row level security;
alter table sessoes_medico enable row level security;
alter table medico_pacientes enable row level security;

-- Rate limiting reaproveita a tabela de tentativas — só precisa aceitar os
-- tipos novos (a trava antiga só conhecia login, confirmar_codigo e vincular).
alter table tentativas_auth drop constraint if exists tentativas_auth_tipo_check;
alter table tentativas_auth add constraint tentativas_auth_tipo_check
  check (tipo in ('login', 'confirmar_codigo', 'vincular', 'login_medico', 'cadastro_medico', 'vincular_medico'));
