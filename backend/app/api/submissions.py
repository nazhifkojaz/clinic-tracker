from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    require_admin,
    require_student,
    require_supervisor,
)
from app.core.database import get_db
from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.audit_log import AuditLog
from app.models.department import Department, TaskCategory
from app.models.submission import CaseSubmission, SubmissionStatus
from app.models.user import User, UserRole, display_name
from app.schemas.pagination import PaginatedResponse
from app.schemas.submission import (
    DeletedSubmissionListResponse,
    ReviewerInfo,
    StudentInfo,
    SubmissionCreate,
    SubmissionListResponse,
    SubmissionResponse,
    SubmissionReview,
    SubmissionUpdate,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.utils.audit import record_audit
from app.utils.storage import generate_read_url, generate_upload_url
from app.utils.submission_notifications import (
    notify_submission_created,
    notify_submission_reviewed,
)

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


async def _get_academic_supervisor(db: AsyncSession, student_id: UUID) -> User | None:
    """Return the primary (academic) supervisor User for a student, or None."""
    assignment_result = await db.execute(
        select(SupervisorAssignment).where(
            SupervisorAssignment.student_id == student_id,
            SupervisorAssignment.assignment_type == AssignmentType.primary,
        )
    )
    assignment = assignment_result.scalar_one_or_none()
    if not assignment:
        return None
    sv_result = await db.execute(
        select(User).where(User.id == assignment.supervisor_id)
    )
    return sv_result.scalar_one_or_none()


@router.post("/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    body: UploadUrlRequest,
    _user: User = Depends(require_student),
):
    """Get a presigned URL for uploading proof image to R2. Student only."""
    upload_url, object_key = generate_upload_url(
        filename=body.filename,
        content_type=body.content_type,
    )
    return UploadUrlResponse(upload_url=upload_url, object_key=object_key)


async def _get_submission_or_403(
    submission_id: UUID,
    user: User,
    db: AsyncSession,
) -> CaseSubmission:
    """Fetch submission (non-deleted) and verify access.

    Students: own submissions only.
    Department supervisors: submissions in their assigned departments.
    Academic supervisors: submissions from their primary-assigned students.
    Admins: all submissions.
    """
    result = await db.execute(
        select(CaseSubmission).where(
            CaseSubmission.id == submission_id,
            CaseSubmission.deleted_at.is_(None),
        )
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if user.role == UserRole.student:
        if submission.student_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif user.role == UserRole.supervisor:
        is_primary_sv = (
            await db.execute(
                select(SupervisorAssignment.id).where(
                    SupervisorAssignment.student_id == submission.student_id,
                    SupervisorAssignment.supervisor_id == user.id,
                    SupervisorAssignment.assignment_type == AssignmentType.primary,
                )
            )
        ).scalar_one_or_none()
        is_dept_sv = (
            await db.execute(
                select(SupervisorAssignment.id).where(
                    SupervisorAssignment.department_id == submission.department_id,
                    SupervisorAssignment.supervisor_id == user.id,
                    SupervisorAssignment.assignment_type == AssignmentType.department,
                )
            )
        ).scalar_one_or_none()
        if not is_primary_sv and not is_dept_sv:
            raise HTTPException(status_code=403, detail="Access denied")

    return submission


async def _get_target_sv_info(
    submission: CaseSubmission, db: AsyncSession
) -> ReviewerInfo | None:
    """Fetch target supervisor info for a submission."""
    if not submission.target_supervisor_id:
        return None
    sv_result = await db.execute(
        select(User).where(User.id == submission.target_supervisor_id)
    )
    sv_user = sv_result.scalar_one_or_none()
    if not sv_user:
        return None
    return ReviewerInfo(id=sv_user.id, full_name=display_name(sv_user))


def _build_submission_response(
    submission: CaseSubmission, target_sv: ReviewerInfo | None = None
) -> SubmissionResponse:
    """Build SubmissionResponse from scalar fields only (avoids lazy relationship access)."""
    return SubmissionResponse(
        id=submission.id,
        student_id=submission.student_id,
        department_id=submission.department_id,
        task_category_id=submission.task_category_id,
        case_count=submission.case_count,
        proof_key=submission.proof_key,
        notes=submission.notes,
        status=submission.status,
        target_supervisor_id=submission.target_supervisor_id,
        target_supervisor=target_sv,
        reviewed_by=submission.reviewed_by,
        review_notes=submission.review_notes,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
        deleted_at=submission.deleted_at,
    )


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    body: SubmissionCreate,
    user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """Create a case submission. Student only."""
    # Verify department exists and is active
    dept_result = await db.execute(
        select(Department).where(
            Department.id == body.department_id,
            Department.is_active.is_(True),
        )
    )
    if not dept_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Department not found or inactive")

    # Verify task category exists, is active, and belongs to the department
    cat_result = await db.execute(
        select(TaskCategory).where(
            TaskCategory.id == body.task_category_id,
            TaskCategory.department_id == body.department_id,
            TaskCategory.is_active.is_(True),
        )
    )
    if not cat_result.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail="Task category not found, inactive, or does not belong to this department",
        )

    # Verify target supervisor is assigned to this department
    sv_result = await db.execute(
        select(SupervisorAssignment).where(
            SupervisorAssignment.supervisor_id == body.target_supervisor_id,
            SupervisorAssignment.department_id == body.department_id,
            SupervisorAssignment.assignment_type == AssignmentType.department,
        )
    )
    if not sv_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Selected supervisor is not assigned to this department",
        )

    submission = CaseSubmission(
        student_id=user.id,
        **body.model_dump(),
    )
    db.add(submission)
    await db.flush()  # Get server-generated UUID before audit
    await record_audit(
        db,
        user_id=user.id,
        action="create",
        table_name="case_submissions",
        record_id=submission.id,
        new_values={
            "student_id": str(submission.student_id),
            "department_id": str(submission.department_id),
            "task_category_id": str(submission.task_category_id),
            "case_count": submission.case_count,
            "target_supervisor_id": str(submission.target_supervisor_id),
        },
    )

    # Notifications: fetch users needed, then queue records + emails before commit
    sv_user_result = await db.execute(
        select(User).where(User.id == submission.target_supervisor_id)
    )
    target_sv_user = sv_user_result.scalar_one()
    academic_sv_user = await _get_academic_supervisor(db, user.id)
    await notify_submission_created(
        db, submission, user, target_sv_user, academic_sv_user
    )

    await db.commit()
    await db.refresh(submission)

    return _build_submission_response(
        submission, await _get_target_sv_info(submission, db)
    )


@router.get("", response_model=PaginatedResponse[SubmissionListResponse])
async def list_submissions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    department_id: UUID | None = Query(None),
    status_filter: SubmissionStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
):
    """List submissions with pagination. Role-based visibility with can_review flag."""
    query = (
        select(CaseSubmission, User)
        .join(User, CaseSubmission.student_id == User.id)
        .where(CaseSubmission.deleted_at.is_(None))
    )

    # Role-based filtering
    if user.role == UserRole.student:
        query = query.where(CaseSubmission.student_id == user.id)
    elif user.role == UserRole.supervisor:
        primary_students = select(SupervisorAssignment.student_id).where(
            SupervisorAssignment.supervisor_id == user.id,
            SupervisorAssignment.assignment_type == AssignmentType.primary,
        )
        supervised_depts = select(SupervisorAssignment.department_id).where(
            SupervisorAssignment.supervisor_id == user.id,
            SupervisorAssignment.assignment_type == AssignmentType.department,
        )
        query = query.where(
            CaseSubmission.student_id.in_(primary_students)
            | CaseSubmission.department_id.in_(supervised_depts)
        )
    # Admins see all submissions (no filter)

    if department_id:
        query = query.where(CaseSubmission.department_id == department_id)
    if status_filter:
        query = query.where(CaseSubmission.status == status_filter)

    count_subquery = query.subquery()
    count_query = select(func.count()).select_from(count_subquery)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(CaseSubmission.created_at.desc())
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)

    reviewer_ids: set[UUID] = set()
    target_sv_ids: set[UUID] = set()
    submissions_data = []
    for row in result.all():
        submission, student_user = row
        submissions_data.append((submission, student_user))
        if submission.reviewed_by:
            reviewer_ids.add(submission.reviewed_by)
        if submission.target_supervisor_id:
            target_sv_ids.add(submission.target_supervisor_id)

    # Batch-load all referenced users (reviewers + target supervisors)
    user_ids = reviewer_ids | target_sv_ids
    users_map: dict[UUID, User] = {}
    if user_ids:
        users_result = await db.execute(select(User).where(User.id.in_(list(user_ids))))
        users_map = {u.id: u for u in users_result.scalars().all()}

    # Pre-compute supervisor's accessible data for can_review
    is_admin = user.role == UserRole.admin

    submissions = []
    for submission, student_user in submissions_data:
        student_info = StudentInfo(
            id=student_user.id,
            full_name=display_name(student_user),
            student_id=student_user.institutional_id,
            email=student_user.email,
        )

        reviewer_info = None
        if submission.reviewed_by and submission.reviewed_by in users_map:
            reviewer_user = users_map[submission.reviewed_by]
            reviewer_info = ReviewerInfo(
                id=reviewer_user.id,
                full_name=display_name(reviewer_user),
            )

        target_sv_info = None
        if (
            submission.target_supervisor_id
            and submission.target_supervisor_id in users_map
        ):
            target_sv_user = users_map[submission.target_supervisor_id]
            target_sv_info = ReviewerInfo(
                id=target_sv_user.id,
                full_name=display_name(target_sv_user),
            )

        can_review = submission.status == SubmissionStatus.pending and (
            is_admin
            or (
                user.role == UserRole.supervisor
                and submission.target_supervisor_id == user.id
            )
        )

        submissions.append(
            SubmissionListResponse(
                id=submission.id,
                student_id=submission.student_id,
                student=student_info,
                department_id=submission.department_id,
                task_category_id=submission.task_category_id,
                case_count=submission.case_count,
                proof_key=submission.proof_key,
                notes=submission.notes,
                status=submission.status,
                target_supervisor_id=submission.target_supervisor_id,
                target_supervisor=target_sv_info,
                reviewed_by=submission.reviewed_by,
                reviewer=reviewer_info,
                review_notes=submission.review_notes,
                can_review=can_review,
                created_at=submission.created_at,
                updated_at=submission.updated_at,
                deleted_at=submission.deleted_at,
            )
        )

    return PaginatedResponse.create(submissions, total, limit, offset)


# NOTE: /deleted must be registered before /{submission_id} to avoid FastAPI
# matching the literal string "deleted" as a UUID.
@router.get("/deleted", response_model=PaginatedResponse[DeletedSubmissionListResponse])
async def list_deleted_submissions(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
):
    """List soft-deleted submissions. Admin only."""
    query = (
        select(CaseSubmission, User)
        .join(User, CaseSubmission.student_id == User.id)
        .where(CaseSubmission.deleted_at.isnot(None))
        .order_by(CaseSubmission.deleted_at.desc())
    )

    count_subquery = query.subquery()
    count_query = select(func.count()).select_from(count_subquery)
    total = (await db.execute(count_query)).scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()

    # Resolve who deleted each submission via audit log (batch query, not N+1)
    submission_ids = [row[0].id for row in rows]
    deleted_by_map: dict[UUID, tuple[UUID | None, str | None]] = {}
    if submission_ids:
        audit_result = await db.execute(
            select(AuditLog.record_id, AuditLog.user_id)
            .where(
                AuditLog.table_name == "case_submissions",
                AuditLog.action == "delete",
                AuditLog.record_id.in_(submission_ids),
            )
            .order_by(AuditLog.record_id, AuditLog.created_at.desc())
            .distinct(AuditLog.record_id)
        )
        audit_rows = audit_result.all()
        deleter_user_ids = {r.user_id for r in audit_rows if r.user_id}
        deleter_users: dict[UUID, User] = {}
        if deleter_user_ids:
            users_result = await db.execute(
                select(User).where(User.id.in_(list(deleter_user_ids)))
            )
            deleter_users = {u.id: u for u in users_result.scalars().all()}
        for audit_row in audit_rows:
            deleter = (
                deleter_users.get(audit_row.user_id) if audit_row.user_id else None
            )
            deleted_by_map[audit_row.record_id] = (
                audit_row.user_id,
                display_name(deleter) if deleter else None,
            )

    submissions = []
    for submission, student_user in rows:
        student_info = StudentInfo(
            id=student_user.id,
            full_name=display_name(student_user),
            student_id=student_user.institutional_id,
            email=student_user.email,
        )
        deleter_id, deleter_name = deleted_by_map.get(submission.id, (None, None))
        submissions.append(
            DeletedSubmissionListResponse(
                id=submission.id,
                student_id=submission.student_id,
                student=student_info,
                department_id=submission.department_id,
                task_category_id=submission.task_category_id,
                case_count=submission.case_count,
                proof_key=submission.proof_key,
                notes=submission.notes,
                status=submission.status,
                target_supervisor_id=submission.target_supervisor_id,
                target_supervisor=None,
                reviewed_by=submission.reviewed_by,
                reviewer=None,
                review_notes=submission.review_notes,
                can_review=False,
                created_at=submission.created_at,
                updated_at=submission.updated_at,
                deleted_at=submission.deleted_at,
                deleted_by_id=deleter_id,
                deleted_by_name=deleter_name,
            )
        )

    return PaginatedResponse.create(submissions, total, limit, offset)


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a submission detail with target supervisor info."""
    submission = await _get_submission_or_403(submission_id, user, db)

    return _build_submission_response(
        submission, await _get_target_sv_info(submission, db)
    )


@router.put("/{submission_id}", response_model=SubmissionResponse)
async def update_submission(
    submission_id: UUID,
    body: SubmissionUpdate,
    user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """Edit a pending submission. Students can only change case_count, proof_key, notes."""
    submission = await _get_submission_or_403(submission_id, user, db)

    if submission.status != SubmissionStatus.pending:
        raise HTTPException(
            status_code=400,
            detail="Only pending submissions can be edited",
        )

    old_values = {
        "case_count": submission.case_count,
        "proof_key": submission.proof_key,
        "notes": submission.notes,
    }

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return _build_submission_response(
            submission, await _get_target_sv_info(submission, db)
        )

    for field, value in updates.items():
        setattr(submission, field, value)

    await db.flush()
    await record_audit(
        db,
        user_id=user.id,
        action="update",
        table_name="case_submissions",
        record_id=submission.id,
        old_values=old_values,
        new_values=updates,
    )
    await db.commit()
    await db.refresh(submission)

    return _build_submission_response(
        submission, await _get_target_sv_info(submission, db)
    )


@router.patch("/{submission_id}/review", response_model=SubmissionResponse)
async def review_submission(
    submission_id: UUID,
    body: SubmissionReview,
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a submission. Only target supervisor or admin."""
    status_enum = SubmissionStatus(body.status)

    result = await db.execute(
        select(CaseSubmission).where(
            CaseSubmission.id == submission_id,
            CaseSubmission.deleted_at.is_(None),
        )
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.status != SubmissionStatus.pending:
        raise HTTPException(
            status_code=400,
            detail=f"Submission already {submission.status.value}",
        )

    # Only the target supervisor or admin can review
    if user.role != UserRole.admin:
        if submission.target_supervisor_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned supervisor can review this submission",
            )

    old_values = {
        "status": submission.status.value,
        "reviewed_by": None,
        "review_notes": None,
    }

    submission.status = status_enum
    submission.reviewed_by = user.id
    submission.review_notes = body.review_notes

    await db.flush()
    await record_audit(
        db,
        user_id=user.id,
        action="update",
        table_name="case_submissions",
        record_id=submission.id,
        old_values=old_values,
        new_values={
            "status": submission.status.value,
            "reviewed_by": str(submission.reviewed_by),
            "review_notes": submission.review_notes,
        },
    )

    # Notifications: fetch users needed, then queue records + emails before commit
    student_result = await db.execute(
        select(User).where(User.id == submission.student_id)
    )
    student = student_result.scalar_one()
    academic_sv_user = await _get_academic_supervisor(db, submission.student_id)
    await notify_submission_reviewed(db, submission, student, user, academic_sv_user)

    await db.commit()
    await db.refresh(submission)

    return _build_submission_response(
        submission, await _get_target_sv_info(submission, db)
    )


@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    submission_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a pending submission.

    Students can delete their own pending submissions.
    Supervisors and admins can delete any pending submission they can see.
    """
    result = await db.execute(
        select(CaseSubmission).where(
            CaseSubmission.id == submission_id,
            CaseSubmission.deleted_at.is_(None),
        )
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Students can only delete their own submissions
    if user.role == UserRole.student and submission.student_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if submission.status != SubmissionStatus.pending:
        raise HTTPException(
            status_code=400,
            detail="Only pending submissions can be deleted",
        )

    old_values = {
        "status": submission.status.value,
        "student_id": str(submission.student_id),
        "case_count": submission.case_count,
        "deleted_at": None,
    }

    submission.deleted_at = datetime.now(timezone.utc)

    await db.flush()
    await record_audit(
        db,
        user_id=user.id,
        action="delete",
        table_name="case_submissions",
        record_id=submission.id,
        old_values=old_values,
        new_values={"deleted_at": submission.deleted_at.isoformat()},
    )
    await db.commit()


@router.post("/{submission_id}/restore", response_model=SubmissionResponse)
async def restore_submission(
    submission_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Restore a soft-deleted submission. Admin only."""
    result = await db.execute(
        select(CaseSubmission).where(
            CaseSubmission.id == submission_id,
            CaseSubmission.deleted_at.isnot(None),
        )
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Deleted submission not found")

    old_deleted_at = submission.deleted_at
    submission.deleted_at = None

    await db.flush()
    await record_audit(
        db,
        user_id=user.id,
        action="update",
        table_name="case_submissions",
        record_id=submission.id,
        old_values={"deleted_at": old_deleted_at.isoformat()},
        new_values={"deleted_at": None},
    )
    await db.commit()
    await db.refresh(submission)

    return _build_submission_response(
        submission, await _get_target_sv_info(submission, db)
    )


@router.get("/{submission_id}/deleted-proof-url")
async def get_deleted_proof_url(
    submission_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get a presigned URL to view the proof image of a soft-deleted submission. Admin only."""
    result = await db.execute(
        select(CaseSubmission).where(
            CaseSubmission.id == submission_id,
            CaseSubmission.deleted_at.isnot(None),
        )
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Deleted submission not found")

    if not submission.proof_key:
        raise HTTPException(status_code=404, detail="Proof URL not available")

    url = generate_read_url(submission.proof_key)
    return {"url": url}


@router.get("/{submission_id}/proof-url")
async def get_proof_url(
    submission_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a temporary presigned URL to view the proof image."""
    submission = await _get_submission_or_403(submission_id, user, db)

    if not submission.proof_key:
        raise HTTPException(status_code=404, detail="Proof URL not available")

    url = generate_read_url(submission.proof_key)
    return {"url": url}
