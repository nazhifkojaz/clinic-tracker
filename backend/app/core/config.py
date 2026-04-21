from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "Smart Clinic Tracker"
    DEBUG: bool = False

    # Database (Neon PostgreSQL)
    DATABASE_URL: str  # Required — no default, must be set in env
    DATABASE_SSL: bool = (
        True  # Default to secure for production, set false for local dev
    )
    # Connection pool settings (configurable via environment for different deployment scenarios)
    # For production: Use larger pools for better concurrency
    # For free-tier: Override with smaller values to minimize stale connections
    DATABASE_POOL_SIZE: int = 5  # Increased for moderate concurrent load
    DATABASE_MAX_OVERFLOW: int = 10  # Allow bursts up to 15 total connections
    DATABASE_POOL_RECYCLE: int = 300  # Recycle after 5 min (before sleep timeout)
    DATABASE_POOL_TIMEOUT: int = 30

    # Auth (JWT)
    SECRET_KEY: str  # Required — no default
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5174",  # Vite dev server (alternate)
    ]

    # Cloudflare R2 (S3-compatible)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "clinic-tracker"

    # Email / SMTP
    EMAIL_MOCK_MODE: bool = False  # True → log only, never send
    EMAIL_FROM: str = "noreply@example.com"  # Defaults to GMAIL_USER if not set

    # SMTP transport (override for local dev to point at Mailpit)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True  # False for Mailpit
    SMTP_REQUIRE_AUTH: bool = True  # False for Mailpit

    # Gmail credentials (only required when SMTP_REQUIRE_AUTH=True)
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""

    # Frontend URL (used for building email verification links)
    FRONTEND_URL: str = "http://localhost:5173"


settings = Settings()
