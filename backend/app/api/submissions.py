from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    require_student,
    require_supervisor,
)
from app.core.database import get_db
from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.department import Department, TaskCategory
from app.models.submission import CaseSubmission, SubmissionStatus
from app.models.user import User, UserRole, display_name
from app.schemas.pagination import PaginatedResponse
from app.schemas.submission import (
    ReviewerInfo,
    StudentInfo,
    SubmissionCreate,
    SubmissionListResponse,
    SubmissionResponse,
    SubmissionReview,
    UploadUrlResponse,
)
from app.utils.audit import record_audit
from app.utils.storage import generate_read_url, generate_upload_url

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.get("/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    _user: User = Depends(require_student),
    filename: str = "image.jpg",
    content_type: str = "image/jpeg",
):
    """Get a presigned URL for uploading proof image to R2. Student only."""
    upload_url, object_key = generate_upload_url(
        filename=filename,
        content_type=content_type,
    )
    return UploadUrlResponse(upload_url=upload_url, key=object_key)


async def _get_submission_or_403(
    submission_id: UUID,
    user: User,
    db: AsyncSession,
) -> CaseSubmission:
    """Fetch submission and verify student ownership.

    Args:
        submission_id: ID of submission to fetch
        user: Current authenticated user
        db: Database session

    Returns:
        The submission if found and user has access

    Raises:
        HTTPException: 404 if not found, 403 if access denied
    """
    result = await db.execute(
        select(CaseSubmission).where(CaseSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Students can only see their own submissions
    if user.role == UserRole.student and submission.student_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return submission


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
        },
    )
    await db.commit()
    await db.refresh(submission)

    return submission


@router.get("", response_model=PaginatedResponse[SubmissionListResponse])
async def list_submissions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    department_id: UUID | None = Query(None),
    status_filter: SubmissionStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
):
    """List submissions with pagination. Students see their own; supervisors/admins see all."""
    # Join with User to get student information
    query = select(CaseSubmission, User).join(
        User, CaseSubmission.student_id == User.id
    )

    # Role-based filtering
    if user.role == UserRole.student:
        query = query.where(CaseSubmission.student_id == user.id)
    elif user.role == UserRole.supervisor:
        # Supervisors see submissions from:
        # 1. Students they are primary supervisor of
        primary_students = select(SupervisorAssignment.student_id).where(
            SupervisorAssignment.supervisor_id == user.id,
            SupervisorAssignment.assignment_type == AssignmentType.primary,
        )
        # 2. Any submission for a department they supervise
        supervised_depts = select(SupervisorAssignment.department_id).where(
            SupervisorAssignment.supervisor_id == user.id,
            SupervisorAssignment.assignment_type == AssignmentType.department,
        )
        query = query.where(
            CaseSubmission.student_id.in_(primary_students)
            | CaseSubmission.department_id.in_(supervised_depts)
        )
    # Admins see all submissions (no filter)

    # Optional filters
    if department_id:
        query = query.where(CaseSubmission.department_id == department_id)
    if status_filter:
        query = query.where(CaseSubmission.status == status_filter)

    # Get total count
    count_subquery = query.subquery()
    count_query = select(func.count()).select_from(count_subquery)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(CaseSubmission.created_at.desc())
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)

    # Collect all reviewer IDs
    reviewer_ids: set[UUID] = set()
    submissions_data = []
    for row in result.all():
        submission, student_user = row
        submissions_data.append((submission, student_user))
        if submission.reviewed_by:
            reviewer_ids.add(submission.reviewed_by)

    # Fetch all reviewers in one query
    reviewers_map: dict[UUID, User] = {}
    if reviewer_ids:
        reviewers_result = await db.execute(
            select(User).where(User.id.in_(list(reviewer_ids)))
        )
        reviewers_map = {r.id: r for r in reviewers_result.scalars().all()}

    # Build response with student and reviewer info
    submissions = []
    for submission, student_user in submissions_data:
        student_info = StudentInfo(
            id=student_user.id,
            full_name=display_name(student_user),
            student_id=student_user.student_id,
            email=student_user.email,
        )

        reviewer_info = None
        if submission.reviewed_by and submission.reviewed_by in reviewers_map:
            reviewer_user = reviewers_map[submission.reviewed_by]
            reviewer_info = ReviewerInfo(
                id=reviewer_user.id,
                full_name=display_name(reviewer_user),
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
                reviewed_by=submission.reviewed_by,
                reviewer=reviewer_info,
                review_notes=submission.review_notes,
                created_at=submission.created_at,
                updated_at=submission.updated_at,
            )
        )

    return PaginatedResponse.create(submissions, total, limit, offset)


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a submission detail. Students can only view their own."""
    submission = await _get_submission_or_403(submission_id, user, db)
    return submission


@router.patch("/{submission_id}/review", response_model=SubmissionResponse)
async def review_submission(
    submission_id: UUID,
    body: SubmissionReview,
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a submission. Supervisor/admin only."""
    # Convert string status to enum
    status_enum = SubmissionStatus(body.status)

    result = await db.execute(
        select(CaseSubmission).where(CaseSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.status != SubmissionStatus.pending:
        raise HTTPException(
            status_code=400,
            detail=f"Submission already {submission.status.value}",
        )

    # Store old values for audit
    old_values = {
        "status": submission.status.value,
        "reviewed_by": None,
        "review_notes": None,
    }

    submission.status = status_enum
    submission.reviewed_by = user.id
    submission.review_notes = body.review_notes

    await db.flush()  # Ensure changes are staged
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
    await db.commit()
    await db.refresh(submission)

    return submission


@router.get("/{submission_id}/proof-url")
async def get_proof_url(
    submission_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a temporary presigned URL to view the proof image."""
    submission = await _get_submission_or_403(submission_id, user, db)

    # Runtime guard: check for empty proof_key before generating URL
    if not submission.proof_key:
        raise HTTPException(status_code=404, detail="Proof URL not available")

    url = generate_read_url(submission.proof_key)
    return {"url": url}
