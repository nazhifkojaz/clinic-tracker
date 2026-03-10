import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User, UserRole

# Use NullPool to avoid connection reuse across different event loops
test_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

# Store created users for use in tests
_created_users = {}


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def _setup_database():
    """Create tables and seed test users at session start."""
    global _created_users

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create test users
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

    yield
    # Clean up at session end
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(_setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for each test."""
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


def auth_header(token: str) -> dict[str, str]:
    """Helper to create Authorization header."""
    return {"Authorization": f"Bearer {token}"}
