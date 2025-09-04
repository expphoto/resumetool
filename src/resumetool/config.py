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

    class Config:
        env_prefix = "RESUMETOOL_"


settings = Settings()  # loaded on import for simplicity

