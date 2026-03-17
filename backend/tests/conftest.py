import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.cache import categories_cache, departments_cache
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User, UserRole

from tests.factories import _random_suffix

# Use a dedicated test database URL — never the production one.
import os

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. "
        "Set it to a local test database to avoid running tests against production."
    )

# Safety: refuse to run tests against a remote/production database
if "neon.tech" in TEST_DATABASE_URL or "amazonaws.com" in TEST_DATABASE_URL:
    raise RuntimeError(
        f"TEST_DATABASE_URL points to a remote database ({TEST_DATABASE_URL[:50]}...). "
        "Tests must run against a local database (localhost). "
        "Never run tests against production!"
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
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        admin = User(
            email="admin@test.com",
            password_hash=hash_password("testpass123"),
            full_name="Test Admin",
            role=UserRole.admin,
            is_active=True,
        )
        student = User(
            email="student@test.com",
            password_hash=hash_password("testpass123"),
            full_name="Test Student",
            student_id="STU001",
            role=UserRole.student,
            is_active=True,
        )
        supervisor = User(
            email="supervisor@test.com",
            password_hash=hash_password("testpass123"),
            full_name="Test Supervisor",
            role=UserRole.supervisor,
            is_active=True,
        )

        session.add_all([admin, student, supervisor])
        await session.commit()

        for user in [admin, student, supervisor]:
            await session.refresh(user)
            _created_users[user.role.value] = user


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


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh database session for each test (function-scoped event loop)."""
    async with TestSessionLocal() as session:
        yield session


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
        password_hash=hash_password("testpass123"),
        full_name="Inactive User",
        student_id=f"INACTIVE{suffix}",
        role=UserRole.student,
        is_active=False,
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
        password_hash=hash_password("testpass123"),
        full_name="Fresh Student",
        student_id=f"FRESH{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def auth_header(token: str) -> dict[str, str]:
    """Helper to create Authorization header."""
    return {"Authorization": f"Bearer {token}"}
