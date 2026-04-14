from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Monorepo: `.env` lives at repo root; uvicorn cwd is usually `backend/`.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
_ENV_FILES = (
    str(_REPO_ROOT / ".env"),
    str(_BACKEND_DIR / ".env"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://forge:forge@localhost:5433/agentforge",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6380/0", alias="REDIS_URL")
    jwt_secret_key: str = Field(default="dev-secret-change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
        description="Comma-separated origins for browser clients (localhost vs 127.0.0.1 differ).",
    )
    cors_allow_private_network: bool = Field(
        default=True,
        alias="CORS_ALLOW_PRIVATE_NETWORK",
        description=(
            "Reply to Access-Control-Request-Private-Network (Chrome preflight); "
            "needed for many local dev setups."
        ),
    )
    cors_origin_regex: str | None = Field(
        default=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
        alias="CORS_ORIGIN_REGEX",
        description=(
            "Extra allowed Origin pattern (any port on loopback). "
            "Set empty in production if you rely only on CORS_ORIGINS."
        ),
    )
    redteam_mode: str = Field(default="mock", alias="REDTEAM_MODE")
    sandbox_mode: str = Field(
        default="subprocess",
        alias="SANDBOX_MODE",
        description=(
            "subprocess (default, no Docker needed) | docker (isolated container, requires Docker)."
        ),
    )
    allow_registration: bool = Field(
        default=True,
        alias="ALLOW_REGISTRATION",
        description="Set to false to disable public sign-up (invite-only mode).",
    )
    disable_pgvector_memory: bool = Field(
        default=False,
        alias="DISABLE_PGVECTOR_MEMORY",
        description=(
            "When true, use NoopMemoryStore for graph memory nodes and memory API list/delete."
        ),
    )
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")

    observability_backend: str = Field(
        default="langfuse",
        alias="OBSERVABILITY_BACKEND",
        description="langfuse | langsmith | both | none",
    )

    langfuse_secret_key: str | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_public_key: str | None = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_host: str | None = Field(default="https://cloud.langfuse.com", alias="LANGFUSE_HOST")

    langsmith_api_key: str | None = Field(default=None, alias="LANGSMITH_API_KEY")
    langsmith_project: str | None = Field(default=None, alias="LANGSMITH_PROJECT")

    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        alias="SENTRY_TRACES_SAMPLE_RATE",
    )
    sentry_environment: str | None = Field(default=None, alias="SENTRY_ENVIRONMENT")
    modal_enabled: bool = Field(default=False, alias="MODAL_ENABLED")
    modal_inference_url: str | None = Field(
        default=None,
        alias="MODAL_INFERENCE_URL",
        description=(
            "Web endpoint URL from `modal deploy modal_functions/inference.py`. "
            "Set after deployment; deploy action uses this as the inference endpoint."
        ),
    )

    # Object storage (S3-compatible) — used for audio blobs instead of inline base64.
    s3_bucket: str | None = Field(default=None, alias="S3_BUCKET")
    s3_endpoint_url: str | None = Field(
        default=None,
        alias="S3_ENDPOINT_URL",
        description="S3-compatible endpoint (e.g. MinIO, R2, Tigris). Leave blank for AWS S3.",
    )
    s3_access_key: str | None = Field(default=None, alias="S3_ACCESS_KEY")
    s3_secret_key: str | None = Field(default=None, alias="S3_SECRET_KEY")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")

    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    hf_token: str | None = Field(
        default=None,
        alias="HF_TOKEN",
        description=(
            "HuggingFace API token. Optional — the public API works without it "
            "but a token grants higher rate limits and private model access."
        ),
    )

    # SSO / OIDC — enterprise identity provider (Okta, Auth0, Azure AD, etc.)
    sso_oidc_issuer: str | None = Field(
        default=None,
        alias="SSO_OIDC_ISSUER",
        description="OIDC issuer URL, e.g. https://dev-xxx.okta.com or https://accounts.google.com",
    )
    sso_oidc_client_id: str | None = Field(default=None, alias="SSO_OIDC_CLIENT_ID")
    sso_oidc_client_secret: str | None = Field(default=None, alias="SSO_OIDC_CLIENT_SECRET")
    sso_oidc_redirect_uri: str | None = Field(
        default=None,
        alias="SSO_OIDC_REDIRECT_URI",
        description="Backend callback URL, e.g. http://localhost:8000/api/v1/sso/callback",
    )

    google_oauth_client_id: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_SECRET")
    google_oauth_redirect_uri: str | None = Field(
        default=None,
        alias="GOOGLE_OAUTH_REDIRECT_URI",
        description=(
            "Backend callback URL registered in Google Cloud Console, e.g. "
            "http://localhost:8000/api/v1/auth/oauth/google/callback"
        ),
    )
    oauth_frontend_redirect_url: str = Field(
        default="http://localhost:3000/auth/callback",
        alias="OAUTH_FRONTEND_REDIRECT_URL",
        description="Browser redirect after OAuth; should point to SPA route that stores JWTs.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
