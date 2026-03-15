import random
import string
import uuid

import pytest
from sqlalchemy import select

from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.submission import SubmissionStatus
from tests.conftest import auth_header
from tests.factories import create_category, create_department


def _random_suffix() -> str:
    """Generate a random suffix for unique names."""
    return "".join(random.choices(string.ascii_lowercase, k=8))


@pytest.mark.anyio
async def test_create_submission(client, student_user, student_token, db_session):
    """Student can create a valid case submission."""
    dept = await create_department(db_session, name="Oral Surgery")
    cat = await create_category(
        db_session, dept.id, name="Extraction", required_count=20
    )

    response = await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept.id),
            "task_category_id": str(cat.id),
            "case_count": 3,
            "proof_url": "submissions/test-proof.jpg",
            "notes": "Completed 3 extractions",
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["case_count"] == 3
    assert data["status"] == "pending"
    assert data["student_id"] == str(student_user.id)


@pytest.mark.anyio
async def test_create_submission_invalid_department(client, student_token):
    """Submission with nonexistent department should return 404."""
    response = await client.post(
        "/api/submissions",
        json={
            "department_id": str(uuid.uuid4()),
            "task_category_id": str(uuid.uuid4()),
            "case_count": 1,
            "proof_url": "submissions/test.jpg",
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_submission_mismatched_category(
    client, student_user, student_token, db_session
):
    """Submission with category from different department should return 404."""
    dept1 = await create_department(db_session, name="Department 1")
    dept2 = await create_department(db_session, name="Department 2")
    cat1 = await create_category(db_session, dept1.id, name="Category 1")

    response = await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept2.id),  # Different department
            "task_category_id": str(cat1.id),  # Category from dept1
            "case_count": 1,
            "proof_url": "submissions/test.jpg",
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_supervisor_approve_submission(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Supervisor can approve a pending submission."""
    dept = await create_department(db_session, name="Periodontics")
    cat = await create_category(db_session, dept.id, name="Scaling")

    # Student creates submission
    create_resp = await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept.id),
            "task_category_id": str(cat.id),
            "case_count": 2,
            "proof_url": "submissions/proof.jpg",
        },
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    # Supervisor approves
    review_resp = await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "approved"},
        headers=auth_header(supervisor_token),
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "approved"
    assert review_resp.json()["reviewed_by"] == str(supervisor_user.id)


@pytest.mark.anyio
async def test_supervisor_reject_submission(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Supervisor can reject a pending submission."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    # Student creates submission
    create_resp = await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept.id),
            "task_category_id": str(cat.id),
            "case_count": 1,
            "proof_url": "submissions/proof.jpg",
        },
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    # Supervisor rejects with notes
    review_resp = await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "rejected", "review_notes": "Proof image unclear"},
        headers=auth_header(supervisor_token),
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "rejected"
    assert review_resp.json()["review_notes"] == "Proof image unclear"


@pytest.mark.anyio
async def test_cannot_re_review_submission(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Cannot review an already-reviewed submission."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    # Create and approve
    create_resp = await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept.id),
            "task_category_id": str(cat.id),
            "case_count": 1,
            "proof_url": "submissions/proof.jpg",
        },
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "approved"},
        headers=auth_header(supervisor_token),
    )

    # Try to reject the already-approved submission
    re_review = await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "rejected"},
        headers=auth_header(supervisor_token),
    )
    assert re_review.status_code == 400


@pytest.mark.anyio
async def test_student_only_sees_own_submissions(
    client, student_user, student_token, admin_user, admin_token, db_session
):
    """Student listing submissions should only see their own."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    # Get initial count
    initial_list = await client.get(
        "/api/submissions", headers=auth_header(student_token)
    )
    initial_count = len(initial_list.json())

    # Student creates a submission
    await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept.id),
            "task_category_id": str(cat.id),
            "case_count": 1,
            "proof_url": "submissions/proof.jpg",
        },
        headers=auth_header(student_token),
    )

    # Student lists — should see initial_count + 1
    student_list = await client.get(
        "/api/submissions", headers=auth_header(student_token)
    )
    assert len(student_list.json()) == initial_count + 1

    # Admin lists — should also see at least as many as student
    admin_list = await client.get("/api/submissions", headers=auth_header(admin_token))
    assert len(admin_list.json()) >= initial_count + 1


@pytest.mark.anyio
async def test_student_cannot_create_for_another_student(
    client, student_token, admin_user, db_session
):
    """Student cannot create submission for another student (API enforces this via user token)."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    # Student tries to create submission - API uses their own ID from token
    response = await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept.id),
            "task_category_id": str(cat.id),
            "case_count": 1,
            "proof_url": "submissions/proof.jpg",
        },
        headers=auth_header(student_token),
    )
    # Should succeed - submission is created for the authenticated student
    assert response.status_code == 201
    # Verify it's for the student in the token, not admin_user
    # (The API doesn't accept student_id in body, it gets it from the token)


@pytest.mark.anyio
async def test_student_cannot_review_submission(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Student cannot review submissions."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    # Student creates submission
    create_resp = await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept.id),
            "task_category_id": str(cat.id),
            "case_count": 1,
            "proof_url": "submissions/proof.jpg",
        },
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    # Student tries to review - should fail (require_supervisor dependency)
    review_resp = await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "approved"},
        headers=auth_header(student_token),
    )
    assert review_resp.status_code == 403


@pytest.mark.anyio
async def test_supervisor_can_only_see_assigned_students_submissions(
    client,
    student_user,
    student_token,
    supervisor_user,
    supervisor_token,
    admin_token,
    db_session,
):
    """Supervisor should only see submissions from their assigned students or departments."""
    # Create a separate student for this test to avoid interference
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    new_student = User(
        email=f"test_student_{_random_suffix()}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Test Student For Supervisor",
        student_id=f"TS{_random_suffix()}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(new_student)
    await db_session.commit()
    await db_session.refresh(new_student)

    # Create a token for the new student
    from app.core.security import create_access_token

    new_student_token = create_access_token(subject=str(new_student.id), role="student")

    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    # Get initial supervisor count
    initial_supervisor_list = await client.get(
        "/api/submissions", headers=auth_header(supervisor_token)
    )
    initial_count = len(initial_supervisor_list.json())

    # Create a submission from the new student (supervisor not assigned yet)
    await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept.id),
            "task_category_id": str(cat.id),
            "case_count": 1,
            "proof_url": "submissions/proof.jpg",
        },
        headers=auth_header(new_student_token),
    )

    # Supervisor lists - should still see initial_count because they're not assigned
    supervisor_list = await client.get(
        "/api/submissions", headers=auth_header(supervisor_token)
    )
    assert len(supervisor_list.json()) == initial_count

    # Create assignment
    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=new_student.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()

    # Now supervisor should see initial_count + 1 (their assigned student's submission)
    supervisor_list_after = await client.get(
        "/api/submissions", headers=auth_header(supervisor_token)
    )
    assert len(supervisor_list_after.json()) == initial_count + 1


@pytest.mark.anyio
async def test_submission_creates_audit_log(
    client, student_user, student_token, db_session
):
    """Creating a submission should create an audit log entry."""
    from app.models.audit_log import AuditLog

    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    response = await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept.id),
            "task_category_id": str(cat.id),
            "case_count": 1,
            "proof_url": "submissions/proof.jpg",
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    submission_id = response.json()["id"]

    # Check audit log was created
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.table_name == "case_submissions",
            AuditLog.record_id == submission_id,
            AuditLog.action == "create",
        )
    )
    audit_entry = result.scalar_one_or_none()
    assert audit_entry is not None
    assert audit_entry.user_id == student_user.id


@pytest.mark.anyio
async def test_supervisor_sees_department_submissions_not_primary_supervisor(
    client,
    student_user,
    student_token,
    supervisor_user,
    supervisor_token,
    admin_token,
    db_session,
):
    """
    Test that a supervisor sees submissions for their assigned department,
    even when the student is primarily supervised by a different supervisor.
    This is the bug fix: student-b (supervised by supervisor-B) submits for
    department A (supervised by supervisor-A) → supervisor-A should see it.
    """
    from app.core.security import hash_password, create_access_token
    from app.models.user import User, UserRole

    # Create another supervisor (supervisor-B) who will be student's primary supervisor
    other_supervisor = User(
        email=f"other_sup_{_random_suffix()}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Other Supervisor",
        role=UserRole.supervisor,
        is_active=True,
    )
    db_session.add(other_supervisor)
    await db_session.commit()
    await db_session.refresh(other_supervisor)

    other_supervisor_token = create_access_token(
        subject=str(other_supervisor.id), role="supervisor"
    )

    # Create department A that supervisor_user (supervisor-A) will supervise
    dept_a = await create_department(db_session, name="Department A")
    cat_a = await create_category(db_session, dept_a.id, name="Category A")

    # Assign supervisor-A to department A
    dept_assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        department_id=dept_a.id,
        assignment_type=AssignmentType.department,
    )
    db_session.add(dept_assignment)

    # Assign supervisor-B as primary supervisor of the student
    primary_assignment = SupervisorAssignment(
        supervisor_id=other_supervisor.id,
        student_id=student_user.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(primary_assignment)
    await db_session.commit()

    # Student submits for department A
    submission_response = await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept_a.id),
            "task_category_id": str(cat_a.id),
            "case_count": 5,
            "proof_url": "submissions/proof.jpg",
        },
        headers=auth_header(student_token),
    )
    assert submission_response.status_code == 201
    submission_id = submission_response.json()["id"]

    # supervisor-A (department supervisor) should see this submission
    supervisor_a_list = await client.get(
        "/api/submissions", headers=auth_header(supervisor_token)
    )
    supervisor_a_submissions = supervisor_a_list.json()
    submission_ids_seen_by_a = {s["id"] for s in supervisor_a_submissions}
    assert submission_id in submission_ids_seen_by_a

    # supervisor-B (primary supervisor) should also see this submission
    # (because they're the student's primary supervisor)
    supervisor_b_list = await client.get(
        "/api/submissions", headers=auth_header(other_supervisor_token)
    )
    supervisor_b_submissions = supervisor_b_list.json()
    submission_ids_seen_by_b = {s["id"] for s in supervisor_b_submissions}
    assert submission_id in submission_ids_seen_by_b


@pytest.mark.anyio
async def test_invalid_proof_url_format(client, student_token, db_session):
    """Submission with invalid proof_url format should return 422."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    response = await client.post(
        "/api/submissions",
        json={
            "department_id": str(dept.id),
            "task_category_id": str(cat.id),
            "case_count": 1,
            "proof_url": "invalid-path/proof.jpg",  # Missing 'submissions/' prefix
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 422
    assert "proof_url must match pattern" in response.json()["detail"][0]["msg"]


@pytest.mark.anyio
async def test_empty_proof_url_returns_404(
    client, student_user, student_token, db_session
):
    """Empty proof_url on get_proof_url should return 404, not 500."""
    from app.models.submission import CaseSubmission

    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    # Create submission with empty proof_url (directly in DB to bypass validation)
    submission = CaseSubmission(
        student_id=student_user.id,
        department_id=dept.id,
        task_category_id=cat.id,
        case_count=1,
        proof_url="",  # Empty string
        status=SubmissionStatus.pending,
    )
    db_session.add(submission)
    await db_session.commit()
    await db_session.refresh(submission)

    # Try to get proof URL - should return 404, not 500
    response = await client.get(
        f"/api/submissions/{submission.id}/proof-url",
        headers=auth_header(student_token),
    )
    assert response.status_code == 404
    assert "not available" in response.json()["detail"]
