-- Controle de estoque de insumos (insulina, fitas de dextro) — desconta
-- automaticamente a cada dose aplicada / glicemia registrada, e avisa
-- quando tá acabando. Uma linha por (usuario, tipo).
create table if not exists estoque_insumos (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  tipo text not null check (tipo in ('insulina', 'fita_dextro')),
  quantidade_atual numeric(6,1) not null default 0,
  quantidade_por_reposicao numeric(6,1) not null,
  limite_alerta numeric(6,1) not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (usuario_id, tipo)
);

alter table estoque_insumos enable row level security;

create trigger trg_estoque_insumos_updated_at
  before update on estoque_insumos
  for each row execute function set_updated_at();
