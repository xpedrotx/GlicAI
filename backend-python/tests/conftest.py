import os
import sys
from pathlib import Path

# Garante que "app" seja importável independente do diretório de onde o pytest roda.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# app/config.py instancia Settings() na importação (lida por app.services.supabase_client,
# usado por app.services.bolus). Nos testes não existe .env nem Supabase real, então
# fornecemos valores dummy só pra permitir a importação dos módulos.
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
# precisa "parecer" um JWT (regex do client do supabase-py), o conteúdo não importa pros testes
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake.testtoken.value")
os.environ.setdefault("INTERNAL_API_KEY", "chave-de-teste")
