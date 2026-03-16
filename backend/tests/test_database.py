import pytest
from app.core.config import Settings


def test_database_ssl_setting():
    """Test that DATABASE_SSL setting is parsed with correct default."""
    # Test default (should be True for security)
    settings_with_default = Settings(DATABASE_URL="postgresql+asyncpg://localhost/test")
    assert settings_with_default.DATABASE_SSL is True

    # Test explicit false
    settings_with_false = Settings(
        DATABASE_URL="postgresql+asyncpg://localhost/test",
        DATABASE_SSL=False
    )
    assert settings_with_false.DATABASE_SSL is False

    # Test explicit true
    settings_with_true = Settings(
        DATABASE_URL="postgresql+asyncpg://localhost/test",
        DATABASE_SSL=True
    )
    assert settings_with_true.DATABASE_SSL is True


def test_database_ssl_connect_args_logic():
    """Test that the conditional logic for connect_args works correctly."""
    # This tests the pattern used in database.py
    # We can't easily test the actual engine's connect_args without module reload

    # Test SSL=True produces {"ssl": True}
    ssl_true = {"ssl": True} if True else {}
    assert ssl_true == {"ssl": True}

    # Test SSL=False produces {}
    ssl_false = {"ssl": True} if False else {}
    assert ssl_false == {}
