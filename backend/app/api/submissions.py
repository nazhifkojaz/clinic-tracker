from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    require_student,
    require_supervisor,
)
from app.core.database import get_db
from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.department import Department, TaskCategory
from app.models.rotation import StudentRotation
from app.models.submission import CaseSubmission, SubmissionStatus
from app.models.user import User, UserRole
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionResponse,
    SubmissionReview,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.utils.storage import generate_read_url, generate_upload_url

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


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


@router.post(
    "", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED
)
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
    await db.commit()
    await db.refresh(submission)
    return submission


@router.get("", response_model=list[SubmissionResponse])
async def list_submissions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    department_id: UUID | None = Query(None),
    status_filter: SubmissionStatus | None = Query(None, alias="status"),
):
    """List submissions. Students see their own; supervisors/admins see all."""
    query = select(CaseSubmission)

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
        # 2. Students currently rotating in a department they supervise
        supervised_depts = select(SupervisorAssignment.department_id).where(
            SupervisorAssignment.supervisor_id == user.id,
            SupervisorAssignment.assignment_type == AssignmentType.department,
        )
        dept_students = select(StudentRotation.student_id).where(
            StudentRotation.department_id.in_(supervised_depts),
            StudentRotation.is_current.is_(True),
        )
        query = query.where(
            CaseSubmission.student_id.in_(primary_students)
            | CaseSubmission.student_id.in_(dept_students)
        )
    # Admins see all submissions (no filter)

    # Optional filters
    if department_id:
        query = query.where(CaseSubmission.department_id == department_id)
    if status_filter:
        query = query.where(CaseSubmission.status == status_filter)

    query = query.order_by(CaseSubmission.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a submission detail. Students can only view their own."""
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


@router.patch("/{submission_id}/review", response_model=SubmissionResponse)
async def review_submission(
    submission_id: UUID,
    body: SubmissionReview,
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a submission. Supervisor/admin only."""
    # Validate status transition
    if body.status == SubmissionStatus.pending:
        raise HTTPException(
            status_code=400, detail="Cannot set status back to pending"
        )

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

    submission.status = body.status
    submission.reviewed_by = user.id
    submission.review_notes = body.review_notes

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
    result = await db.execute(
        select(CaseSubmission).where(CaseSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Students can only see their own
    if user.role == UserRole.student and submission.student_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    url = generate_read_url(submission.proof_url)
    return {"url": url}
