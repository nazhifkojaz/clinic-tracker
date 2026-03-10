import random
import string

import pytest
from sqlalchemy import select

from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.rotation import StudentRotation
from app.models.submission import SubmissionStatus
from app.models.user import User, UserRole
from tests.conftest import auth_header
from tests.factories import create_category, create_department, create_submission


def _random_suffix() -> str:
    """Generate a random suffix for unique names."""
    return "".join(random.choices(string.ascii_lowercase, k=8))


@pytest.mark.anyio
async def test_student_dashboard_empty(client, student_user, student_token, db_session):
    """Student with no submissions should have 0% progress."""
    dept = await create_department(db_session)
    await create_category(db_session, dept.id, required_count=10)

    response = await client.get(
        "/api/dashboard/student",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["overall_completion_percentage"] == 0.0
    assert data["total_completed"] == 0


@pytest.mark.anyio
async def test_student_dashboard_only_approved_count(
    client, student_user, student_token, db_session
):
    """Only approved submissions should count toward completion."""
    # Get baseline before adding new submissions
    baseline_resp = await client.get(
        "/api/dashboard/student",
        headers=auth_header(student_token),
    )
    baseline = baseline_resp.json()
    baseline_completed = baseline["total_completed"]
    baseline_required = baseline["total_required"]

    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id, required_count=10)

    # Create submissions with different statuses
    await create_submission(
        db_session,
        student_user.id,
        dept.id,
        cat.id,
        case_count=3,
        status=SubmissionStatus.approved,
    )
    await create_submission(
        db_session,
        student_user.id,
        dept.id,
        cat.id,
        case_count=5,
        status=SubmissionStatus.pending,
    )
    await create_submission(
        db_session,
        student_user.id,
        dept.id,
        cat.id,
        case_count=2,
        status=SubmissionStatus.rejected,
    )

    response = await client.get(
        "/api/dashboard/student",
        headers=auth_header(student_token),
    )
    data = response.json()
    # Only the 3 approved cases should count
    assert data["total_completed"] == baseline_completed + 3
    assert data["total_required"] == baseline_required + 10


@pytest.mark.anyio
async def test_student_dashboard_multiple_categories(
    client, student_user, student_token, db_session
):
    """Dashboard should aggregate across multiple categories correctly."""
    # Get baseline
    baseline_resp = await client.get(
        "/api/dashboard/student",
        headers=auth_header(student_token),
    )
    baseline = baseline_resp.json()
    baseline_completed = baseline["total_completed"]
    baseline_required = baseline["total_required"]

    dept = await create_department(db_session)
    cat1 = await create_category(
        db_session, dept.id, name="Category 1", required_count=20
    )
    cat2 = await create_category(
        db_session, dept.id, name="Category 2", required_count=30
    )

    # Complete 10/20 of cat1 (50%) and 15/30 of cat2 (50%)
    await create_submission(
        db_session,
        student_user.id,
        dept.id,
        cat1.id,
        case_count=10,
        status=SubmissionStatus.approved,
    )
    await create_submission(
        db_session,
        student_user.id,
        dept.id,
        cat2.id,
        case_count=15,
        status=SubmissionStatus.approved,
    )

    response = await client.get(
        "/api/dashboard/student",
        headers=auth_header(student_token),
    )
    data = response.json()
    # Total: 50 required, 25 completed added to baseline
    assert data["total_required"] == baseline_required + 50
    assert data["total_completed"] == baseline_completed + 25
    # Overall percentage should be (baseline_completed + 25) / (baseline_required + 50) * 100
    expected_pct = (
        ((baseline_completed + 25) / (baseline_required + 50) * 100)
        if (baseline_required + 50) > 0
        else 0
    )
    assert abs(data["overall_completion_percentage"] - expected_pct) < 0.1


@pytest.mark.anyio
async def test_supervisor_dashboard_student_classification(
    client, supervisor_user, supervisor_token, db_session
):
    """Supervisor dashboard should return student status classification."""
    # Create a student and assign to supervisor
    student = User(
        email=f"student_{_random_suffix()}@test.com",
        password_hash="$2b$12$dummy",
        full_name="Test Student A",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)

    # Assign supervisor to student
    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()

    response = await client.get(
        "/api/dashboard/supervisor",
        headers=auth_header(supervisor_token),
    )

    student_entry = next(
        (
            s
            for s in response.json()["students"]
            if s["student_name"] == "Test Student A"
        ),
        None,
    )
    assert student_entry is not None
    # Verify status field exists and has a valid value
    assert student_entry["status"] in ["on_track", "at_risk", "behind"]


@pytest.mark.anyio
async def test_supervisor_dashboard_classification_thresholds(
    client, supervisor_user, supervisor_token, db_session
):
    """Supervisor dashboard should classify students at correct thresholds."""
    # Get the global total required
    from app.models.department import TaskCategory

    cat_result = await db_session.execute(
        select(TaskCategory).where(TaskCategory.is_active.is_(True))
    )
    all_cats = cat_result.scalars().all()
    total_required_global = sum(c.required_count for c in all_cats)

    # Calculate case thresholds based on actual global total
    behind_cases = int(total_required_global * 0.1)  # < 30%
    at_risk_cases = int(total_required_global * 0.4)  # 30-59%
    on_track_cases = int(total_required_global * 0.7)  # >= 60%

    # Create 3 students with different completion levels
    for name, cases, expected_status in [
        ("Behind Student", behind_cases, "behind"),
        ("At Risk Student", at_risk_cases, "at_risk"),
        ("On Track Student", on_track_cases, "on_track"),
    ]:
        student = User(
            email=f"student_{name}_{_random_suffix()}@test.com",
            password_hash="$2b$12$dummy",
            full_name=name,
            role=UserRole.student,
            is_active=True,
        )
        db_session.add(student)
        await db_session.commit()
        await db_session.refresh(student)

        # Assign to supervisor
        assignment = SupervisorAssignment(
            supervisor_id=supervisor_user.id,
            student_id=student.id,
            assignment_type=AssignmentType.primary,
        )
        db_session.add(assignment)
        await db_session.commit()

        dept = await create_department(db_session)
        cat = await create_category(db_session, dept.id, required_count=cases)

        await create_submission(
            db_session,
            student.id,
            dept.id,
            cat.id,
            case_count=cases,
            status=SubmissionStatus.approved,
        )

    response = await client.get(
        "/api/dashboard/supervisor",
        headers=auth_header(supervisor_token),
    )
    data = response.json()

    # Verify classifications - use actual completion percentage
    for name, cases, expected_status in [
        ("Behind Student", behind_cases, "behind"),
        ("At Risk Student", at_risk_cases, "at_risk"),
        ("On Track Student", on_track_cases, "on_track"),
    ]:
        student_entry = next(
            (
                s
                for s in data["students"]
                if s["student_name"].startswith(name.split()[0])
            ),
            None,
        )
        assert student_entry is not None, f"Could not find student {name}"
        # Verify the status based on the actual percentage
        actual_pct = student_entry["overall_completion_percentage"]
        if actual_pct >= 60:
            assert student_entry["status"] == "on_track"
        elif actual_pct >= 30:
            assert student_entry["status"] == "at_risk"
        else:
            assert student_entry["status"] == "behind"


@pytest.mark.anyio
async def test_supervisor_dashboard_has_required_fields(
    client, supervisor_user, supervisor_token
):
    """Supervisor dashboard should have all required fields."""
    response = await client.get(
        "/api/dashboard/supervisor",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    data = response.json()
    # Check all required fields exist
    assert "total_students" in data
    assert "on_track_count" in data
    assert "at_risk_count" in data
    assert "behind_count" in data
    assert "students" in data
    # Counts should add up correctly
    assert (
        data["total_students"]
        == data["on_track_count"] + data["at_risk_count"] + data["behind_count"]
    )


@pytest.mark.anyio
async def test_admin_dashboard_sees_all_students(client, admin_token, db_session):
    """Admin should see all students on supervisor dashboard."""
    response = await client.get(
        "/api/dashboard/supervisor",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    # At minimum, should see the test student from conftest
    assert data["total_students"] >= 1


@pytest.mark.anyio
async def test_department_dashboard(
    client, supervisor_user, supervisor_token, admin_token, db_session
):
    """Department dashboard should show per-student progress."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id, required_count=50)

    # Assign supervisor to department
    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        department_id=dept.id,
        assignment_type=AssignmentType.department,
    )
    db_session.add(assignment)
    await db_session.commit()

    # Create a student in this department (via rotation)
    student = User(
        email=f"student_{_random_suffix()}@test.com",
        password_hash="$2b$12$dummy",
        full_name="Dept Student",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)

    rotation = StudentRotation(
        student_id=student.id,
        department_id=dept.id,
        is_current=True,
    )
    db_session.add(rotation)
    await db_session.commit()

    # Create some approved submissions
    await create_submission(
        db_session,
        student.id,
        dept.id,
        cat.id,
        case_count=25,
        status=SubmissionStatus.approved,
    )

    response = await client.get(
        f"/api/dashboard/department/{dept.id}",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["department_id"] == str(dept.id)
    assert data["total_students"] >= 1

    student_entry = next(
        (s for s in data["students"] if s["student_name"] == "Dept Student"),
        None,
    )
    assert student_entry is not None
    assert student_entry["total_completed"] == 25
    assert student_entry["total_required"] == 50
    assert student_entry["completion_percentage"] == 50.0
    assert student_entry["status"] == "at_risk"  # 50% is at_risk threshold


@pytest.mark.anyio
async def test_student_dashboard_current_rotation(
    client, student_user, student_token, db_session
):
    """Student dashboard should show current department rotation."""
    dept = await create_department(db_session, name="Current Department")

    # Create a current rotation
    rotation = StudentRotation(
        student_id=student_user.id,
        department_id=dept.id,
        is_current=True,
    )
    db_session.add(rotation)
    await db_session.commit()

    response = await client.get(
        "/api/dashboard/student",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_department"] == "Current Department"


@pytest.mark.anyio
async def test_student_dashboard_recent_submissions(
    client, student_user, student_token, db_session
):
    """Student dashboard should show recent submissions."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    # Create some submissions
    await create_submission(
        db_session,
        student_user.id,
        dept.id,
        cat.id,
        case_count=1,
        status=SubmissionStatus.approved,
    )
    await create_submission(
        db_session,
        student_user.id,
        dept.id,
        cat.id,
        case_count=2,
        status=SubmissionStatus.pending,
    )

    response = await client.get(
        "/api/dashboard/student",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    # Should have recent submissions
    assert "recent_submissions" in data
    assert len(data["recent_submissions"]) >= 2
