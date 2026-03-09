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
