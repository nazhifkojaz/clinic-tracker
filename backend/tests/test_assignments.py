import uuid

from sqlalchemy import select

from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.rotation import StudentRotation
from app.models.user import User, UserRole
from app.core.security import hash_password
from tests.conftest import auth_header
from tests.factories import _random_suffix, create_department


async def test_list_assignments_supervisor_or_admin(client, student_token):
    """Students get 403 when listing assignments."""
    response = await client.get(
        "/api/assignments",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_list_assignments_filters_by_type(
    client, admin_token, db_session, supervisor_user
):
    """Primary vs department filter works correctly."""
    # Create a test student
    suffix = _random_suffix()
    student = User(
        email=f"filter_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Filter Student",
        student_id=f"FS{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)

    # Create a test department
    dept = await create_department(db_session, name="Filter Dept")

    # Create primary assignment
    primary = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(primary)

    # Create department assignment
    dept_assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        assignment_type=AssignmentType.department,
        department_id=dept.id,
    )
    db_session.add(dept_assignment)
    await db_session.commit()

    # Filter by primary
    response = await client.get(
        "/api/assignments?assignment_type=primary",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert all(a["assignment_type"] == "primary" for a in data["items"])

    # Filter by department
    response = await client.get(
        "/api/assignments?assignment_type=department",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert all(a["assignment_type"] == "department" for a in data["items"])


async def test_list_assignments_paginates(
    client, admin_token, db_session, supervisor_user
):
    """Pagination works - current implementation returns all."""
    # Create multiple assignments
    suffix = _random_suffix()
    for i in range(5):
        student = User(
            email=f"page_student_{i}_{suffix}@test.com",
            password_hash=hash_password("testpass123"),
            full_name=f"Page Student {i}",
            student_id=f"PS{i}{suffix}",
            role=UserRole.student,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assignment = SupervisorAssignment(
            supervisor_id=supervisor_user.id,
            student_id=student.id,
            assignment_type=AssignmentType.primary,
        )
        db_session.add(assignment)
    await db_session.commit()

    response = await client.get(
        "/api/assignments",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 5


async def test_get_my_students_supervisor_only(client, student_token):
    """Non-supervisors get 403 when accessing my-students."""
    response = await client.get(
        "/api/assignments/my-students",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_get_my_students_returns_only_assigned(
    client, supervisor_token, db_session, supervisor_user
):
    """Supervisor sees only their assigned students."""
    # Create another supervisor
    suffix = _random_suffix()
    other_supervisor = User(
        email=f"other_sup_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Other Supervisor",
        role=UserRole.supervisor,
        is_active=True,
    )
    db_session.add(other_supervisor)
    await db_session.flush()

    # Create two students
    student1 = User(
        email=f"my_student1_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="My Student 1",
        student_id=f"MS1{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    student2 = User(
        email=f"my_student2_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="My Student 2",
        student_id=f"MS2{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add_all([student1, student2])
    await db_session.flush()

    # Assign student1 to current supervisor
    assignment1 = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=student1.id,
        assignment_type=AssignmentType.primary,
    )
    # Assign student2 to other supervisor
    assignment2 = SupervisorAssignment(
        supervisor_id=other_supervisor.id,
        student_id=student2.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add_all([assignment1, assignment2])
    await db_session.commit()

    response = await client.get(
        "/api/assignments/my-students",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    data = response.json()
    student_ids = [s["student_id"] for s in data]
    assert str(student1.id) in student_ids
    assert str(student2.id) not in student_ids


async def test_get_my_students_includes_dept_students(
    client, supervisor_token, db_session, supervisor_user
):
    """Department assignments include students rotating in that department."""
    suffix = _random_suffix()

    # Create a department
    dept = await create_department(db_session, name="Rotation Dept")

    # Create a student
    student = User(
        email=f"dept_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Dept Student",
        student_id=f"DS{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    # Create department assignment for supervisor
    dept_assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        assignment_type=AssignmentType.department,
        department_id=dept.id,
    )
    db_session.add(dept_assignment)

    # Create student rotation in that department
    rotation = StudentRotation(
        student_id=student.id,
        department_id=dept.id,
        is_current=True,
    )
    db_session.add(rotation)
    await db_session.commit()

    response = await client.get(
        "/api/assignments/my-students",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    data = response.json()
    student_ids = [s["student_id"] for s in data]
    assert str(student.id) in student_ids


async def test_get_my_students_student_details_complete(
    client, supervisor_token, db_session, supervisor_user
):
    """Returns full student info including email and student_code."""
    suffix = _random_suffix()
    student = User(
        email=f"detail_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Detail Student",
        student_id=f"DT{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()

    response = await client.get(
        "/api/assignments/my-students",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    student_data = next((s for s in data if s["student_id"] == str(student.id)), None)
    assert student_data is not None
    assert student_data["student_name"] == "Detail Student"
    assert student_data["student_email"] == f"detail_student_{suffix}@test.com"
    assert student_data["student_code"] == f"DT{suffix}"


async def test_create_assignment_admin_only(client, student_token):
    """Non-admins cannot create assignments."""
    response = await client.post(
        "/api/assignments",
        json={
            "supervisor_id": str(uuid.uuid4()),
            "assignment_type": "primary",
            "student_id": str(uuid.uuid4()),
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_create_primary_assignment_success(
    client, admin_token, db_session, supervisor_user
):
    """Primary assignment created successfully."""
    suffix = _random_suffix()
    student = User(
        email=f"prim_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Primary Student",
        student_id=f"PR{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)

    response = await client.post(
        "/api/assignments",
        json={
            "supervisor_id": str(supervisor_user.id),
            "assignment_type": "primary",
            "student_id": str(student.id),
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["assignment_type"] == "primary"
    assert data["supervisor_id"] == str(supervisor_user.id)
    assert data["student_id"] == str(student.id)


async def test_create_department_assignment_success(
    client, admin_token, db_session, supervisor_user
):
    """Department assignment created successfully."""
    dept = await create_department(db_session, name="Assignment Dept")

    response = await client.post(
        "/api/assignments",
        json={
            "supervisor_id": str(supervisor_user.id),
            "assignment_type": "department",
            "department_id": str(dept.id),
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["assignment_type"] == "department"
    assert data["supervisor_id"] == str(supervisor_user.id)
    assert data["department_id"] == str(dept.id)
    assert data["student_id"] is None


async def test_create_assignment_validates_type_specific_fields(
    client, admin_token, db_session, supervisor_user
):
    """Student for primary, dept_id for department validation."""
    suffix = _random_suffix()
    student = User(
        email=f"valid_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Valid Student",
        student_id=f"VD{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)

    # Primary without student_id should fail
    response = await client.post(
        "/api/assignments",
        json={
            "supervisor_id": str(supervisor_user.id),
            "assignment_type": "primary",
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 422

    # Department without department_id should fail
    response = await client.post(
        "/api/assignments",
        json={
            "supervisor_id": str(supervisor_user.id),
            "assignment_type": "department",
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 422


async def test_create_assignment_mutual_exclusivity(
    client, admin_token, db_session, supervisor_user
):
    """Can't specify both student_id and department_id."""
    suffix = _random_suffix()
    student = User(
        email=f"mutual_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Mutual Student",
        student_id=f"MT{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    dept = await create_department(db_session, name="Mutual Dept")

    # Primary with department_id should fail
    response = await client.post(
        "/api/assignments",
        json={
            "supervisor_id": str(supervisor_user.id),
            "assignment_type": "primary",
            "student_id": str(student.id),
            "department_id": str(dept.id),
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 422

    # Department with student_id should fail
    response = await client.post(
        "/api/assignments",
        json={
            "supervisor_id": str(supervisor_user.id),
            "assignment_type": "department",
            "department_id": str(dept.id),
            "student_id": str(student.id),
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 422


async def test_create_assignment_duplicate_returns_409(
    client, admin_token, db_session, supervisor_user
):
    """Duplicate assignment rejected with 409."""
    suffix = _random_suffix()
    student = User(
        email=f"dup_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Dup Student",
        student_id=f"DP{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    # Create first assignment
    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()

    # Try to create duplicate
    response = await client.post(
        "/api/assignments",
        json={
            "supervisor_id": str(supervisor_user.id),
            "assignment_type": "primary",
            "student_id": str(student.id),
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 409


async def test_delete_assignment_admin_only(
    client, student_token, db_session, supervisor_user
):
    """Non-admins cannot delete assignments."""
    suffix = _random_suffix()
    student = User(
        email=f"del_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Delete Student",
        student_id=f"DL{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()
    await db_session.refresh(assignment)

    response = await client.delete(
        f"/api/assignments/{assignment.id}",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_delete_assignment_success(
    client, admin_token, db_session, supervisor_user
):
    """Assignment removed successfully."""
    suffix = _random_suffix()
    student = User(
        email=f"del_ok_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Delete OK Student",
        student_id=f"DOK{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()
    await db_session.refresh(assignment)

    assignment_id = assignment.id

    response = await client.delete(
        f"/api/assignments/{assignment_id}",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 204

    # Verify it's deleted
    result = await db_session.execute(
        select(SupervisorAssignment).where(SupervisorAssignment.id == assignment_id)
    )
    assert result.scalar_one_or_none() is None
