"""Tests for self-service password change, profile update, and pending changes approval."""

from sqlalchemy import select

from app.core.security import hash_password, verify_password, create_access_token
from app.models.pending_profile_change import PendingChangeStatus, PendingProfileChange
from app.models.user import User, UserRole
from tests.conftest import auth_header
from tests.factories import _random_suffix


async def _create_user(db_session, **overrides):
    """Helper to create a test user."""
    suffix = _random_suffix()
    defaults = {
        "email": f"settingstest_{suffix}@test.com",
        "password_hash": await hash_password("oldpassword123"),
        "full_name": "Settings Test User",
        "role": UserRole.student,
        "is_active": True,
        "email_verified": True,
        "institutional_id": f"ST{suffix}",
    }
    defaults.update(overrides)
    user = User(**defaults)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _token_for(user: User) -> str:
    return create_access_token(subject=str(user.id), role=user.role.value)


# ===========================================================================
# Password change
# ===========================================================================


async def test_change_password_success(client, db_session):
    """User can change password with correct current password."""
    user = await _create_user(db_session)
    token = _token_for(user)

    response = await client.post(
        "/api/users/me/change-password",
        json={"current_password": "oldpassword123", "new_password": "newpassword456"},
        headers=auth_header(token),
    )
    assert response.status_code == 204

    await db_session.refresh(user)
    assert await verify_password("newpassword456", user.password_hash)
    assert not await verify_password("oldpassword123", user.password_hash)


async def test_change_password_wrong_current(client, db_session):
    """Wrong current password returns 400."""
    user = await _create_user(db_session)
    token = _token_for(user)

    response = await client.post(
        "/api/users/me/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpassword456"},
        headers=auth_header(token),
    )
    assert response.status_code == 400
    assert "incorrect" in response.json()["detail"].lower()


async def test_change_password_requires_auth(client):
    """Unauthenticated request returns 401/403."""
    response = await client.post(
        "/api/users/me/change-password",
        json={"current_password": "somepassword", "new_password": "newsecurepass123"},
    )
    assert response.status_code in (401, 403)


# ===========================================================================
# Profile update — admin (applies immediately)
# ===========================================================================


async def test_admin_profile_applies_immediately(client, db_session):
    """Admin profile changes apply without approval."""
    user = await _create_user(db_session, role=UserRole.admin)
    token = _token_for(user)

    response = await client.patch(
        "/api/users/me/profile",
        json={"full_name": "Admin Updated"},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Admin Updated"

    await db_session.refresh(user)
    assert user.full_name == "Admin Updated"


# ===========================================================================
# Profile update — student (queues for approval)
# ===========================================================================


async def test_student_profile_queues_for_approval(client, db_session):
    """Student profile changes create a PendingProfileChange."""
    user = await _create_user(
        db_session, full_name="Original Name", role=UserRole.student
    )
    token = _token_for(user)

    response = await client.patch(
        "/api/users/me/profile",
        json={"full_name": "Queued Name"},
        headers=auth_header(token),
    )
    assert response.status_code == 200

    # Name should NOT be changed yet
    await db_session.refresh(user)
    assert user.full_name == "Original Name"

    # A pending change should exist
    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.field_name == "full_name",
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one_or_none()
    assert change is not None
    assert change.old_value == "Original Name"
    assert change.new_value == "Queued Name"


async def test_student_cannot_change_department(client, db_session):
    """Students cannot change their own department."""
    user = await _create_user(db_session, role=UserRole.student)
    token = _token_for(user)

    import uuid

    response = await client.patch(
        "/api/users/me/profile",
        json={"department_id": str(uuid.uuid4())},
        headers=auth_header(token),
    )
    assert response.status_code == 403


async def test_profile_update_no_changes_returns_400(client, db_session):
    """Submitting with no actual changes returns 400."""
    user = await _create_user(db_session, full_name="Same Name", role=UserRole.student)
    token = _token_for(user)

    response = await client.patch(
        "/api/users/me/profile",
        json={},  # No fields set
        headers=auth_header(token),
    )
    assert response.status_code == 400


async def test_duplicate_pending_change_replaces(client, db_session):
    """Submitting the same field again replaces the existing pending change."""
    user = await _create_user(db_session, full_name="Original", role=UserRole.student)
    token = _token_for(user)

    # First submission
    await client.patch(
        "/api/users/me/profile",
        json={"full_name": "First Change"},
        headers=auth_header(token),
    )

    # Second submission — should replace
    await client.patch(
        "/api/users/me/profile",
        json={"full_name": "Second Change"},
        headers=auth_header(token),
    )

    # Should only have ONE pending change for full_name
    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.field_name == "full_name",
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    changes = result.scalars().all()
    assert len(changes) == 1
    assert changes[0].new_value == "Second Change"


# ===========================================================================
# Get my pending changes
# ===========================================================================


async def test_get_my_pending_changes(client, db_session):
    """User can view their own pending changes."""
    user = await _create_user(db_session, full_name="Original", role=UserRole.student)
    token = _token_for(user)

    # Create a pending change
    await client.patch(
        "/api/users/me/profile",
        json={"full_name": "Pending Name"},
        headers=auth_header(token),
    )

    response = await client.get(
        "/api/users/me/pending-changes",
        headers=auth_header(token),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["field_name"] == "full_name"
    assert data[0]["new_value"] == "Pending Name"


# ===========================================================================
# Admin: list pending changes
# ===========================================================================


async def test_list_pending_changes_admin_only(client, student_token):
    """Non-admins cannot list all pending changes."""
    response = await client.get(
        "/api/users/pending-changes",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_list_pending_changes_with_filter(client, admin_token, db_session):
    """Admin can filter pending changes by status."""
    user = await _create_user(
        db_session, full_name="Filter Test", role=UserRole.student
    )
    token = _token_for(user)

    # Create a pending change
    await client.patch(
        "/api/users/me/profile",
        json={"full_name": "Filtered Name"},
        headers=auth_header(token),
    )

    # Filter for pending
    response = await client.get(
        "/api/users/pending-changes?status=pending",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0
    assert all(item["status"] == "pending" for item in data["items"])


# ===========================================================================
# Admin: approve / reject
# ===========================================================================


async def test_approve_pending_change(client, admin_token, db_session):
    """Approving a change applies it to the user."""
    user = await _create_user(
        db_session, full_name="Before Approval", role=UserRole.student
    )
    token = _token_for(user)

    # Submit a change
    await client.patch(
        "/api/users/me/profile",
        json={"full_name": "After Approval"},
        headers=auth_header(token),
    )

    # Find the pending change
    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one()
    change_id = str(change.id)

    # Approve it
    response = await client.post(
        f"/api/users/pending-changes/{change_id}/approve",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 204

    # Verify the change was applied
    await db_session.refresh(user)
    assert user.full_name == "After Approval"

    await db_session.refresh(change)
    assert change.status == PendingChangeStatus.approved
    assert change.reviewed_at is not None


async def test_reject_pending_change(client, admin_token, db_session):
    """Rejecting a change does NOT apply it to the user."""
    user = await _create_user(
        db_session, full_name="Before Rejection", role=UserRole.student
    )
    token = _token_for(user)

    # Submit a change
    await client.patch(
        "/api/users/me/profile",
        json={"full_name": "After Rejection"},
        headers=auth_header(token),
    )

    # Find the pending change
    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one()
    change_id = str(change.id)

    # Reject it
    response = await client.post(
        f"/api/users/pending-changes/{change_id}/reject",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 204

    # Verify the change was NOT applied
    await db_session.refresh(user)
    assert user.full_name == "Before Rejection"

    await db_session.refresh(change)
    assert change.status == PendingChangeStatus.rejected


async def test_cannot_approve_already_reviewed(client, admin_token, db_session):
    """Approving an already-reviewed change returns 400."""
    user = await _create_user(
        db_session, full_name="Already Reviewed", role=UserRole.student
    )
    token = _token_for(user)

    await client.patch(
        "/api/users/me/profile",
        json={"full_name": "New Name"},
        headers=auth_header(token),
    )

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one()
    change_id = str(change.id)

    # Approve once
    await client.post(
        f"/api/users/pending-changes/{change_id}/approve",
        headers=auth_header(admin_token),
    )

    # Try to approve again
    response = await client.post(
        f"/api/users/pending-changes/{change_id}/approve",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 400
    assert "already" in response.json()["detail"].lower()


async def test_approve_nonexistent_change(client, admin_token):
    """Approving a non-existent change returns 404."""
    import uuid

    response = await client.post(
        f"/api/users/pending-changes/{uuid.uuid4()}/approve",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 404
