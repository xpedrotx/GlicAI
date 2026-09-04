-- Site de acompanhamento: login com CPF + senha.
--
-- Não existe CPF/senha coletados hoje (cadastro via WhatsApp só pede
-- telefone/nome) — o paciente cria a senha no próprio site, provando posse
-- do número de WhatsApp com um código de 6 dígitos (mesmo padrão do convite
-- de cuidador em convites_cuidador). Sessão é um token opaco (não JWT),
-- guardado com hash em sessoes_web, pra dar pra revogar no logout.

alter table usuarios add column if not exists cpf text unique;
alter table usuarios add column if not exists senha_hash text;

create table if not exists codigos_login_web (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  codigo text not null,
  expira_em timestamptz not null,
  usado_em timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_codigos_login_web_usuario on codigos_login_web(usuario_id);

alter table codigos_login_web enable row level security;

create table if not exists sessoes_web (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  token_hash text not null unique,
  criado_em timestamptz not null default now(),
  expira_em timestamptz not null
);

create index if not exists idx_sessoes_web_token_hash on sessoes_web(token_hash);
create index if not exists idx_sessoes_web_usuario on sessoes_web(usuario_id);

alter table sessoes_web enable row level security;
