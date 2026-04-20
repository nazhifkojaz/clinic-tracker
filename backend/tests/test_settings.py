"""Tests for self-service password change, profile update, and pending changes approval."""

import uuid

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


async def test_student_can_request_department_change(client, db_session):
    """Students can request a department change (queued for approval)."""
    from app.models.department import Department

    dept = Department(name="Test Dept", is_active=True)
    db_session.add(dept)
    await db_session.flush()

    user = await _create_user(db_session, role=UserRole.student)
    token = _token_for(user)

    response = await client.patch(
        "/api/users/me/profile",
        json={"department_id": str(dept.id)},
        headers=auth_header(token),
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.field_name == "department_id",
        )
    )
    change = result.scalar_one()
    assert change.new_value == str(dept.id)
    assert change.status == PendingChangeStatus.pending


async def test_student_department_change_validates_dept(client, db_session):
    """Students cannot request change to an inactive or nonexistent department."""
    user = await _create_user(db_session, role=UserRole.student)
    token = _token_for(user)

    response = await client.patch(
        "/api/users/me/profile",
        json={"department_id": str(uuid.uuid4())},
        headers=auth_header(token),
    )
    assert response.status_code == 400


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


async def test_duplicate_pending_change_blocked(client, db_session):
    """Submitting the same field again is blocked while a request is pending."""
    user = await _create_user(db_session, full_name="Original", role=UserRole.student)
    token = _token_for(user)

    # First submission
    response = await client.patch(
        "/api/users/me/profile",
        json={"full_name": "First Change"},
        headers=auth_header(token),
    )
    assert response.status_code == 200

    # Second submission — should be blocked
    response = await client.patch(
        "/api/users/me/profile",
        json={"full_name": "Second Change"},
        headers=auth_header(token),
    )
    assert response.status_code == 409

    # Original pending change should still be there
    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.field_name == "full_name",
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    changes = result.scalars().all()
    assert len(changes) == 1
    assert changes[0].new_value == "First Change"


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
    response = await client.post(
        f"/api/users/pending-changes/{uuid.uuid4()}/approve",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 404


# ===========================================================================
# Email change
# ===========================================================================


async def test_student_email_change_request(client, db_session):
    """Student can submit an email change request."""
    user = await _create_user(
        db_session, email="old_email@test.com", role=UserRole.student
    )
    token = _token_for(user)

    response = await client.patch(
        "/api/users/me/profile",
        json={"email": "new_email@test.com"},
        headers=auth_header(token),
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.field_name == "email",
        )
    )
    change = result.scalar_one()
    assert change.old_value == "old_email@test.com"
    assert change.new_value == "new_email@test.com"
    assert change.status == PendingChangeStatus.pending


async def test_approve_email_change(client, admin_token, db_session):
    """Approving an email change updates email and sets email_verified=False."""
    user = await _create_user(
        db_session, email="pre_approval@test.com", role=UserRole.student
    )
    token = _token_for(user)

    await client.patch(
        "/api/users/me/profile",
        json={"email": "post_approval@test.com"},
        headers=auth_header(token),
    )

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one()

    response = await client.post(
        f"/api/users/pending-changes/{change.id}/approve",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 204

    await db_session.refresh(user)
    assert user.email == "post_approval@test.com"
    assert user.email_verified is False


async def test_reject_email_change(client, admin_token, db_session):
    """Rejecting an email change leaves email unchanged."""
    user = await _create_user(
        db_session, email="unchanged@test.com", role=UserRole.student
    )
    token = _token_for(user)

    await client.patch(
        "/api/users/me/profile",
        json={"email": "changed@test.com"},
        headers=auth_header(token),
    )

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one()

    await client.post(
        f"/api/users/pending-changes/{change.id}/reject",
        headers=auth_header(admin_token),
    )

    await db_session.refresh(user)
    assert user.email == "unchanged@test.com"


async def test_duplicate_email_returns_409(client, db_session):
    """Submitting an email already in use returns 409."""
    await _create_user(db_session, email="taken@test.com")
    user = await _create_user(
        db_session, email="unique@test.com", role=UserRole.student
    )
    token = _token_for(user)

    response = await client.patch(
        "/api/users/me/profile",
        json={"email": "taken@test.com"},
        headers=auth_header(token),
    )
    assert response.status_code == 409


# ===========================================================================
# Student department change — approval
# ===========================================================================


async def test_approve_student_department_change(client, admin_token, db_session):
    """Approving a student department change triggers rotation override."""
    from tests.factories import create_department

    dept1 = await create_department(db_session, name="Original Dept")
    dept2 = await create_department(db_session, name="New Dept")

    user = await _create_user(db_session, department_id=dept1.id, role=UserRole.student)
    token = _token_for(user)

    await client.patch(
        "/api/users/me/profile",
        json={"department_id": str(dept2.id)},
        headers=auth_header(token),
    )

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.field_name == "department_id",
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one()

    await client.post(
        f"/api/users/pending-changes/{change.id}/approve",
        headers=auth_header(admin_token),
    )

    await db_session.refresh(user)
    assert user.department_id == dept2.id


# ===========================================================================
# Supervisor change
# ===========================================================================


async def test_student_supervisor_change_request(client, db_session):
    """Student can submit a supervisor change request."""
    new_sv = await _create_user(
        db_session,
        full_name="New Supervisor",
        role=UserRole.supervisor,
        email=f"new_sv_{_random_suffix()}@test.com",
    )
    user = await _create_user(db_session, role=UserRole.student)
    token = _token_for(user)

    response = await client.patch(
        "/api/users/me/profile",
        json={"supervisor_id": str(new_sv.id)},
        headers=auth_header(token),
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.field_name == "supervisor_id",
        )
    )
    change = result.scalar_one()
    assert change.new_value == str(new_sv.id)
    assert change.old_value == "None"


async def test_approve_supervisor_change(client, admin_token, db_session):
    """Approving a supervisor change removes old assignment and creates new one."""
    from app.models.assignment import AssignmentType, SupervisorAssignment

    old_sv = await _create_user(
        db_session,
        full_name="Old SV",
        role=UserRole.supervisor,
        email=f"approve_old_sv_{_random_suffix()}@test.com",
    )
    new_sv = await _create_user(
        db_session,
        full_name="New SV",
        role=UserRole.supervisor,
        email=f"approve_new_sv_{_random_suffix()}@test.com",
    )
    user = await _create_user(db_session, role=UserRole.student)

    # Create existing assignment
    assignment = SupervisorAssignment(
        supervisor_id=old_sv.id,
        student_id=user.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()

    token = _token_for(user)
    await client.patch(
        "/api/users/me/profile",
        json={"supervisor_id": str(new_sv.id)},
        headers=auth_header(token),
    )

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one()

    await client.post(
        f"/api/users/pending-changes/{change.id}/approve",
        headers=auth_header(admin_token),
    )

    # Old assignment should be gone, new one should exist
    result = await db_session.execute(
        select(SupervisorAssignment).where(
            SupervisorAssignment.student_id == user.id,
            SupervisorAssignment.assignment_type == AssignmentType.primary,
        )
    )
    new_assignment = result.scalar_one()
    assert new_assignment.supervisor_id == new_sv.id


async def test_invalid_supervisor_returns_400(client, db_session):
    """Requesting a nonexistent supervisor returns 400."""
    import uuid

    user = await _create_user(db_session, role=UserRole.student)
    token = _token_for(user)

    response = await client.patch(
        "/api/users/me/profile",
        json={"supervisor_id": str(uuid.uuid4())},
        headers=auth_header(token),
    )
    assert response.status_code == 400


# ===========================================================================
# Student removal
# ===========================================================================


async def test_supervisor_student_removal_request(client, db_session):
    """Supervisor can submit a student removal request with reason."""
    from app.models.assignment import AssignmentType, SupervisorAssignment

    student = await _create_user(
        db_session,
        full_name="Removal Student",
        role=UserRole.student,
        email=f"removal_stu_{_random_suffix()}@test.com",
    )
    sv = await _create_user(
        db_session,
        full_name="Removal SV",
        role=UserRole.supervisor,
        email=f"removal_sv_{_random_suffix()}@test.com",
    )
    assignment = SupervisorAssignment(
        supervisor_id=sv.id,
        student_id=student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()

    token = _token_for(sv)
    response = await client.patch(
        "/api/users/me/profile",
        json={"remove_student_id": str(student.id), "reason": "Graduating"},
        headers=auth_header(token),
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == sv.id,
            PendingProfileChange.field_name == "remove_student_id",
        )
    )
    change = result.scalar_one()
    assert change.new_value == str(student.id)
    assert change.reason == "Graduating"


async def test_approve_student_removal(client, admin_token, db_session):
    """Approving a student removal deletes the primary assignment."""
    from app.models.assignment import AssignmentType, SupervisorAssignment

    student = await _create_user(
        db_session,
        full_name="Approved Removal Student",
        role=UserRole.student,
        email=f"app_rem_stu_{_random_suffix()}@test.com",
    )
    sv = await _create_user(
        db_session,
        full_name="Approved Removal SV",
        role=UserRole.supervisor,
        email=f"app_rem_sv_{_random_suffix()}@test.com",
    )
    assignment = SupervisorAssignment(
        supervisor_id=sv.id,
        student_id=student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()

    token = _token_for(sv)
    await client.patch(
        "/api/users/me/profile",
        json={"remove_student_id": str(student.id)},
        headers=auth_header(token),
    )

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == sv.id,
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one()

    await client.post(
        f"/api/users/pending-changes/{change.id}/approve",
        headers=auth_header(admin_token),
    )

    result = await db_session.execute(
        select(SupervisorAssignment).where(
            SupervisorAssignment.supervisor_id == sv.id,
            SupervisorAssignment.student_id == student.id,
            SupervisorAssignment.assignment_type == AssignmentType.primary,
        )
    )
    assert result.scalar_one_or_none() is None


async def test_removal_unassigned_student_returns_400(client, db_session):
    """Supervisor cannot request removal of a student not assigned to them."""
    student = await _create_user(
        db_session,
        role=UserRole.student,
        email=f"unassigned_stu_{_random_suffix()}@test.com",
    )
    sv = await _create_user(
        db_session,
        role=UserRole.supervisor,
        email=f"unassigned_sv_{_random_suffix()}@test.com",
    )
    token = _token_for(sv)

    response = await client.patch(
        "/api/users/me/profile",
        json={"remove_student_id": str(student.id)},
        headers=auth_header(token),
    )
    assert response.status_code == 400


# ===========================================================================
# Cross-role validation
# ===========================================================================


async def test_student_cannot_use_remove_student_id(client, db_session):
    """Students get 403 when trying to use remove_student_id."""
    user = await _create_user(db_session, role=UserRole.student)
    token = _token_for(user)

    response = await client.patch(
        "/api/users/me/profile",
        json={"remove_student_id": str(uuid.uuid4())},
        headers=auth_header(token),
    )
    assert response.status_code == 403


async def test_supervisor_cannot_use_supervisor_id(client, db_session):
    """Supervisors get 403 when trying to use supervisor_id."""
    sv = await _create_user(
        db_session,
        role=UserRole.supervisor,
        email=f"xrole_sv_{_random_suffix()}@test.com",
    )
    token = _token_for(sv)

    response = await client.patch(
        "/api/users/me/profile",
        json={"supervisor_id": str(uuid.uuid4())},
        headers=auth_header(token),
    )
    assert response.status_code == 403


# ===========================================================================
# Notifications
# ===========================================================================


async def test_new_request_notifies_admin(client, admin_user, db_session):
    """Submitting a change request creates a Notification for active admins."""
    from app.models.notification import Notification

    user = await _create_user(
        db_session, full_name="Notify Test", role=UserRole.student
    )
    token = _token_for(user)

    await client.patch(
        "/api/users/me/profile",
        json={"full_name": "Notify Name"},
        headers=auth_header(token),
    )

    result = await db_session.execute(
        select(Notification).where(
            Notification.recipient_id == admin_user.id,
            Notification.sender_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()
    assert notification is not None
    assert "profile change" in notification.subject.lower()


async def test_approval_notifies_user(client, admin_token, admin_user, db_session):
    """Approving a change creates a Notification for the requesting user."""
    from app.models.notification import Notification

    user = await _create_user(
        db_session, full_name="Approval Notify", role=UserRole.student
    )
    token = _token_for(user)

    await client.patch(
        "/api/users/me/profile",
        json={"full_name": "Approved Name"},
        headers=auth_header(token),
    )

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one()

    await client.post(
        f"/api/users/pending-changes/{change.id}/approve",
        headers=auth_header(admin_token),
    )

    result = await db_session.execute(
        select(Notification).where(
            Notification.recipient_id == user.id,
            Notification.sender_id == admin_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    assert notification is not None
    assert "approved" in notification.subject.lower()


async def test_rejection_notifies_user(client, admin_token, admin_user, db_session):
    """Rejecting a change creates a Notification for the requesting user."""
    from app.models.notification import Notification

    user = await _create_user(
        db_session, full_name="Rejection Notify", role=UserRole.student
    )
    token = _token_for(user)

    await client.patch(
        "/api/users/me/profile",
        json={"full_name": "Rejected Name"},
        headers=auth_header(token),
    )

    result = await db_session.execute(
        select(PendingProfileChange).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    change = result.scalar_one()

    await client.post(
        f"/api/users/pending-changes/{change.id}/reject",
        headers=auth_header(admin_token),
    )

    result = await db_session.execute(
        select(Notification).where(
            Notification.recipient_id == user.id,
            Notification.sender_id == admin_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    assert notification is not None
    assert "rejected" in notification.subject.lower()
