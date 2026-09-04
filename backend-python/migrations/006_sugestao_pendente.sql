-- Guarda a última sugestão de comando feita pela IA de fallback, aguardando
-- confirmação do paciente (sim/não). Formato: {"comando": "...", "criado_em": "iso8601"}
alter table usuarios add column if not exists sugestao_pendente jsonb;
