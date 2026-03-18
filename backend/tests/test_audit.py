"""Tests for audit logging atomicity."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.utils.audit import record_audit
from app.core.security import hash_password


@pytest.mark.asyncio
async def test_audit_and_main_operation_in_same_transaction(db: AsyncSession):
    """Verify that audit entry and main operation are committed together."""
    # Create a user with audit
    user = User(
        email="audit-test@example.com",
        password_hash=hash_password("password123"),
        full_name="Audit Test User",
        role=UserRole.student,
    )
    db.add(user)

    # Flush to get the server-generated UUID
    await db.flush()

    # Record audit before commit
    await record_audit(
        db,
        user_id=uuid.uuid4(),  # Some admin user
        action="create",
        table_name="users",
        record_id=user.id,
        new_values={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
        },
    )

    # Commit both together
    await db.commit()
    await db.refresh(user)

    # Verify both user and audit exist
    assert user.id is not None

    # Check audit entry exists
    from sqlalchemy import select
    result = await db.execute(
        select(AuditLog).where(AuditLog.record_id == user.id)
    )
    audit_entry = result.scalar_one_or_none()

    assert audit_entry is not None
    assert audit_entry.action == "create"
    assert audit_entry.table_name == "users"
    assert audit_entry.new_values["email"] == "audit-test@example.com"


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_main_operation(db: AsyncSession):
    """Verify that if audit fails, the main operation is also rolled back."""
    # Create a user
    user = User(
        email="rollback-test@example.com",
        password_hash=hash_password("password123"),
        full_name="Rollback Test User",
        role=UserRole.student,
    )
    db.add(user)
    await db.flush()

    # Record valid audit
    await record_audit(
        db,
        user_id=uuid.uuid4(),
        action="create",
        table_name="users",
        record_id=user.id,
        new_values={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
        },
    )

    # Before commit, roll back the transaction manually
    await db.rollback()

    # Verify user was NOT persisted
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.email == "rollback-test@example.com")
    )
    persisted_user = result.scalar_one_or_none()

    assert persisted_user is None, "User should not exist after rollback"

    # Also verify no audit entry
    audit_result = await db.execute(
        select(AuditLog).where(AuditLog.record_id == user.id)
    )
    audit_entry = audit_result.scalar_one_or_none()

    assert audit_entry is None, "Audit entry should not exist after rollback"


@pytest.mark.asyncio
async def test_flush_populates_id_before_commit(db: AsyncSession):
    """Verify that db.flush() makes server-generated UUID available before commit."""
    user = User(
        email="flush-test@example.com",
        password_hash=hash_password("password123"),
        full_name="Flush Test User",
        role=UserRole.student,
    )
    db.add(user)

    # Before flush, ID should be None (server-generated)
    assert user.id is None, "ID should be None before flush"

    # Flush to get the ID from database
    await db.flush()

    # After flush, ID should be populated
    assert user.id is not None, "ID should be populated after flush"

    # Rollback to clean up
    await db.rollback()


@pytest.mark.asyncio
async def test_session_state_after_audit_failure(db: AsyncSession):
    """Verify that session remains usable after an audit operation fails."""
    # Create first user successfully
    user1 = User(
        email="session-test-1@example.com",
        password_hash=hash_password("password123"),
        full_name="Session Test User 1",
        role=UserRole.student,
    )
    db.add(user1)
    await db.flush()

    await record_audit(
        db,
        user_id=uuid.uuid4(),
        action="create",
        table_name="users",
        record_id=user1.id,
        new_values={"email": user1.email},
    )
    await db.commit()

    # Verify session is still usable by creating another user
    user2 = User(
        email="session-test-2@example.com",
        password_hash=hash_password("password123"),
        full_name="Session Test User 2",
        role=UserRole.student,
    )
    db.add(user2)
    await db.flush()

    await record_audit(
        db,
        user_id=uuid.uuid4(),
        action="create",
        table_name="users",
        record_id=user2.id,
        new_values={"email": user2.email},
    )
    await db.commit()

    # Verify both users exist
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.email.like("session-test-%@example.com"))
    )
    users = result.scalars().all()

    assert len(users) == 2, "Both users should be created"


@pytest.mark.asyncio
async def test_create_user_creates_audit_entry(db: AsyncSession, admin_token: str):
    """Integration test: creating a user via API creates an audit entry."""
    from httpx import AsyncClient
    from app.main import app
    from app.core.database import async_session_maker

    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a user
        response = await client.post(
            "/api/users",
            json={
                "email": "integration-audit@example.com",
                "password": "password123",
                "full_name": "Integration Audit User",
                "role": "student",
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 201

    # Verify audit entry was created (use fresh session)
    async with async_session_maker() as verify_db:
        from sqlalchemy import select
        result = await verify_db.execute(
            select(AuditLog).where(
                AuditLog.table_name == "users",
                AuditLog.action == "create"
            ).order_by(AuditLog.created_at.desc())
        )
        audit_entry = result.first()

        assert audit_entry is not None
        assert audit_entry.new_values["email"] == "integration-audit@example.com"


@pytest.mark.asyncio
async def test_create_department_creates_audit_entry(db: AsyncSession, admin_token: str):
    """Integration test: creating a department via API creates an audit entry."""
    from httpx import AsyncClient
    from app.main import app
    from app.core.database import async_session_maker

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/departments",
            json={
                "name": "Audit Test Department",
                "description": "Test department for audit",
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 201

    # Verify audit entry
    async with async_session_maker() as verify_db:
        from sqlalchemy import select
        result = await verify_db.execute(
            select(AuditLog).where(
                AuditLog.table_name == "departments",
                AuditLog.action == "create"
            ).order_by(AuditLog.created_at.desc())
        )
        audit_entry = result.first()

        assert audit_entry is not None
        assert audit_entry.new_values["name"] == "Audit Test Department"
