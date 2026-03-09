from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # App
    APP_NAME: str = "Smart Clinic Tracker"
    DEBUG: bool = False

    # Database (Neon PostgreSQL)
    DATABASE_URL: str  # Required — no default, must be set in env

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


settings = Settings()
