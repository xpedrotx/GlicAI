-- GlicAI — Migration 016
-- Planos e assinatura: teste grátis de 7 dias, depois plano Free (1 medição
-- por dia, sem lembretes) ou GlicAI Pro (R$ 9,90/mês, via Stripe) — ver
-- app/services/planos.py e app/services/pagamentos.py.
-- Rode no SQL Editor do Supabase depois da migration 015.

alter table usuarios
  -- Linhas já existentes ganham 7 dias de teste a partir do momento em que
  -- esta migration roda (o default é calculado uma vez, na execução).
  add column if not exists teste_termina_em timestamptz not null default (now() + interval '7 days'),
  -- Conta com Pro liberado sem cobrança (dono do serviço, convidados).
  add column if not exists plano_cortesia boolean not null default false,
  add column if not exists stripe_customer_id text,
  add column if not exists stripe_subscription_id text,
  -- Estado da assinatura no Stripe: active, trialing, past_due, canceled,
  -- unpaid, incomplete, incomplete_expired, paused. Null = nunca assinou.
  add column if not exists assinatura_status text,
  add column if not exists assinatura_renova_em timestamptz,
  add column if not exists assinatura_cancela_no_fim boolean not null default false,
  -- Quando o aviso de "seu teste acabou" foi mandado no WhatsApp (uma vez só).
  add column if not exists aviso_fim_teste_em timestamptz;

create unique index if not exists idx_usuarios_stripe_customer
  on usuarios (stripe_customer_id) where stripe_customer_id is not null;

-- Para liberar o Pro na sua própria conta, sem cobrança:
--   update usuarios set plano_cortesia = true where telefone = '<seu JID>';
