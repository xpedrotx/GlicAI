-- Endurece as funções criadas na migration 009 conforme apontado pelo
-- linter de segurança do Supabase (get_advisors):
--   - function_search_path_mutable: search_path mutável é vetor de
--     schema-injection em funções SECURITY DEFINER.
--   - anon/authenticated_security_definer_function_executable:
--     tamanho_banco_bytes() estava chamável via REST por qualquer client
--     anon/authenticated, sem necessidade — é uso interno do backend.

alter function set_updated_at() set search_path = '';
alter function tamanho_banco_bytes() set search_path = '';

revoke execute on function tamanho_banco_bytes() from public;
revoke execute on function tamanho_banco_bytes() from anon;
revoke execute on function tamanho_banco_bytes() from authenticated;
grant execute on function tamanho_banco_bytes() to service_role;
