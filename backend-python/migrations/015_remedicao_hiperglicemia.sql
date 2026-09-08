-- GlicAI — Migration 015
-- Estende o lembrete de remedição (antes só hipoglicemia, 15min) pra
-- também cobrir hiperglicemia (60min) — ver app/services/remedicao.py.
-- Rode no SQL Editor do Supabase depois da migration 014.

alter table lembretes_remedicao add column if not exists tipo text
  not null default 'hipoglicemia' check (tipo in ('hipoglicemia', 'hiperglicemia'));

-- O default cobre as linhas antigas (todas eram hipoglicemia, único tipo
-- que existia até aqui) e evita quebrar inserts que ainda não passem
-- "tipo" explicitamente. Novo código (remedicao.agendar) sempre passa.
