-- Lembrete automático de remedição — Regra dos 15: depois de tratar uma
-- hipoglicemia com carboidrato de ação rápida, medir a glicemia de novo em
-- 15 minutos antes de decidir qualquer outra coisa (nunca aplicar insulina
-- em hipoglicemia). Um lembrete avulso por hipoglicemia registrada.

create table if not exists lembretes_remedicao (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  disparar_em timestamptz not null,
  enviado boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_lembretes_remedicao_pendentes on lembretes_remedicao(disparar_em) where not enviado;

alter table lembretes_remedicao enable row level security;
