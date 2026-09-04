-- Segundo lembrete no ciclo de confirmação de glicemia crítica (hiper/hipo):
-- agora são 2 lembretes pro paciente (5min, 10min) antes de escalar pros
-- cuidadores aos 15min sem confirmação, em vez de 1 lembrete (5min) + 1
-- escalonamento (10min).
alter table confirmacoes_glicemia add column if not exists lembrete2_enviado boolean not null default false;
