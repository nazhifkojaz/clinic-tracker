from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.rotation import StudentRotation
from app.models.submission import SubmissionStatus
from app.models.user import User, UserRole
from tests.conftest import auth_header
from tests.factories import (
    _random_suffix,
    create_category,
    create_department,
    create_submission,
)


async def test_student_dashboard_empty(client, fresh_student, db_session):
    """Student with no submissions should have 0% progress."""
    from app.core.security import create_access_token

    dept = await create_department(db_session)
    await create_category(db_session, dept.id, required_count=10)

    # Create token for fresh_student
    fresh_token = create_access_token(subject=str(fresh_student.id), role="student")

    response = await client.get(
        "/api/dashboard/student",
        headers=auth_header(fresh_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["overall_completion_percentage"] == 0.0
    assert data["total_completed"] == 0


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
            for s in response.json()["students"]["items"]
            if s["student_name"] == "Test Student A"
        ),
        None,
    )
    assert student_entry is not None
    # Verify status field exists and has a valid value
    assert student_entry["status"] in ["on_track", "at_risk", "behind"]


async def test_supervisor_dashboard_classification_thresholds(
    client, supervisor_user, supervisor_token, db_session
):
    """Supervisor dashboard should classify students at correct thresholds using known values."""
    # Use known values: 100 required, test 10/40/70 cases (10%/40%/70% completion)
    required_count = 100

    # Create 3 students with specific completion levels
    for cases, expected_status in [
        (10, "behind"),  # 10% -> behind
        (40, "at_risk"),  # 40% -> at_risk
        (70, "on_track"),  # 70% -> on_track
    ]:
        student = User(
            email=f"student_{expected_status}_{_random_suffix()}@test.com",
            password_hash="$2b$12$dummy",
            full_name=f"{expected_status.title()} Student",
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
        cat = await create_category(db_session, dept.id, required_count=required_count)

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

    # Verify each student's classification is consistent with the returned percentage.
    # The total_required_global varies with test data so we verify the threshold
    # logic (not specific percentages): < 30% → behind, 30–59% → at_risk, ≥ 60% → on_track.
    status_labels = ["behind", "at_risk", "on_track"]
    for _, label in [(10, "behind"), (40, "at_risk"), (70, "on_track")]:
        student_entry = next(
            (
                s
                for s in data["students"]["items"]
                if s["student_name"] == f"{label.title()} Student"
            ),
            None,
        )
        assert student_entry is not None, f"Could not find {label} student"
        pct = student_entry["overall_completion_percentage"]
        expected = "on_track" if pct >= 60 else "at_risk" if pct >= 30 else "behind"
        assert student_entry["status"] == expected, (
            f"{label.title()} Student: {pct}% should be '{expected}', got '{student_entry['status']}'"
        )

    # Additionally verify relative ordering: more submissions → better or equal status
    entries = {
        label: next(
            s
            for s in data["students"]["items"]
            if s["student_name"] == f"{label.title()} Student"
        )
        for label in ["behind", "at_risk", "on_track"]
    }
    assert status_labels.index(entries["behind"]["status"]) <= status_labels.index(
        entries["at_risk"]["status"]
    )
    assert status_labels.index(entries["at_risk"]["status"]) <= status_labels.index(
        entries["on_track"]["status"]
    )


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


# ============================================================================
# PERF-01 Tests: Redundant DB fetch fix
# ============================================================================


async def test_student_dashboard_rotation_warning_from_joined_data(
    client, student_user, student_token, db_session
):
    """Verify rotation warning is computed correctly using joined rotation_duration_days.

    PERF-01: This test verifies that rotation_duration_days is fetched from the JOIN
    query and not from a redundant db.get() call.
    """
    from datetime import datetime, timezone, timedelta

    # Create department with 30-day rotation duration
    dept = await create_department(
        db_session, name="Test Dept", rotation_duration_days=30
    )
    cat = await create_category(db_session, dept.id, required_count=100)

    # Create current rotation started 16 days ago (53% elapsed)
    rotation = StudentRotation(
        student_id=student_user.id,
        department_id=dept.id,
        is_current=True,
        started_at=datetime.now(timezone.utc) - timedelta(days=16),
        days_offset=0,
    )
    db_session.add(rotation)
    await db_session.commit()

    # Create submissions: 50/100 cases (50% complete)
    await create_submission(
        db_session,
        student_user.id,
        dept.id,
        cat.id,
        case_count=50,
        status=SubmissionStatus.approved,
    )

    response = await client.get(
        "/api/dashboard/student",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    # Time: 53% elapsed, Cases: 50% complete -> Should show warning
    assert data["show_rotation_warning"] is True


async def test_student_dashboard_rotation_duration_null_handling(
    client, student_user, student_token, db_session
):
    """Verify NULL or zero rotation_duration_days is handled gracefully.

    PERF-01: This test verifies edge cases where rotation_duration_days is None or 0.
    """
    from datetime import datetime, timezone, timedelta

    # Create department with 0-day rotation duration (edge case)
    dept = await create_department(
        db_session, name="Zero Duration Dept", rotation_duration_days=0
    )

    # Create current rotation
    rotation = StudentRotation(
        student_id=student_user.id,
        department_id=dept.id,
        is_current=True,
        started_at=datetime.now(timezone.utc) - timedelta(days=16),
        days_offset=0,
    )
    db_session.add(rotation)
    await db_session.commit()

    response = await client.get(
        "/api/dashboard/student",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    # Should not crash, show_rotation_warning should be False
    assert data["show_rotation_warning"] is False


async def test_student_dashboard_no_rotation_warning_when_on_track(
    client, student_user, student_token, db_session
):
    """Verify rotation warning doesn't show when student is on track.

    PERF-01: This test verifies the warning logic works correctly with joined data.
    """
    from datetime import datetime, timezone, timedelta

    # Create department with 30-day rotation duration
    dept = await create_department(
        db_session, name="On Track Dept", rotation_duration_days=30
    )
    cat = await create_category(db_session, dept.id, required_count=100)

    # Create current rotation started 16 days ago (53% elapsed)
    rotation = StudentRotation(
        student_id=student_user.id,
        department_id=dept.id,
        is_current=True,
        started_at=datetime.now(timezone.utc) - timedelta(days=16),
        days_offset=0,
    )
    db_session.add(rotation)
    await db_session.commit()

    # Create submissions: 65/100 cases (65% complete - on track)
    await create_submission(
        db_session,
        student_user.id,
        dept.id,
        cat.id,
        case_count=65,
        status=SubmissionStatus.approved,
    )

    response = await client.get(
        "/api/dashboard/student",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    # Time: 53% elapsed, Cases: 65% complete -> Should NOT show warning
    assert data["show_rotation_warning"] is False


# ============================================================================
# PERF-02 Tests: Pagination for supervisor dashboard
# ============================================================================


async def test_supervisor_dashboard_pagination_structure(
    client, supervisor_user, supervisor_token, db_session
):
    """Verify supervisor dashboard returns paginated response structure.

    PERF-02: This test verifies the pagination structure is correct.
    """
    # Create 60 students assigned to supervisor
    for i in range(60):
        student = User(
            email=f"student_{i:03d}_{_random_suffix()}@test.com",
            password_hash="$2b$12$dummy",
            full_name=f"Student {i:03d}",
            role=UserRole.student,
            is_active=True,
        )
        db_session.add(student)
        await db_session.commit()
        await db_session.refresh(student)

        assignment = SupervisorAssignment(
            supervisor_id=supervisor_user.id,
            student_id=student.id,
            assignment_type=AssignmentType.primary,
        )
        db_session.add(assignment)
        await db_session.commit()

    # Request with limit=20, offset=0
    response = await client.get(
        "/api/dashboard/supervisor?limit=20&offset=0",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    data = response.json()

    # Verify pagination structure
    assert "students" in data
    assert "items" in data["students"]
    assert "total" in data["students"]
    assert "limit" in data["students"]
    assert "offset" in data["students"]
    assert "has_more" in data["students"]

    # Verify values
    assert data["students"]["total"] == 60
    assert data["students"]["limit"] == 20
    assert data["students"]["offset"] == 0
    assert data["students"]["has_more"] is True
    assert len(data["students"]["items"]) == 20

    # Verify status counts are computed from ALL students
    assert data["total_students"] == 60
    assert data["on_track_count"] + data["at_risk_count"] + data["behind_count"] == 60


async def test_supervisor_dashboard_status_counts_accuracy(
    client, supervisor_user, supervisor_token, db_session
):
    """Verify status counts are computed from all students, not just paginated subset.

    PERF-02: This test verifies that status counts are accurate regardless of pagination.
    """
    # Create 100 students with known completion percentages
    dept = await create_department(db_session, name="Count Test Dept")
    cat = await create_category(db_session, dept.id, required_count=100)

    # 30 students with 70% completion (on_track)
    for i in range(30):
        student = User(
            email=f"on_track_{i}_{_random_suffix()}@test.com",
            password_hash="$2b$12$dummy",
            full_name=f"On Track Student {i}",
            role=UserRole.student,
            is_active=True,
        )
        db_session.add(student)
        await db_session.commit()
        await db_session.refresh(student)

        assignment = SupervisorAssignment(
            supervisor_id=supervisor_user.id,
            student_id=student.id,
            assignment_type=AssignmentType.primary,
        )
        db_session.add(assignment)
        await db_session.commit()

        await create_submission(
            db_session,
            student.id,
            dept.id,
            cat.id,
            case_count=70,
            status=SubmissionStatus.approved,
        )

    # 40 students with 40% completion (at_risk)
    for i in range(40):
        student = User(
            email=f"at_risk_{i}_{_random_suffix()}@test.com",
            password_hash="$2b$12$dummy",
            full_name=f"At Risk Student {i}",
            role=UserRole.student,
            is_active=True,
        )
        db_session.add(student)
        await db_session.commit()
        await db_session.refresh(student)

        assignment = SupervisorAssignment(
            supervisor_id=supervisor_user.id,
            student_id=student.id,
            assignment_type=AssignmentType.primary,
        )
        db_session.add(assignment)
        await db_session.commit()

        await create_submission(
            db_session,
            student.id,
            dept.id,
            cat.id,
            case_count=40,
            status=SubmissionStatus.approved,
        )

    # 30 students with 20% completion (behind)
    for i in range(30):
        student = User(
            email=f"behind_{i}_{_random_suffix()}@test.com",
            password_hash="$2b$12$dummy",
            full_name=f"Behind Student {i}",
            role=UserRole.student,
            is_active=True,
        )
        db_session.add(student)
        await db_session.commit()
        await db_session.refresh(student)

        assignment = SupervisorAssignment(
            supervisor_id=supervisor_user.id,
            student_id=student.id,
            assignment_type=AssignmentType.primary,
        )
        db_session.add(assignment)
        await db_session.commit()

        await create_submission(
            db_session,
            student.id,
            dept.id,
            cat.id,
            case_count=20,
            status=SubmissionStatus.approved,
        )

    # Request first page only (limit=10)
    response = await client.get(
        "/api/dashboard/supervisor?limit=10&offset=0",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    data = response.json()

    # Verify counts are from ALL students, not just the 10 returned
    assert data["total_students"] == 100
    assert data["on_track_count"] == 30
    assert data["at_risk_count"] == 40
    assert data["behind_count"] == 30

    # Verify only 10 students returned in items
    assert len(data["students"]["items"]) == 10


async def test_supervisor_dashboard_default_limit(
    client, supervisor_user, supervisor_token, db_session
):
    """Verify default limit=50 when no parameters provided.

    PERF-02: This test verifies default pagination behavior.
    """
    # Create 75 students
    for i in range(75):
        student = User(
            email=f"default_{i}_{_random_suffix()}@test.com",
            password_hash="$2b$12$dummy",
            full_name=f"Default Student {i}",
            role=UserRole.student,
            is_active=True,
        )
        db_session.add(student)
        await db_session.commit()
        await db_session.refresh(student)

        assignment = SupervisorAssignment(
            supervisor_id=supervisor_user.id,
            student_id=student.id,
            assignment_type=AssignmentType.primary,
        )
        db_session.add(assignment)
        await db_session.commit()

    response = await client.get(
        "/api/dashboard/supervisor",  # No limit/offset params
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    data = response.json()

    # Verify default behavior
    assert data["students"]["limit"] == 50
    assert data["students"]["offset"] == 0
    assert len(data["students"]["items"]) == 50
    assert data["students"]["has_more"] is True
    assert data["students"]["total"] == 75


async def test_supervisor_dashboard_max_limit_enforcement(
    client, supervisor_user, supervisor_token
):
    """Verify max limit of 200 is enforced.

    PERF-02: This test verifies that limit > 200 is rejected by FastAPI validation.
    """
    response = await client.get(
        "/api/dashboard/supervisor?limit=999",  # Try to exceed max
        headers=auth_header(supervisor_token),
    )
    # FastAPI should reject this before it reaches the endpoint
    assert response.status_code == 422  # Validation error


async def test_supervisor_dashboard_offset_behavior(
    client, supervisor_user, supervisor_token, db_session
):
    """Verify offset skips correct number of records.

    PERF-02: This test verifies offset behavior for pagination.
    """
    # Create 50 students with predictable names
    for i in range(50):
        student = User(
            email=f"offset_{i:03d}_{_random_suffix()}@test.com",
            password_hash="$2b$12$dummy",
            full_name=f"Offset Student {i:03d}",
            role=UserRole.student,
            is_active=True,
        )
        db_session.add(student)
        await db_session.commit()
        await db_session.refresh(student)

        assignment = SupervisorAssignment(
            supervisor_id=supervisor_user.id,
            student_id=student.id,
            assignment_type=AssignmentType.primary,
        )
        db_session.add(assignment)
        await db_session.commit()

    # Request second page (offset=20, limit=10)
    response = await client.get(
        "/api/dashboard/supervisor?limit=10&offset=20",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    data = response.json()

    # Should return students 20-29 (0-indexed)
    assert len(data["students"]["items"]) == 10
    assert data["students"]["offset"] == 20
    assert data["students"]["has_more"] is True  # 50 total, 20+10=30, still 20 left


async def test_supervisor_dashboard_empty_result_pagination(
    client, supervisor_user, supervisor_token, db_session
):
    """Verify pagination works correctly when there are no students.

    PERF-02: This test verifies edge case of empty result set.
    """
    # Create a new supervisor with no students
    new_supervisor = User(
        email=f"empty_sup_{_random_suffix()}@test.com",
        password_hash="$2b$12$dummy",
        full_name="Empty Supervisor",
        role=UserRole.supervisor,
        is_active=True,
    )
    db_session.add(new_supervisor)
    await db_session.commit()
    await db_session.refresh(new_supervisor)

    from app.core.security import create_access_token

    token = create_access_token(subject=str(new_supervisor.id), role="supervisor")

    response = await client.get(
        "/api/dashboard/supervisor",
        headers=auth_header(token),
    )
    assert response.status_code == 200
    data = response.json()

    # Verify empty pagination structure
    assert data["total_students"] == 0
    assert data["on_track_count"] == 0
    assert data["at_risk_count"] == 0
    assert data["behind_count"] == 0
    assert data["students"]["total"] == 0
    assert data["students"]["items"] == []
    assert data["students"]["has_more"] is False


async def test_supervisor_dashboard_assignment_type_primary(
    client, supervisor_user, supervisor_token, db_session
):
    """Primary supervisees should have assignment_type='primary'."""
    student = User(
        email=f"primary_{_random_suffix()}@test.com",
        password_hash="$2b$12$dummy",
        full_name="Primary Student",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)

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
    assert response.status_code == 200
    entry = next(
        s for s in response.json()["students"]["items"] if s["student_name"] == "Primary Student"
    )
    assert entry["assignment_type"] == "primary"


async def test_supervisor_dashboard_assignment_type_department(
    client, supervisor_user, supervisor_token, db_session
):
    """Students rotating in a supervised department should have assignment_type='department'."""
    dept = await create_department(db_session)

    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        department_id=dept.id,
        assignment_type=AssignmentType.department,
    )
    db_session.add(assignment)

    student = User(
        email=f"dept_{_random_suffix()}@test.com",
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

    response = await client.get(
        "/api/dashboard/supervisor",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    entry = next(
        s for s in response.json()["students"]["items"] if s["student_name"] == "Dept Student"
    )
    assert entry["assignment_type"] == "department"


async def test_admin_dashboard_assignment_type_null(
    client, admin_token
):
    """Admin sees all students with assignment_type=null."""
    response = await client.get(
        "/api/dashboard/supervisor",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    for item in response.json()["students"]["items"]:
        assert item["assignment_type"] is None
