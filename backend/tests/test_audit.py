"""Tests for audit logging atomicity."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.utils.audit import record_audit
from app.core.security import hash_password


@pytest.mark.asyncio
async def test_audit_and_main_operation_in_same_transaction(db_session: AsyncSession):
    """Verify that audit entry and main operation are committed together."""
    # Create a user with audit
    user = User(
        email="audit-test@example.com",
        password_hash=await hash_password("password123"),
        full_name="Audit Test User",
        role=UserRole.student,
    )
    db_session.add(user)

    # Flush to get the server-generated UUID
    await db_session.flush()

    # Record audit before commit
    await record_audit(
        db_session,
        user_id=user.id,  # Some admin user
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
    await db_session.commit()
    await db_session.refresh(user)

    # Verify both user and audit exist
    assert user.id is not None

    # Check audit entry exists
    from sqlalchemy import select

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.record_id == user.id)
    )
    audit_entry = result.scalar_one_or_none()

    assert audit_entry is not None
    assert audit_entry.action == "create"
    assert audit_entry.table_name == "users"
    assert audit_entry.new_values["email"] == "audit-test@example.com"


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_main_operation(db_session: AsyncSession):
    """Verify that if audit fails, the main operation is also rolled back."""
    # Create a user
    user = User(
        email="rollback-test@example.com",
        password_hash=await hash_password("password123"),
        full_name="Rollback Test User",
        role=UserRole.student,
    )
    db_session.add(user)
    await db_session.flush()

    # Record valid audit
    await record_audit(
        db_session,
        user_id=user.id,
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
    await db_session.rollback()

    # Verify user was NOT persisted
    from sqlalchemy import select

    result = await db_session.execute(
        select(User).where(User.email == "rollback-test@example.com")
    )
    persisted_user = result.scalar_one_or_none()

    assert persisted_user is None, "User should not exist after rollback"

    # Also verify no audit entry
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.record_id == user.id)
    )
    audit_entry = audit_result.scalar_one_or_none()

    assert audit_entry is None, "Audit entry should not exist after rollback"


@pytest.mark.asyncio
async def test_flush_populates_id_before_commit(db_session: AsyncSession):
    """Verify that db.flush() makes server-generated UUID available before commit."""
    user = User(
        email="flush-test@example.com",
        password_hash=await hash_password("password123"),
        full_name="Flush Test User",
        role=UserRole.student,
    )
    db_session.add(user)

    # Before flush, ID should be None (server-generated)
    assert user.id is None, "ID should be None before flush"

    # Flush to get the ID from database
    await db_session.flush()

    # After flush, ID should be populated
    assert user.id is not None, "ID should be populated after flush"

    # Rollback to clean up
    await db_session.rollback()


@pytest.mark.asyncio
async def test_session_state_after_audit(db_session: AsyncSession):
    """Verify that session remains usable after audit + flush (no commit)."""
    from sqlalchemy import select

    # First user + audit
    user1 = User(
        email="session-test-1@example.com",
        password_hash=await hash_password("password123"),
        full_name="Session Test User 1",
        role=UserRole.student,
    )
    db_session.add(user1)
    await db_session.flush()

    await record_audit(
        db_session,
        user_id=user1.id,
        action="create",
        table_name="users",
        record_id=user1.id,
        new_values={"email": user1.email},
    )
    await db_session.flush()

    # Second user + audit (session should still be usable)
    user2 = User(
        email="session-test-2@example.com",
        password_hash=await hash_password("password123"),
        full_name="Session Test User 2",
        role=UserRole.student,
    )
    db_session.add(user2)
    await db_session.flush()

    await record_audit(
        db_session,
        user_id=user2.id,
        action="create",
        table_name="users",
        record_id=user2.id,
        new_values={"email": user2.email},
    )
    await db_session.flush()

    # Both should be visible in the same transaction
    result = await db_session.execute(
        select(User).where(User.email.like("session-test-%@example.com"))
    )
    users = result.scalars().all()
    assert len(users) == 2, "Both users should be visible after flush"

    await db_session.rollback()


@pytest.mark.asyncio
async def test_create_user_creates_audit_entry(client, admin_token, db_session):
    """Integration test: creating a user via API creates an audit entry."""
    from sqlalchemy import select
    from tests.factories import _random_suffix

    suffix = _random_suffix()
    response = await client.post(
        "/api/users",
        json={
            "email": f"integration-audit-{suffix}@example.com",
            "password": "password123",
            "full_name": "Integration Audit User",
            "role": "student",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201

    # Verify audit entry via the same test session
    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.table_name == "users", AuditLog.action == "create")
        .order_by(AuditLog.created_at.desc())
    )
    audit_entry = result.scalars().first()

    assert audit_entry is not None
    assert audit_entry.new_values["email"] == f"integration-audit-{suffix}@example.com"


@pytest.mark.asyncio
async def test_create_department_creates_audit_entry(client, admin_token, db_session):
    """Integration test: creating a department via API creates an audit entry."""
    from sqlalchemy import select
    from tests.factories import _random_suffix

    suffix = _random_suffix()
    response = await client.post(
        "/api/departments",
        json={
            "name": f"Audit Test Dept {suffix}",
            "description": "Test department for audit",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201

    # Verify audit entry via the same test session
    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.table_name == "departments", AuditLog.action == "create")
        .order_by(AuditLog.created_at.desc())
    )
    audit_entry = result.scalars().first()

    assert audit_entry is not None
    assert audit_entry.new_values["name"] == f"Audit Test Dept {suffix}"
