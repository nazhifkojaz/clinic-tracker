from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

connect_args = {"ssl": True} if settings.DATABASE_SSL else {}

# Use default async pool with pre-ping for auto-sleep compatibility on fly.io/Neon free tier.
# pool_pre_ping tests connections before use, detecting stale connections from auto-sleep.
# Small pool size minimizes the number of connections that can go stale.
if settings.DEBUG:
    # Use NullPool in development/CI for immediate connection cleanup
    pool_config: dict = {"poolclass": NullPool}
else:
    # Use default AsyncAdaptedQueuePool in production with health checks
    pool_config = {
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_recycle": settings.DATABASE_POOL_RECYCLE,
        "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
        "pool_pre_ping": True,
    }

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=connect_args,
    **pool_config,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_maker() as session:
        yield session
