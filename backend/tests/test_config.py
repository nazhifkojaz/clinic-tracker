import pytest


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


def test_settings_requires_database_url(monkeypatch):
    """Settings should fail if DATABASE_URL is not set."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    from app.core.config import Settings

    with pytest.raises(Exception):
        Settings()
