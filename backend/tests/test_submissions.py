import uuid

from sqlalchemy import select

from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.submission import CaseSubmission, SubmissionStatus
from tests.conftest import auth_header
from tests.factories import (
    _random_suffix,
    create_category,
    create_department,
    create_submission,
)


async def _setup_dept_with_supervisor(db_session, supervisor_user, dept_name=None):
    """Create a department, category, and assign supervisor to the department."""
    dept = await create_department(db_session, name=dept_name)
    cat = await create_category(db_session, dept.id)
    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        department_id=dept.id,
        assignment_type=AssignmentType.department,
    )
    db_session.add(assignment)
    await db_session.commit()
    return dept, cat


def _submission_payload(dept_id, cat_id, supervisor_id, **overrides):
    """Build a submission creation payload with required target_supervisor_id."""
    payload = {
        "department_id": str(dept_id),
        "target_supervisor_id": str(supervisor_id),
        "task_category_id": str(cat_id),
        "case_count": 3,
        "proof_key": "submissions/test-proof.jpg",
        "notes": "Completed 3 extractions",
    }
    payload.update(overrides)
    return payload


async def test_create_submission(
    client, student_user, student_token, supervisor_user, db_session
):
    """Student can create a valid case submission with target supervisor."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    response = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["case_count"] == 3
    assert data["status"] == "pending"
    assert data["student_id"] == str(student_user.id)
    assert data["target_supervisor_id"] == str(supervisor_user.id)
    assert data["target_supervisor"]["id"] == str(supervisor_user.id)


async def test_create_submission_invalid_supervisor(
    client, student_user, student_token, supervisor_user, db_session
):
    """Submission with supervisor not assigned to department should return 400."""
    dept = await create_department(db_session, name="No SV Dept")
    cat = await create_category(db_session, dept.id)

    response = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    assert response.status_code == 400
    assert "not assigned to this department" in response.json()["detail"]


async def test_create_submission_invalid_department(
    client, student_token, supervisor_user
):
    """Submission with nonexistent department should return 404."""
    response = await client.post(
        "/api/submissions",
        json={
            "department_id": str(uuid.uuid4()),
            "target_supervisor_id": str(supervisor_user.id),
            "task_category_id": str(uuid.uuid4()),
            "case_count": 1,
            "proof_key": "submissions/test.jpg",
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


async def test_create_submission_mismatched_category(
    client, student_user, student_token, supervisor_user, db_session
):
    """Submission with category from different department should return 404."""
    dept1 = await create_department(db_session, name="Department 1")
    dept2, cat2 = await _setup_dept_with_supervisor(
        db_session, supervisor_user, "Department 2"
    )
    cat1 = await create_category(db_session, dept1.id, name="Category 1")

    response = await client.post(
        "/api/submissions",
        json=_submission_payload(dept2.id, cat1.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


async def test_supervisor_approve_submission(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Target supervisor can approve a pending submission."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id, case_count=2),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    review_resp = await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "approved"},
        headers=auth_header(supervisor_token),
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "approved"
    assert review_resp.json()["reviewed_by"] == str(supervisor_user.id)


async def test_non_target_supervisor_cannot_review(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Supervisor who is NOT the target supervisor cannot review."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    # Set up dept with supervisor_user as target
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    # Create another supervisor also assigned to the same department
    other_sv = User(
        email=f"other_sv_{_random_suffix()}@test.com",
        password_hash=await hash_password("testpass123"),
        full_name="Other Department Supervisor",
        role=UserRole.supervisor,
        is_active=True,
    )
    db_session.add(other_sv)
    await db_session.commit()
    await db_session.refresh(other_sv)

    other_dept_assignment = SupervisorAssignment(
        supervisor_id=other_sv.id,
        department_id=dept.id,
        assignment_type=AssignmentType.department,
    )
    db_session.add(other_dept_assignment)
    await db_session.commit()

    from app.core.security import create_access_token

    other_sv_token = create_access_token(subject=str(other_sv.id), role="supervisor")

    review_resp = await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "approved"},
        headers=auth_header(other_sv_token),
    )
    assert review_resp.status_code == 403
    assert "assigned supervisor" in review_resp.json()["detail"]


async def test_supervisor_reject_submission(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Target supervisor can reject a pending submission."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    review_resp = await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "rejected", "review_notes": "Proof image unclear"},
        headers=auth_header(supervisor_token),
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "rejected"
    assert review_resp.json()["review_notes"] == "Proof image unclear"


async def test_cannot_re_review_submission(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Cannot review an already-reviewed submission."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "approved"},
        headers=auth_header(supervisor_token),
    )

    re_review = await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "rejected"},
        headers=auth_header(supervisor_token),
    )
    assert re_review.status_code == 400


async def test_student_only_sees_own_submissions(
    client,
    student_user,
    student_token,
    admin_user,
    admin_token,
    supervisor_user,
    db_session,
):
    """Student listing submissions should only see their own."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    initial_list = await client.get(
        "/api/submissions", headers=auth_header(student_token)
    )
    initial_count = len(initial_list.json()["items"])

    await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )

    student_list = await client.get(
        "/api/submissions", headers=auth_header(student_token)
    )
    assert len(student_list.json()["items"]) == initial_count + 1

    admin_list = await client.get("/api/submissions", headers=auth_header(admin_token))
    assert len(admin_list.json()["items"]) >= initial_count + 1


async def test_student_cannot_create_for_another_student(
    client, student_user, student_token, supervisor_user, db_session
):
    """Student cannot create submission for another student (API enforces this via user token)."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    response = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == str(student_user.id)


async def test_student_cannot_review_submission(
    client, student_user, student_token, supervisor_user, db_session
):
    """Student cannot review submissions."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    review_resp = await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "approved"},
        headers=auth_header(student_token),
    )
    assert review_resp.status_code == 403


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
    from app.core.security import hash_password, create_access_token
    from app.models.user import User, UserRole

    new_student = User(
        email=f"test_student_{_random_suffix()}@test.com",
        password_hash=await hash_password("testpass123"),
        full_name="Test Student For Supervisor",
        institutional_id=f"TS{_random_suffix()}",
        role=UserRole.student,
        is_active=True,
        email_verified=True,
    )
    db_session.add(new_student)
    await db_session.commit()
    await db_session.refresh(new_student)

    new_student_token = create_access_token(subject=str(new_student.id), role="student")

    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    initial_supervisor_list = await client.get(
        "/api/submissions", headers=auth_header(supervisor_token)
    )
    initial_count = len(initial_supervisor_list.json()["items"])

    # New student submits (supervisor not assigned to this student)
    await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(new_student_token),
    )

    # Supervisor sees it because they supervise the department
    supervisor_list = await client.get(
        "/api/submissions", headers=auth_header(supervisor_token)
    )
    assert len(supervisor_list.json()["items"]) == initial_count + 1


async def test_submission_creates_audit_log(
    client, student_user, student_token, supervisor_user, db_session
):
    """Creating a submission should create an audit log entry."""
    from app.models.audit_log import AuditLog

    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    response = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    submission_id = response.json()["id"]

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
    Supervisor-A sees submissions for their assigned department,
    even when the student is primarily supervised by supervisor-B.
    """
    from app.core.security import hash_password, create_access_token
    from app.models.user import User, UserRole

    other_supervisor = User(
        email=f"other_sup_{_random_suffix()}@test.com",
        password_hash=await hash_password("testpass123"),
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

    dept_a, cat_a = await _setup_dept_with_supervisor(
        db_session, supervisor_user, "Department A"
    )

    # Assign supervisor-B as primary supervisor of the student
    primary_assignment = SupervisorAssignment(
        supervisor_id=other_supervisor.id,
        student_id=student_user.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(primary_assignment)
    await db_session.commit()

    # Student submits for department A targeting supervisor-A
    submission_response = await client.post(
        "/api/submissions",
        json=_submission_payload(dept_a.id, cat_a.id, supervisor_user.id, case_count=5),
        headers=auth_header(student_token),
    )
    assert submission_response.status_code == 201
    submission_id = submission_response.json()["id"]

    # supervisor-A (department + target supervisor) should see this
    supervisor_a_list = await client.get(
        "/api/submissions", headers=auth_header(supervisor_token)
    )
    submission_ids_seen_by_a = {s["id"] for s in supervisor_a_list.json()["items"]}
    assert submission_id in submission_ids_seen_by_a

    # supervisor-B (primary/academic supervisor) should also see this
    supervisor_b_list = await client.get(
        "/api/submissions", headers=auth_header(other_supervisor_token)
    )
    submission_ids_seen_by_b = {s["id"] for s in supervisor_b_list.json()["items"]}
    assert submission_id in submission_ids_seen_by_b

    # supervisor-B should NOT be able to review (not the target)
    sv_b_review = await client.patch(
        f"/api/submissions/{submission_id}/review",
        json={"status": "approved"},
        headers=auth_header(other_supervisor_token),
    )
    assert sv_b_review.status_code == 403


async def test_invalid_proof_url_format(
    client, student_token, supervisor_user, db_session
):
    """Submission with invalid proof_url format should return 422."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    response = await client.post(
        "/api/submissions",
        json=_submission_payload(
            dept.id, cat.id, supervisor_user.id, proof_key="invalid-path/proof.jpg"
        ),
        headers=auth_header(student_token),
    )
    assert response.status_code == 422
    assert "proof_key must match pattern" in response.json()["detail"][0]["msg"]


async def test_empty_proof_url_returns_404(
    client, student_user, student_token, db_session
):
    """Empty proof_url on get_proof_url should return 404, not 500."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    submission = CaseSubmission(
        student_id=student_user.id,
        department_id=dept.id,
        task_category_id=cat.id,
        case_count=1,
        proof_key="",
        status=SubmissionStatus.pending,
    )
    db_session.add(submission)
    await db_session.commit()
    await db_session.refresh(submission)

    response = await client.get(
        f"/api/submissions/{submission.id}/proof-url",
        headers=auth_header(student_token),
    )
    assert response.status_code == 404
    assert "not available" in response.json()["detail"]


async def test_get_submission_by_id_student_own_only(
    client, student_user, student_token, supervisor_user, db_session
):
    """Student can only fetch their own submission by ID."""
    from app.core.security import hash_password, create_access_token
    from app.models.user import User, UserRole

    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    other_student = User(
        email=f"other_student_{_random_suffix()}@test.com",
        password_hash=await hash_password("testpass123"),
        full_name="Other Student",
        institutional_id=f"OS{_random_suffix()}",
        role=UserRole.student,
        is_active=True,
        email_verified=True,
    )
    db_session.add(other_student)
    await db_session.commit()
    await db_session.refresh(other_student)

    other_student_token = create_access_token(
        subject=str(other_student.id), role="student"
    )

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(other_student_token),
    )
    sub_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/submissions/{sub_id}",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_get_submission_by_id_supervisor_can_view_assigned(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Supervisor can view submission from their assigned department."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/submissions/{sub_id}",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200
    assert response.json()["id"] == sub_id
    assert response.json()["target_supervisor"]["id"] == str(supervisor_user.id)


async def test_get_submission_by_id_admin_can_view_all(
    client, student_user, student_token, supervisor_user, admin_token, db_session
):
    """Admin can view any submission by ID."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/submissions/{sub_id}",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["id"] == sub_id


async def test_get_submission_not_found_returns_404(client, student_token):
    """Fetching a non-existent submission ID should return 404."""
    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/submissions/{fake_id}",
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


async def test_get_proof_url_student_own_only(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Student can only get proof URL for their own submission."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/submissions/{sub_id}/proof-url",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 200


async def test_get_proof_url_empty_returns_404(
    client, student_user, student_token, db_session
):
    """Empty proof_url should return 404."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)

    submission = CaseSubmission(
        student_id=student_user.id,
        department_id=dept.id,
        task_category_id=cat.id,
        case_count=1,
        proof_key="",
        status=SubmissionStatus.pending,
    )
    db_session.add(submission)
    await db_session.commit()
    await db_session.refresh(submission)

    response = await client.get(
        f"/api/submissions/{submission.id}/proof-url",
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


async def test_get_upload_url_student_only(client, supervisor_token):
    """Only students can get upload URLs."""
    response = await client.post(
        "/api/submissions/upload-url",
        json={"filename": "proof.jpg", "content_type": "image/jpeg"},
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 403


async def test_get_upload_url_returns_presigned_url(client, student_token):
    """Upload URL endpoint returns a valid presigned URL."""
    response = await client.post(
        "/api/submissions/upload-url",
        json={"filename": "proof.jpg", "content_type": "image/jpeg"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert "upload_url" in data
    assert "object_key" in data
    assert isinstance(data["upload_url"], str)
    assert isinstance(data["object_key"], str)


async def test_get_upload_url_includes_unique_key(client, student_token):
    """Upload URL key includes a unique identifier."""
    response = await client.post(
        "/api/submissions/upload-url",
        json={"filename": "proof.jpg", "content_type": "image/jpeg"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["object_key"]) > 0


# ---------------------------------------------------------------------------
# Soft-delete and restore tests
# ---------------------------------------------------------------------------


async def test_student_can_delete_own_pending_submission(
    client, student_user, student_token, db_session
):
    """Student can soft-delete their own pending submission."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)
    sub = await create_submission(db_session, student_user.id, dept.id, cat.id)

    response = await client.delete(
        f"/api/submissions/{sub.id}",
        headers=auth_header(student_token),
    )
    assert response.status_code == 204

    get_resp = await client.get(
        f"/api/submissions/{sub.id}",
        headers=auth_header(student_token),
    )
    assert get_resp.status_code == 404


async def test_student_cannot_delete_approved_submission(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Student cannot delete an already-approved submission."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "approved"},
        headers=auth_header(supervisor_token),
    )

    response = await client.delete(
        f"/api/submissions/{sub_id}",
        headers=auth_header(student_token),
    )
    assert response.status_code == 400


async def test_student_cannot_delete_others_submission(
    client, student_user, student_token, supervisor_user, db_session
):
    """Student cannot delete another student's submission."""
    from app.core.security import hash_password, create_access_token
    from app.models.user import User, UserRole

    other = User(
        email=f"del_other_{_random_suffix()}@test.com",
        password_hash=await hash_password("testpass123"),
        full_name="Other Student",
        institutional_id=f"DELOTH{_random_suffix()}",
        role=UserRole.student,
        is_active=True,
        email_verified=True,
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    other_token = create_access_token(subject=str(other.id), role="student")

    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(other_token),
    )
    sub_id = create_resp.json()["id"]

    response = await client.delete(
        f"/api/submissions/{sub_id}",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_supervisor_can_delete_pending_submission(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Supervisor can delete any pending submission."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    response = await client.delete(
        f"/api/submissions/{sub_id}",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 204


async def test_admin_can_delete_any_pending_submission(
    client, student_user, student_token, supervisor_user, admin_token, db_session
):
    """Admin can delete any pending submission."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    response = await client.delete(
        f"/api/submissions/{sub_id}",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 204


async def test_deleted_submission_excluded_from_list(
    client, student_user, student_token, db_session
):
    """Soft-deleted submissions do not appear in the normal list."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)
    sub = await create_submission(db_session, student_user.id, dept.id, cat.id)

    list_before = await client.get(
        "/api/submissions", headers=auth_header(student_token)
    )
    ids_before = {s["id"] for s in list_before.json()["items"]}
    assert str(sub.id) in ids_before

    await client.delete(
        f"/api/submissions/{sub.id}", headers=auth_header(student_token)
    )

    list_after = await client.get(
        "/api/submissions", headers=auth_header(student_token)
    )
    ids_after = {s["id"] for s in list_after.json()["items"]}
    assert str(sub.id) not in ids_after


async def test_admin_can_list_deleted_submissions(
    client, student_user, student_token, admin_token, db_session
):
    """Admin can see soft-deleted submissions via /deleted endpoint."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)
    sub = await create_submission(db_session, student_user.id, dept.id, cat.id)

    await client.delete(
        f"/api/submissions/{sub.id}", headers=auth_header(student_token)
    )

    response = await client.get(
        "/api/submissions/deleted", headers=auth_header(admin_token)
    )
    assert response.status_code == 200
    ids = {s["id"] for s in response.json()["items"]}
    assert str(sub.id) in ids

    deleted_sub = next(s for s in response.json()["items"] if s["id"] == str(sub.id))
    assert deleted_sub["deleted_at"] is not None


async def test_non_admin_cannot_list_deleted_submissions(
    client, student_token, supervisor_token
):
    """Students and supervisors cannot access /deleted endpoint."""
    for token in (student_token, supervisor_token):
        response = await client.get(
            "/api/submissions/deleted", headers=auth_header(token)
        )
        assert response.status_code == 403


async def test_admin_can_restore_deleted_submission(
    client, student_user, student_token, admin_token, db_session
):
    """Admin can restore a soft-deleted submission; it reappears in the normal list."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)
    sub = await create_submission(db_session, student_user.id, dept.id, cat.id)

    await client.delete(
        f"/api/submissions/{sub.id}", headers=auth_header(student_token)
    )

    list_resp = await client.get("/api/submissions", headers=auth_header(admin_token))
    ids = {s["id"] for s in list_resp.json()["items"]}
    assert str(sub.id) not in ids

    restore_resp = await client.post(
        f"/api/submissions/{sub.id}/restore", headers=auth_header(admin_token)
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["deleted_at"] is None

    list_after = await client.get("/api/submissions", headers=auth_header(admin_token))
    ids_after = {s["id"] for s in list_after.json()["items"]}
    assert str(sub.id) in ids_after


async def test_non_admin_cannot_restore_submission(
    client, student_user, student_token, supervisor_token, db_session
):
    """Supervisor cannot restore a deleted submission."""
    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)
    sub = await create_submission(db_session, student_user.id, dept.id, cat.id)

    await client.delete(
        f"/api/submissions/{sub.id}", headers=auth_header(student_token)
    )

    response = await client.post(
        f"/api/submissions/{sub.id}/restore", headers=auth_header(supervisor_token)
    )
    assert response.status_code == 403


async def test_delete_creates_audit_log(
    client, student_user, student_token, db_session
):
    """Soft-deleting a submission creates an audit log entry with action='delete'."""
    from app.models.audit_log import AuditLog

    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)
    sub = await create_submission(db_session, student_user.id, dept.id, cat.id)

    await client.delete(
        f"/api/submissions/{sub.id}", headers=auth_header(student_token)
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.table_name == "case_submissions",
            AuditLog.record_id == sub.id,
            AuditLog.action == "delete",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.user_id == student_user.id


async def test_restore_creates_audit_log(
    client, student_user, student_token, admin_user, admin_token, db_session
):
    """Restoring a submission creates an audit log entry with action='update'."""
    from app.models.audit_log import AuditLog

    dept = await create_department(db_session)
    cat = await create_category(db_session, dept.id)
    sub = await create_submission(db_session, student_user.id, dept.id, cat.id)

    await client.delete(
        f"/api/submissions/{sub.id}", headers=auth_header(student_token)
    )
    await client.post(
        f"/api/submissions/{sub.id}/restore", headers=auth_header(admin_token)
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.table_name == "case_submissions",
            AuditLog.record_id == sub.id,
            AuditLog.action == "update",
        )
    )
    entries = result.scalars().all()
    restore_entries = [e for e in entries if e.user_id == admin_user.id]
    assert len(restore_entries) >= 1


# ---------------------------------------------------------------------------
# Student edit pending submission tests
# ---------------------------------------------------------------------------


async def test_student_can_edit_pending_submission(
    client, student_user, student_token, supervisor_user, db_session
):
    """Student can edit case_count, proof_key, and notes on a pending submission."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/submissions/{sub_id}",
        json={
            "case_count": 5,
            "proof_key": "submissions/updated-proof.jpg",
            "notes": "Updated notes",
        },
        headers=auth_header(student_token),
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["case_count"] == 5
    assert data["proof_key"] == "submissions/updated-proof.jpg"
    assert data["notes"] == "Updated notes"
    # Immutable fields unchanged
    assert data["department_id"] == str(dept.id)
    assert data["task_category_id"] == str(cat.id)
    assert data["target_supervisor_id"] == str(supervisor_user.id)


async def test_student_cannot_edit_reviewed_submission(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """Student cannot edit an already-reviewed submission."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )
    sub_id = create_resp.json()["id"]

    await client.patch(
        f"/api/submissions/{sub_id}/review",
        json={"status": "approved"},
        headers=auth_header(supervisor_token),
    )

    update_resp = await client.put(
        f"/api/submissions/{sub_id}",
        json={"case_count": 10},
        headers=auth_header(student_token),
    )
    assert update_resp.status_code == 400


async def test_student_cannot_edit_others_submission(
    client, student_user, student_token, supervisor_user, db_session
):
    """Student cannot edit another student's submission."""
    from app.core.security import hash_password, create_access_token
    from app.models.user import User, UserRole

    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    other = User(
        email=f"edit_other_{_random_suffix()}@test.com",
        password_hash=await hash_password("testpass123"),
        full_name="Other Student",
        institutional_id=f"EDITOTH{_random_suffix()}",
        role=UserRole.student,
        is_active=True,
        email_verified=True,
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    other_token = create_access_token(subject=str(other.id), role="student")

    create_resp = await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(other_token),
    )
    sub_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/submissions/{sub_id}",
        json={"case_count": 10},
        headers=auth_header(student_token),
    )
    assert update_resp.status_code == 403


# ---------------------------------------------------------------------------
# can_review flag tests
# ---------------------------------------------------------------------------


async def test_can_review_true_for_target_supervisor(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """can_review is true for the target supervisor."""
    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )

    list_resp = await client.get(
        "/api/submissions", headers=auth_header(supervisor_token)
    )
    items = list_resp.json()["items"]
    sub = next(s for s in items if s["target_supervisor_id"] == str(supervisor_user.id))
    assert sub["can_review"] is True


async def test_can_review_false_for_academic_supervisor(
    client, student_user, student_token, supervisor_user, supervisor_token, db_session
):
    """can_review is false for academic (primary) supervisors who are not the target."""
    from app.core.security import hash_password, create_access_token
    from app.models.user import User, UserRole

    academic_sv = User(
        email=f"academic_sv_{_random_suffix()}@test.com",
        password_hash=await hash_password("testpass123"),
        full_name="Academic Supervisor",
        role=UserRole.supervisor,
        is_active=True,
    )
    db_session.add(academic_sv)
    await db_session.commit()
    await db_session.refresh(academic_sv)
    academic_sv_token = create_access_token(
        subject=str(academic_sv.id), role="supervisor"
    )

    dept, cat = await _setup_dept_with_supervisor(db_session, supervisor_user)

    # Assign academic supervisor to student
    primary = SupervisorAssignment(
        supervisor_id=academic_sv.id,
        student_id=student_user.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(primary)
    await db_session.commit()

    await client.post(
        "/api/submissions",
        json=_submission_payload(dept.id, cat.id, supervisor_user.id),
        headers=auth_header(student_token),
    )

    list_resp = await client.get(
        "/api/submissions", headers=auth_header(academic_sv_token)
    )
    items = list_resp.json()["items"]
    assert len(items) > 0
    for item in items:
        assert item["can_review"] is False
