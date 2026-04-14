import uuid

from app.models.rotation import StudentRotation
from app.models.user import User, UserRole
from app.core.security import hash_password, create_access_token
from tests.conftest import auth_header
from tests.factories import _random_suffix, create_department


# ---------------------------------------------------------------------------
# Existing tests (preserved / updated)
# ---------------------------------------------------------------------------


async def test_get_current_rotation_student_only(client, supervisor_token):
    """Non-students get 403 when accessing current rotation."""
    response = await client.get(
        "/api/rotations/current",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 403


async def test_get_current_rotation_returns_current(client, db_session, fresh_student):
    """Returns is_current=True rotation."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept = await create_department(db_session)

    rotation = StudentRotation(
        student_id=fresh_student.id,
        department_id=dept.id,
        is_current=True,
    )
    db_session.add(rotation)
    await db_session.commit()

    response = await client.get(
        "/api/rotations/current",
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["is_current"] is True
    assert data["department_id"] == str(dept.id)


async def test_get_current_rotation_none_when_not_set(
    client, db_session, fresh_student
):
    """Returns null if no rotation is set."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    response = await client.get(
        "/api/rotations/current",
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data is None


async def test_create_rotation_student_only(client, admin_token):
    """Non-students get 403 when creating rotation."""
    response = await client.post(
        "/api/rotations",
        json={"department_id": str(uuid.uuid4())},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 403


async def test_create_rotation_success(client, db_session, fresh_student):
    """Student creates rotation successfully."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept = await create_department(db_session)

    response = await client.post(
        "/api/rotations",
        json={"department_id": str(dept.id)},
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == str(fresh_student.id)
    assert data["department_id"] == str(dept.id)
    assert data["is_current"] is True
    assert data["started_at"] is not None


async def test_create_rotation_with_days_offset(client, db_session, fresh_student):
    """Student can specify days_offset when creating rotation."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept = await create_department(db_session)

    response = await client.post(
        "/api/rotations",
        json={"department_id": str(dept.id), "days_offset": 5},
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["days_offset"] == 5


async def test_create_rotation_default_days_offset_zero(
    client, db_session, fresh_student
):
    """days_offset defaults to 0 when not provided."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept = await create_department(db_session)

    response = await client.post(
        "/api/rotations",
        json={"department_id": str(dept.id)},
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["days_offset"] == 0


async def test_create_rotation_days_offset_negative_rejected(
    client, db_session, fresh_student
):
    """Negative days_offset is rejected by validation."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept = await create_department(db_session)

    response = await client.post(
        "/api/rotations",
        json={"department_id": str(dept.id), "days_offset": -1},
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 422


async def test_create_rotation_locked_when_already_assigned(
    client, db_session, fresh_student
):
    """Student cannot switch departments once assigned — returns 400."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept1 = await create_department(db_session)
    dept2 = await create_department(db_session)

    # Assign to dept1 first
    response = await client.post(
        "/api/rotations",
        json={"department_id": str(dept1.id)},
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 201

    # Attempt to switch to dept2 — should be blocked
    response = await client.post(
        "/api/rotations",
        json={"department_id": str(dept2.id)},
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 400
    assert "active department rotation" in response.json()["detail"]

    # Original rotation should still be active
    current = await client.get(
        "/api/rotations/current",
        headers=auth_header(fresh_token),
    )
    assert current.json()["department_id"] == str(dept1.id)


async def test_create_rotation_same_department_idempotent(
    client, db_session, fresh_student
):
    """Re-selecting the same department returns the existing rotation."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept = await create_department(db_session)

    # First assignment
    r1 = await client.post(
        "/api/rotations",
        json={"department_id": str(dept.id)},
        headers=auth_header(fresh_token),
    )
    assert r1.status_code == 201
    r1_id = r1.json()["id"]

    # Same department again — should return same rotation
    r2 = await client.post(
        "/api/rotations",
        json={"department_id": str(dept.id)},
        headers=auth_header(fresh_token),
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == r1_id


async def test_create_rotation_requires_department(client, student_token):
    """Missing dept_id returns 422 validation error."""
    response = await client.post(
        "/api/rotations",
        json={},
        headers=auth_header(student_token),
    )
    assert response.status_code == 422


async def test_get_rotation_history_admin_or_supervisor(client, student_token):
    """Students can access their own rotation history."""
    response = await client.get(
        "/api/rotations/history",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200


async def test_get_rotation_history_returns_all(client, db_session, fresh_student):
    """Returns all rotations for the student."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept1 = await create_department(db_session)
    dept2 = await create_department(db_session)
    dept3 = await create_department(db_session)

    rotations = [
        StudentRotation(
            student_id=fresh_student.id, department_id=dept1.id, is_current=False
        ),
        StudentRotation(
            student_id=fresh_student.id, department_id=dept2.id, is_current=False
        ),
        StudentRotation(
            student_id=fresh_student.id, department_id=dept3.id, is_current=True
        ),
    ]
    db_session.add_all(rotations)
    await db_session.commit()

    response = await client.get(
        "/api/rotations/history",
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    dept_ids = {r["department_id"] for r in data["items"]}
    assert str(dept1.id) in dept_ids
    assert str(dept2.id) in dept_ids
    assert str(dept3.id) in dept_ids


async def test_get_rotation_history_includes_inactive(
    client, db_session, fresh_student
):
    """Shows ended rotations (is_current=False) in history."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept1 = await create_department(db_session)
    dept2 = await create_department(db_session)

    old_rotation = StudentRotation(
        student_id=fresh_student.id,
        department_id=dept1.id,
        is_current=False,
        ended_at=None,
    )
    db_session.add(old_rotation)

    current_rotation = StudentRotation(
        student_id=fresh_student.id,
        department_id=dept2.id,
        is_current=True,
    )
    db_session.add(current_rotation)
    await db_session.commit()

    response = await client.get(
        "/api/rotations/history",
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert any(not r["is_current"] for r in data["items"])


async def test_get_student_rotation_supervisor_can_access(
    client, supervisor_token, db_session
):
    """Supervisors can access student rotation endpoint."""
    suffix = _random_suffix()
    student = User(
        email=f"super_student_{suffix}@test.com",
        password_hash=await hash_password("testpass123"),
        full_name="Super Student",
        institutional_id=f"SS{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)

    response = await client.get(
        f"/api/rotations/students/{student.id}/current",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200


async def test_get_student_rotation_not_found(client, supervisor_token):
    """Non-existent student returns null, not 404."""
    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/rotations/students/{fake_id}/current",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    assert response.json() is None


# ---------------------------------------------------------------------------
# NEW: Admin override department tests
# ---------------------------------------------------------------------------


async def test_admin_override_department_success(
    client, db_session, fresh_student, admin_token
):
    """Admin can change a student's department."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept1 = await create_department(db_session)
    dept2 = await create_department(db_session)

    # Student assigns to dept1
    r1 = await client.post(
        "/api/rotations",
        json={"department_id": str(dept1.id)},
        headers=auth_header(fresh_token),
    )
    assert r1.status_code == 201

    # Admin overrides to dept2
    response = await client.post(
        f"/api/rotations/students/{fresh_student.id}/override-department",
        json={"department_id": str(dept2.id)},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["department_id"] == str(dept2.id)
    assert data["is_current"] is True
    assert data["student_id"] == str(fresh_student.id)

    # Verify student's current rotation is now dept2
    current = await client.get(
        "/api/rotations/current",
        headers=auth_header(fresh_token),
    )
    assert current.json()["department_id"] == str(dept2.id)


async def test_admin_override_preserves_history(
    client, db_session, fresh_student, admin_token
):
    """Admin override deactivates old rotation (preserving it in history)."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept1 = await create_department(db_session)
    dept2 = await create_department(db_session)

    # Student assigns to dept1
    await client.post(
        "/api/rotations",
        json={"department_id": str(dept1.id)},
        headers=auth_header(fresh_token),
    )

    # Admin overrides to dept2
    await client.post(
        f"/api/rotations/students/{fresh_student.id}/override-department",
        json={"department_id": str(dept2.id)},
        headers=auth_header(admin_token),
    )

    # History should show both rotations
    history = await client.get(
        "/api/rotations/history",
        headers=auth_header(fresh_token),
    )
    items = history.json()["items"]
    assert len(items) == 2
    dept_ids = {i["department_id"] for i in items}
    assert str(dept1.id) in dept_ids
    assert str(dept2.id) in dept_ids

    # Old rotation should be inactive
    old = [i for i in items if i["department_id"] == str(dept1.id)][0]
    assert old["is_current"] is False


async def test_admin_override_student_only(client, db_session, admin_token):
    """Override endpoint rejects non-student user IDs."""
    suffix = _random_suffix()
    supervisor = User(
        email=f"override_sup_{suffix}@test.com",
        password_hash=await hash_password("testpass123"),
        full_name="Override Supervisor",
        institutional_id=f"OS{suffix}",
        role=UserRole.supervisor,
        is_active=True,
    )
    db_session.add(supervisor)
    await db_session.commit()
    await db_session.refresh(supervisor)

    dept = await create_department(db_session)
    response = await client.post(
        f"/api/rotations/students/{supervisor.id}/override-department",
        json={"department_id": str(dept.id)},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 404
    assert "Student not found" in response.json()["detail"]


async def test_admin_override_requires_admin(
    client, db_session, fresh_student, supervisor_token
):
    """Non-admin users cannot access override endpoint."""
    dept = await create_department(db_session)
    response = await client.post(
        f"/api/rotations/students/{fresh_student.id}/override-department",
        json={"department_id": str(dept.id)},
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 403


async def test_admin_override_inactive_department_rejected(
    client, db_session, fresh_student, admin_token
):
    """Cannot override to an inactive department."""
    dept = await create_department(db_session, is_active=False)
    response = await client.post(
        f"/api/rotations/students/{fresh_student.id}/override-department",
        json={"department_id": str(dept.id)},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 404
    assert "Department not found" in response.json()["detail"]


async def test_admin_override_no_existing_rotation(
    client, db_session, fresh_student, admin_token
):
    """Admin can assign department even if student has no current rotation."""
    dept = await create_department(db_session)
    response = await client.post(
        f"/api/rotations/students/{fresh_student.id}/override-department",
        json={"department_id": str(dept.id)},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["department_id"] == str(dept.id)
    assert data["is_current"] is True
