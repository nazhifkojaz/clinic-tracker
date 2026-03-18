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
    # Connection pool settings (small for auto-sleep compatibility on fly.io/Neon free tier)
    DATABASE_POOL_SIZE: int = 2  # Small pool to minimize stale connections
    DATABASE_MAX_OVERFLOW: int = 1  # Allow brief bursts
    DATABASE_POOL_RECYCLE: int = 300  # Recycle after 5 min (before sleep timeout)
    DATABASE_POOL_TIMEOUT: int = 30

    # Auth (JWT)
    SECRET_KEY: str  # Required — no default
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # Vite dev server
    ]

    # Cloudflare R2 (S3-compatible)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "clinic-tracker"

    # Resend (email)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@example.com"
    EMAIL_MOCK_MODE: bool = False  # Explicit flag for dev/test


settings = Settings()
