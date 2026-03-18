import random
import string

from sqlalchemy import select

from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.notification import Notification
from app.models.rotation import StudentRotation
from app.models.user import User, UserRole
from tests.conftest import auth_header
from tests.factories import create_department


def _random_suffix() -> str:
    """Generate a random suffix for unique names."""
    return "".join(random.choices(string.ascii_lowercase, k=8))


async def _create_student(db_session) -> User:
    """Helper to create a unique student for test isolation."""
    from app.core.security import hash_password

    student = User(
        email=f"student_{_random_suffix()}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Test Student",
        student_id=f"TS{_random_suffix()}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


async def test_supervisor_with_primary_assignment_can_notify_student(
    client, supervisor_user, supervisor_token, db_session
):
    """Supervisor with primary assignment can send notification to their student."""
    # Use a unique student to avoid test interference
    student = await _create_student(db_session)

    # Assign supervisor as primary supervisor of student
    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()

    response = await client.post(
        "/api/notifications/send",
        json={
            "recipient_ids": [str(student.id)],
            "subject": f"Test Subject {_random_suffix()}",
            "message": "Test message",
        },
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["recipient_id"] == str(student.id)


async def test_supervisor_with_department_assignment_can_notify_rotating_student(
    client, supervisor_user, supervisor_token, db_session
):
    """Supervisor with department assignment can notify students rotating in that department."""
    # Create department and assign supervisor to it
    dept = await create_department(db_session, name="Test Department")
    dept_assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        department_id=dept.id,
        assignment_type=AssignmentType.department,
    )
    db_session.add(dept_assignment)

    # Create a student currently rotating in that department
    student = await _create_student(db_session)

    rotation = StudentRotation(
        student_id=student.id,
        department_id=dept.id,
        is_current=True,
    )
    db_session.add(rotation)
    await db_session.commit()

    # Supervisor should be able to send notification to this student
    response = await client.post(
        "/api/notifications/send",
        json={
            "recipient_ids": [str(student.id)],
            "subject": f"Department Notice {_random_suffix()}",
            "message": "Please review your cases",
        },
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_supervisor_cannot_notify_student_not_in_their_department(
    client, supervisor_user, supervisor_token, db_session
):
    """
    Regression test for the bug: Supervisor with department assignment
    CANNOT notify student who is NOT rotating in their department.
    """
    # Create a unique student that is NOT assigned to the supervisor
    student = await _create_student(db_session)

    # Assign supervisor to a department
    dept = await create_department(db_session, name="Supervisor's Department")
    dept_assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        department_id=dept.id,
        assignment_type=AssignmentType.department,
    )
    db_session.add(dept_assignment)
    await db_session.commit()

    # Student is NOT rotating in supervisor's department (no rotation record)
    # Supervisor should NOT be able to send notification to this student
    response = await client.post(
        "/api/notifications/send",
        json={
            "recipient_ids": [str(student.id)],
            "subject": f"Unauthorized Notification {_random_suffix()}",
            "message": "This should fail",
        },
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 403
    assert "not assigned to student" in response.json()["detail"]


async def test_admin_can_notify_any_student(
    client, admin_token, db_session
):
    """Admins can send notifications to any student without assignment checks."""
    student = await _create_student(db_session)

    response = await client.post(
        "/api/notifications/send",
        json={
            "recipient_ids": [str(student.id)],
            "subject": f"Admin Notice {_random_suffix()}",
            "message": "From admin",
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_notification_requires_student_recipients(
    client, supervisor_token, admin_user, db_session
):
    """Recipients must be students - non-student IDs return 404 or 403."""
    # Create a unique subject for this test
    test_subject = f"Test Non-Student Recipient {_random_suffix()}"

    response = await client.post(
        "/api/notifications/send",
        json={
            "recipient_ids": [str(admin_user.id)],  # Admin is not a student
            "subject": test_subject,
            "message": "Test",
        },
        headers=auth_header(supervisor_token),
    )
    # Either 403 (not assigned) or 404 (not a student) is acceptable
    # The API checks assignment first (403), then validates student role (404)
    # Since supervisor is not assigned to admin_user, we get 403
    assert response.status_code in (403, 404)


async def test_notification_saves_to_database(
    client, supervisor_user, supervisor_token, db_session
):
    """Sending a notification creates a database record."""
    student = await _create_student(db_session)

    # Create assignment
    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()

    # Use a unique subject to avoid test interference
    test_subject = f"Database Test {_random_suffix()}"

    # Send notification
    await client.post(
        "/api/notifications/send",
        json={
            "recipient_ids": [str(student.id)],
            "subject": test_subject,
            "message": "Testing DB save",
        },
        headers=auth_header(supervisor_token),
    )

    # Verify in database - filter by subject to avoid counting other test data
    result = await db_session.execute(
        select(Notification).where(
            Notification.sender_id == supervisor_user.id,
            Notification.subject == test_subject,
        )
    )
    notifications = result.scalars().all()
    assert len(notifications) == 1
    assert notifications[0].recipient_id == student.id
    assert notifications[0].subject == test_subject
