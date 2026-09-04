-- =========================================================
-- GlicAI — Migration 002
-- Rode no SQL Editor do Supabase depois do schema_glicia.sql
-- =========================================================

-- Guarda o passo atual e os dados já coletados durante o cadastro
-- conversacional (ex: {"passo": "basal", "dados": {"nome": "Ana", ...}}).
-- Fica null depois que o cadastro é concluído (status_cadastro = 'completo').
alter table usuarios add column if not exists estado_cadastro jsonb;
