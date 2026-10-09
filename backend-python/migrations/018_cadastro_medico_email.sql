-- GlicAI — Migration 018
-- Cadastro do médico passa a confirmar o e-mail: os dados ficam aqui, como
-- pendentes, até o médico digitar o código de 6 dígitos que recebeu por
-- e-mail. Só então a conta é criada em "medicos" — ver app/services/medicos.py.
-- Rode no SQL Editor do Supabase depois da migration 017.

create table if not exists cadastros_medico_pendentes (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  email text not null,
  crm text not null,
  uf text not null,
  senha_hash text not null,
  -- só o hash do código fica guardado (o código em si só existe no e-mail)
  codigo_hash text not null,
  expira_em timestamptz not null,
  -- erros de digitação do código: ao passar do limite o cadastro pendente
  -- é descartado e o médico precisa recomeçar
  tentativas int not null default 0,
  reenvios int not null default 0,
  ultimo_envio_em timestamptz not null default now(),
  criado_em timestamptz not null default now()
);

create unique index if not exists idx_cadastros_medico_pendentes_email
  on cadastros_medico_pendentes (lower(email));

alter table cadastros_medico_pendentes enable row level security;
