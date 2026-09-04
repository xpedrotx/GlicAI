-- =========================================================
-- GlicAI — Migration 005
-- Controle de envio dos relatórios semanal/mensal automáticos
-- Rode no SQL Editor do Supabase depois da migration 004
-- =========================================================

-- Guarda quando cada relatório foi mandado pela última vez, pra o scheduler
-- não mandar duas vezes na mesma semana/mês (ver app/services/relatorios.py).
alter table usuarios add column if not exists relatorio_semanal_enviado_em timestamptz;
alter table usuarios add column if not exists relatorio_mensal_enviado_em timestamptz;
