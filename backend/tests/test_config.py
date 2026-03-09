import pytest
from pydantic import ValidationError


def test_settings_loads_from_env(monkeypatch):
    """Settings should load required values from environment variables."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://test:test@localhost/testdb"
    )
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")

    # Re-import to pick up patched env
    from app.core.config import Settings

    s = Settings()

    assert s.DATABASE_URL == "postgresql+asyncpg://test:test@localhost/testdb"
    assert s.SECRET_KEY == "test-secret-key-at-least-32-chars-long!!"
    assert s.APP_NAME == "Smart Clinic Tracker"
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert s.REFRESH_TOKEN_EXPIRE_DAYS == 7


def test_settings_defaults(monkeypatch):
    """Settings should have correct default values for optional fields."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/testdb")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.delenv("DEBUG", raising=False)

    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    from app.core.config import Settings

    s = Settings()

    # Verify defaults (DEBUG defaults to False when not set)
    assert s.APP_NAME == "Smart Clinic Tracker"
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert s.REFRESH_TOKEN_EXPIRE_DAYS == 7
    assert len(s.CORS_ORIGINS) >= 1
    assert "http://localhost:5173" in s.CORS_ORIGINS
