import uuid


from app.models.rotation import StudentRotation
from app.models.user import User, UserRole
from app.core.security import hash_password, create_access_token
from tests.conftest import auth_header
from tests.factories import _random_suffix, create_department


async def test_get_current_rotation_student_only(client, supervisor_token):
    """Non-students get 403 when accessing current rotation."""
    response = await client.get(
        "/api/rotations/current",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 403


async def test_get_current_rotation_returns_current(
    client, db_session, fresh_student
):
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


async def test_get_current_rotation_none_when_not_set(client, db_session, fresh_student):
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


async def test_create_rotation_success(
    client, db_session, fresh_student
):
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


async def test_create_rotation_closes_previous(
    client, db_session, fresh_student
):
    """Previous rotation's is_current set to False when creating new one."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept1 = await create_department(db_session)
    dept2 = await create_department(db_session)

    # Create first rotation
    rotation1 = StudentRotation(
        student_id=fresh_student.id,
        department_id=dept1.id,
        is_current=True,
    )
    db_session.add(rotation1)
    await db_session.commit()

    # Create second rotation via API
    response = await client.post(
        "/api/rotations",
        json={"department_id": str(dept2.id)},
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 201

    # Check first rotation was closed
    await db_session.refresh(rotation1)
    assert rotation1.is_current is False
    assert rotation1.ended_at is not None


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


async def test_get_rotation_history_returns_all(
    client, db_session, fresh_student
):
    """Returns all rotations for the student."""
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")
    dept1 = await create_department(db_session)
    dept2 = await create_department(db_session)
    dept3 = await create_department(db_session)

    rotations = [
        StudentRotation(student_id=fresh_student.id, department_id=dept1.id, is_current=False),
        StudentRotation(student_id=fresh_student.id, department_id=dept2.id, is_current=False),
        StudentRotation(student_id=fresh_student.id, department_id=dept3.id, is_current=True),
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


async def test_get_student_rotation_supervisor_assigned_only(
    client, supervisor_token, db_session
):
    """Supervisors can access the endpoint."""
    suffix = _random_suffix()
    student = User(
        email=f"super_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Super Student",
        student_id=f"SS{suffix}",
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
