# Must set environment variables BEFORE any app imports
import os

# Enable email mock mode for tests (no real emails sent)
os.environ.setdefault("EMAIL_MOCK_MODE", "true")

import asyncio
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.cache import categories_cache, departments_cache
from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User, UserRole

from tests.factories import _random_suffix

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. "
        "Set it to a local test database to avoid running tests against production."
    )

# Safety: only allow local test databases (allowlist approach)
parsed = urlparse(TEST_DATABASE_URL)
host = parsed.hostname or ""  # None for SQLite/unix sockets

# Allowed: localhost, IPv4 loopback, IPv6 loopback, empty host (SQLite/unix socket)
local_hosts = {"localhost", "127.0.0.1", "::1", ""}
is_local = (
    host in local_hosts  # localhost or loopback
    or host.startswith("/")  # Unix socket path
    or TEST_DATABASE_URL.startswith(
        ("sqlite+aiosqlite:///", "sqlite:///")
    )  # SQLite file
    or ":memory:" in TEST_DATABASE_URL  # In-memory SQLite
)

if not is_local:
    raise RuntimeError(
        f"TEST_DATABASE_URL must point to a local database only. "
        f"Got host: {host or 'local file'}. "
        f"Tests must run against localhost/127.0.0.1/::1, SQLite files, or Unix sockets. "
        f"Never run destructive tests against remote databases!"
    )

# Use NullPool so each test's event loop gets a fresh connection with no cross-loop sharing.
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

# Store created users for use in tests (populated once at session start)
_created_users = {}


async def _run_setup():
    """Create schema and seed base test users. Runs once per session via asyncio.run()."""
    from sqlalchemy import text

    async with test_engine.begin() as conn:
        # Enable pg_trgm extension for trigram indexes (PERF-04)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        from sqlalchemy import select

        # Define seed users
        seed_users = [
            {
                "email": "admin@test.com",
                "password_hash": await hash_password("testpass123"),
                "full_name": "Test Admin",
                "role": UserRole.admin,
                "is_active": True,
            },
            {
                "email": "student@test.com",
                "password_hash": await hash_password("testpass123"),
                "full_name": "Test Student",
                "institutional_id": "STU001",
                "role": UserRole.student,
                "is_active": True,
                "email_verified": True,
            },
            {
                "email": "supervisor@test.com",
                "password_hash": await hash_password("testpass123"),
                "full_name": "Test Supervisor",
                "role": UserRole.supervisor,
                "is_active": True,
            },
        ]

        for user_data in seed_users:
            email = user_data["email"]
            result = await session.execute(select(User).where(User.email == email))
            existing = result.scalar_one_or_none()

            if existing is None:
                # User doesn't exist, create it
                user = User(**user_data)
                session.add(user)
                await session.flush()  # Get the ID
                await session.refresh(user)
                _created_users[user.role.value] = user
            else:
                # User already exists from a previous run, reuse it
                _created_users[existing.role.value] = existing

        await session.commit()


async def _run_teardown():
    """Drop all tables. Runs once per session via asyncio.run()."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    """Session-scoped sync fixture: creates schema + seeds users before any test runs."""
    asyncio.run(_run_setup())
    yield
    asyncio.run(_run_teardown())


@pytest.fixture(autouse=True)
def _disable_cache_during_tests():
    """Disable caching during tests to ensure fresh data for each test."""
    categories_cache.disable()
    departments_cache.disable()
    yield
    categories_cache.enable()
    departments_cache.enable()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset rate limiter storage between tests so limits don't carry over."""
    limiter.reset()
    yield


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh database session for each test with transaction rollback isolation."""
    # Start a connection and begin a transaction
    async with test_engine.connect() as connection:
        # Begin a transaction that will be rolled back after each test
        await connection.begin()

        # Create a session bound to this connection
        # Use rollback_only mode so test commits don't persist to outer transaction
        async_session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="rollback_only",
        )

        try:
            yield async_session
        finally:
            # Close the session (may be in a closed state after test rollback)
            await async_session.close()
            # Rollback the outer transaction to undo all test changes
            await connection.rollback()
        await connection.close()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with DB dependency overridden."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user() -> User:
    """Return the pre-created admin user."""
    return _created_users.get("admin")


@pytest.fixture
def student_user() -> User:
    """Return the pre-created student user."""
    return _created_users.get("student")


@pytest.fixture
def supervisor_user() -> User:
    """Return the pre-created supervisor user."""
    return _created_users.get("supervisor")


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """JWT access token for admin user."""
    return create_access_token(subject=str(admin_user.id), role="admin")


@pytest.fixture
def student_token(student_user: User) -> str:
    """JWT access token for student user."""
    return create_access_token(subject=str(student_user.id), role="student")


@pytest.fixture
def supervisor_token(supervisor_user: User) -> str:
    """JWT access token for supervisor user."""
    return create_access_token(subject=str(supervisor_user.id), role="supervisor")


@pytest.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """Create an inactive user for testing inactive login scenarios."""
    suffix = _random_suffix()
    user = User(
        email=f"inactive_{suffix}@test.com",
        password_hash=await hash_password("testpass123"),
        full_name="Inactive User",
        institutional_id=f"INACTIVE{suffix}",
        role=UserRole.student,
        is_active=False,
        email_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def fresh_student(db_session: AsyncSession) -> User:
    """Create a fresh student with no pre-existing data for isolated tests."""
    suffix = _random_suffix()
    user = User(
        email=f"fresh_{suffix}@test.com",
        password_hash=await hash_password("testpass123"),
        full_name="Fresh Student",
        institutional_id=f"FRESH{suffix}",
        role=UserRole.student,
        is_active=True,
        email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def auth_header(token: str) -> dict[str, str]:
    """Helper to create Authorization header."""
    return {"Authorization": f"Bearer {token}"}
