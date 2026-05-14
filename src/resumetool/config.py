from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM providers (optional; leave unset to run offline stubs)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None

    # Behavior toggles
    offline: bool = False
    redact_pii: bool = True
    max_cost_usd: float = 1.0

    # Database — SQLite for local dev, Postgres for production
    database_url: str = "sqlite:///./triage.db"

    # Background tasks
    redis_url: str = "redis://localhost:6379/0"

    # Email delivery (resend.com API key)
    email_api_key: str | None = None
    email_from_address: str = "hiring@example.com"

    # HR dashboard basic auth (comma-separated "user:pass" pairs)
    hr_auth_users: str = "admin:changeme"

    class Config:
        env_prefix = "RESUMETOOL_"


settings = Settings()  # loaded on import for simplicity
