from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---------------------------------------------------------------
    environment: str = "local"
    debug: bool = False
    app_name: str = "WhatsAgent AI API"
    api_v1_prefix: str = "/api/v1"
    allowed_origins: list[str] = ["http://localhost:3000"]

    # --- Database / Redis ----------------------------------------------------
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # --- Supabase (Auth: GoTrue REST + JWT validation via JWKS) --------------
    supabase_url: str
    supabase_jwks_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: str

    # --- Auth session cookies (backend-issued, httpOnly) ----------------------
    auth_access_token_cookie: str = "wa_access_token"
    auth_refresh_token_cookie: str = "wa_refresh_token"
    auth_cookie_domain: str | None = None
    auth_cookie_secure: bool = True

    # --- WhatsApp Cloud API ---------------------------------------------------
    whatsapp_app_id: str
    whatsapp_app_secret: str
    whatsapp_webhook_verify_token: str
    whatsapp_graph_api_version: str = "v21.0"
    whatsapp_graph_api_base_url: str = "https://graph.facebook.com"

    # --- AI providers (provider-agnostic orchestration layer) ----------------
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    # Cross-provider fallback (OpenAI ↔ Anthropic). When the primary provider
    # exhausts its retry budget on a retryable error (429 / 5xx / network),
    # `generate_structured_reply` retries against the other provider using the
    # fallback model below. Off by default so behaviour is unchanged for
    # callers that haven't opted in.
    llm_fallback_enabled: bool = False
    fallback_openai_model: str = "gpt-4o-mini"
    fallback_anthropic_model: str = "claude-sonnet-4-5"

    # --- Token encryption (at-rest encryption of stored OAuth/API tokens) ----
    token_encryption_key: str

    # --- Observability --------------------------------------------------------
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1

    # --- Stripe ---------------------------------------------------------------
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_starter_price_id: str | None = None
    stripe_growth_price_id: str | None = None
    stripe_agency_price_id: str | None = None

    # --- Razorpay -------------------------------------------------------------
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None
    razorpay_starter_plan_id: str | None = None
    razorpay_growth_plan_id: str | None = None
    razorpay_agency_plan_id: str | None = None

    # --- Email (transactional — invites, notifications) ----------------------
    sendgrid_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    email_from_address: str = "noreply@whatsagent.ai"
    email_from_name: str = "WhatsAgent AI"

    # --- X (Twitter) API -----------------------------------------------------
    x_client_id: str | None = None
    x_client_secret: str | None = None
    x_bearer_token: str | None = None   # App-only bearer token for search
    # X Account Activity API webhook environment name (registered in dev portal)
    x_webhook_env_name: str = "production"

    # --- Frontend ------------------------------------------------------------
    app_frontend_url: str | None = None

    @field_validator("token_encryption_key")
    @classmethod
    def _validate_token_encryption_key(cls, value: str) -> str:
        """Fail fast at startup if TOKEN_ENCRYPTION_KEY isn't a valid Fernet key.

        Fernet keys are 32 url-safe base64-encoded bytes (44 chars). A bad key
        would otherwise only surface the first time a token is encrypted/decrypted
        — i.e. mid-request, in production, against a real OAuth token.
        """
        try:
            Fernet(value.encode("utf-8"))
        except Exception as exc:
            raise ValueError(
                "TOKEN_ENCRYPTION_KEY must be a valid Fernet key — "
                "32 url-safe base64-encoded bytes (44 characters). "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from exc
        return value

    @property
    def whatsapp_graph_api_url(self) -> str:
        return f"{self.whatsapp_graph_api_base_url}/{self.whatsapp_graph_api_version}"

    @property
    def supabase_auth_url(self) -> str:
        return f"{self.supabase_url}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
