-- Guarda quando a dose foi de fato APLICADA (paciente confirmou via
-- "apliquei"), separado de `horario` (que é quando o bot calculou/sugeriu a
-- dose). A insulina ativa (IOB) precisa decair a partir do momento real da
-- aplicação — se o paciente demora pra aplicar, ou aplica sem cálculo prévio,
-- os dois horários podem ser bem diferentes.
alter table registros_bolus add column if not exists horario_aplicacao timestamptz;
