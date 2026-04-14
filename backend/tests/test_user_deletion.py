"""Tests for user deletion (soft and hard delete)."""

from app.models.user import User, UserRole
from app.core.security import hash_password
from tests.conftest import auth_header
from tests.factories import _random_suffix


async def _create_user(db_session, **overrides):
    """Helper to create a test user."""
    suffix = _random_suffix()
    defaults = {
        "email": f"delete_{suffix}@test.com",
        "password_hash": await hash_password("testpass123"),
        "full_name": "Delete Target",
        "role": UserRole.student,
        "is_active": True,
        "email_verified": True,
        "institutional_id": f"DEL{suffix}",
    }
    defaults.update(overrides)
    user = User(**defaults)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------


async def test_soft_delete_sets_inactive(client, admin_token, db_session):
    """Soft delete sets is_active=False."""
    user = await _create_user(db_session)
    response = await client.delete(
        f"/api/users/{user.id}?mode=soft",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 204

    await db_session.refresh(user)
    assert user.is_active is False
    # PII should still be intact
    assert user.full_name == "Delete Target"
    assert "delete_" in user.email


async def test_soft_delete_default_mode(client, admin_token, db_session):
    """Default delete mode is soft (no mode param needed)."""
    user = await _create_user(db_session)
    response = await client.delete(
        f"/api/users/{user.id}",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 204

    await db_session.refresh(user)
    assert user.is_active is False


# ---------------------------------------------------------------------------
# Hard delete
# ---------------------------------------------------------------------------


async def test_hard_delete_anonymizes_pii(client, admin_token, db_session):
    """Hard delete anonymizes user PII."""
    user = await _create_user(
        db_session, full_name="Real Name", institutional_id="ID12345"
    )
    response = await client.delete(
        f"/api/users/{user.id}?mode=hard",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 204

    await db_session.refresh(user)
    assert user.full_name == "Real Name (Deleted User)"
    assert user.institutional_id is None
    assert user.email.startswith("deleted_")
    assert user.email.endswith("@deleted")
    assert user.is_active is False
    assert user.email_verified is False
    assert user.password_hash != ""  # Replaced with random invalid hash
    from app.core.security import verify_password

    assert not await verify_password("testpass123", user.password_hash)


async def test_hard_delete_preserves_row(client, admin_token, db_session):
    """Hard delete keeps the row in the database (FK integrity)."""
    from sqlalchemy import select

    user = await _create_user(db_session)
    user_id = user.id

    response = await client.delete(
        f"/api/users/{user_id}?mode=hard",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 204

    # Row still exists
    result = await db_session.execute(select(User).where(User.id == user_id))
    assert result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Self-deletion prevention
# ---------------------------------------------------------------------------


async def test_cannot_delete_self(client, admin_token, admin_user):
    """Admin cannot delete their own account."""
    response = await client.delete(
        f"/api/users/{admin_user.id}?mode=soft",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 400
    assert (
        "cannot delete" in response.json()["detail"].lower()
        or "own" in response.json()["detail"].lower()
    )


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


async def test_delete_admin_only(client, student_token, db_session):
    """Non-admins cannot delete users."""
    user = await _create_user(db_session)
    response = await client.delete(
        f"/api/users/{user.id}?mode=soft",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_delete_nonexistent_user(client, admin_token):
    """Deleting a non-existent user returns 404."""
    import uuid

    response = await client.delete(
        f"/api/users/{uuid.uuid4()}?mode=soft",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 404
