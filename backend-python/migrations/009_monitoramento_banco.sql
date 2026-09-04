-- Monitoramento de uso do banco (plano gratuito do Supabase = 500MB): uma
-- função RPC pra expor pg_database_size() via API, e uma tabela genérica de
-- estado pra guardar quando foi o último alerta enviado (evita mandar email
-- toda vez que o job rodar enquanto o uso continuar acima do limiar).
create or replace function tamanho_banco_bytes()
returns bigint
language sql
security definer
as $$
  select pg_database_size(current_database());
$$;

grant execute on function tamanho_banco_bytes() to service_role;

create table if not exists monitoramento_estado (
  chave text primary key,
  valor jsonb,
  atualizado_em timestamptz not null default now()
);

-- Mesmo padrão do resto do schema: RLS ligado, sem políticas — só o
-- service_role (que ignora RLS) consegue acessar; anon/authenticated ficam
-- sem nenhum acesso por padrão.
alter table monitoramento_estado enable row level security;
