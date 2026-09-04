from supabase import create_client, Client
from app.config import settings

# Usa a service_role key: o backend tem acesso total às tabelas,
# ignorando o Row Level Security (RLS) habilitado no schema.
supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,
)
