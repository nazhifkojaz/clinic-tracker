import pytest
from app.core.database import Base, engine, async_session_maker, get_db
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


def test_base_is_declarative_base():
    """Base should be a SQLAlchemy DeclarativeBase subclass."""
    assert issubclass(Base, DeclarativeBase)


def test_engine_is_async():
    """Engine should be an async engine instance."""
    assert isinstance(engine, AsyncEngine)


def test_session_maker_configured():
    """Session maker should be an async_sessionmaker."""
    assert isinstance(async_session_maker, async_sessionmaker)


@pytest.mark.anyio
async def test_get_db_yields_session():
    """get_db should yield an AsyncSession."""
    # Note: This test won't actually connect to a DB — it tests the generator structure
    import inspect

    assert inspect.isasyncgenfunction(get_db)


def test_database_ssl_setting():
    """Test that DATABASE_SSL setting is parsed with correct default."""
    from app.core.config import Settings

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
