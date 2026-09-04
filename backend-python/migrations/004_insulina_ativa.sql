-- =========================================================
-- GlicAI — Migration 004
-- Tempo de insulina ativa (IOB — insulin on board)
-- Rode no SQL Editor do Supabase depois da migration 003
-- =========================================================

-- Quantas horas a insulina rápida continua agindo no corpo do paciente
-- depois de aplicada. Fica null até o paciente informar (cadastro ou
-- comando "tempo_insulina_ativa <horas>") — sem esse valor, o cálculo de
-- bolus não desconta insulina ativa (comportamento igual ao de antes dessa
-- migration), porque não inventamos um número clínico sem o paciente/médico
-- confirmar.
alter table perfil_glicemico add column if not exists tempo_insulina_ativa_horas numeric(3,1);
