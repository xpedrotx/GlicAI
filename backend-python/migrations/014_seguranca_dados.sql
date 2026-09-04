-- GlicAI — Migration 014
-- Reforço de segurança: rate limiting em códigos de 6 dígitos (login web e
-- convite de cuidador) e suporte a exclusão completa de conta (LGPD).
-- Rode no SQL Editor do Supabase depois da migration 013.

-- Registro de tentativa (só as que falharam) pra bloquear força bruta nos
-- códigos de 6 dígitos — login web (CPF+senha), confirmação de código, e
-- vínculo de cuidador. "identificador" é o IP (login/confirmação, vem da
-- API web) ou o telefone/JID (vínculo de cuidador, vem do WhatsApp) que fez
-- a tentativa — nunca o CPF/código em si, pra não vazar dado sensível numa
-- tabela de auditoria de abuso.
create table if not exists tentativas_auth (
  id uuid primary key default gen_random_uuid(),
  identificador text not null,
  tipo text not null check (tipo in ('login', 'confirmar_codigo', 'vincular')),
  criado_em timestamptz not null default now()
);

create index if not exists idx_tentativas_auth_lookup on tentativas_auth(identificador, tipo, criado_em desc);

alter table tentativas_auth enable row level security;

-- Nenhuma limpeza automática das linhas antigas: o volume é baixo (só
-- tentativas falhas) e a janela de bloqueio já as torna irrelevantes depois
-- de alguns minutos — mas nada impede rodar um DELETE periódico manual se
-- a tabela crescer demais com o tempo.
