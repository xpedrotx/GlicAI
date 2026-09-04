from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    node_bridge_url: str = "http://localhost:3000"
    internal_api_key: str
    port: int = 8000
    # Opcional: sem essa chave, o fallback de IA pra comandos digitados errado
    # simplesmente fica desativado (nunca derruba o app).
    anthropic_api_key: str = ""
    # Opcional: sem essa chave, o alerta de uso do banco (perto do limite
    # gratuito do Supabase) simplesmente não envia o email.
    resend_api_key: str = ""
    # Cookie de sessão do site (glicai_sessao) só é enviado pelo browser em
    # HTTPS quando True (obrigatório em produção). Em dev local sem TLS
    # (ex: rodando o backend direto, sem o Caddy na frente), colocar
    # COOKIE_SECURE=false no .env pra conseguir testar o login no browser.
    cookie_secure: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
