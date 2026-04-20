from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin, require_student, require_supervisor
from app.core.database import get_db
from app.models.department import Department
from app.models.rotation import StudentRotation
from app.models.user import User, UserRole
from app.schemas.pagination import PaginatedResponse
from app.schemas.rotation import (
    DayAdjustmentRequest,
    DepartmentOverrideRequest,
    RotationCreate,
    RotationOffsetUpdate,
    RotationResponse,
)
from app.utils.audit import record_audit

router = APIRouter(prefix="/api/rotations", tags=["rotations"])

SECONDS_PER_DAY = 86400


def _resume_prior_rotation(prior: StudentRotation) -> StudentRotation:
    prior_segment_days = max(
        0,
        int((prior.ended_at - prior.started_at).total_seconds() // SECONDS_PER_DAY),
    )
    prior.days_offset = prior.days_offset + prior_segment_days
    prior.started_at = datetime.now(timezone.utc)
    prior.ended_at = None
    prior.is_current = True
    return prior


@router.get("/current", response_model=RotationResponse | None)
async def get_current_rotation(
    user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """Get the student's current active rotation. Returns null if none."""
    result = await db.execute(
        select(StudentRotation).where(
            StudentRotation.student_id == user.id,
            StudentRotation.is_current.is_(True),
        )
    )
    return result.scalar_one_or_none()


@router.post("", response_model=RotationResponse, status_code=status.HTTP_201_CREATED)
async def set_rotation(
    body: RotationCreate,
    user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """Set the student's current rotation. Resumes previous rotation if one exists."""
    # Verify department exists and is active
    dept_result = await db.execute(
        select(Department).where(
            Department.id == body.department_id,
            Department.is_active.is_(True),
        )
    )
    if not dept_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Department not found or inactive")

    # Check for active rotation — students cannot switch departments once assigned
    current_check = await db.execute(
        select(StudentRotation).where(
            StudentRotation.student_id == user.id,
            StudentRotation.is_current.is_(True),
        )
    )
    current = current_check.scalar_one_or_none()
    if current and current.department_id != body.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active department rotation. Contact an administrator to change departments.",
        )

    # If already assigned to the same department, return it as-is
    if current and current.department_id == body.department_id:
        return current

    # Deactivate current rotation (if any) in a single UPDATE
    await db.execute(
        update(StudentRotation)
        .where(
            StudentRotation.student_id == user.id,
            StudentRotation.is_current.is_(True),
        )
        .values(is_current=False, ended_at=func.now())
    )
    await db.flush()

    # Check for a prior rotation for this department (resume logic)
    prior_result = await db.execute(
        select(StudentRotation)
        .where(
            StudentRotation.student_id == user.id,
            StudentRotation.department_id == body.department_id,
            StudentRotation.is_current.is_(False),
        )
        .order_by(StudentRotation.started_at.desc())
        .limit(1)
    )
    prior = prior_result.scalar_one_or_none()

    if prior and prior.ended_at:
        rotation = _resume_prior_rotation(prior)
    else:
        # Create new rotation
        rotation = StudentRotation(
            student_id=user.id,
            department_id=body.department_id,
            is_current=True,
            days_offset=body.days_offset,
        )
        db.add(rotation)

    await db.commit()
    await db.refresh(rotation)
    return rotation


@router.get("/history", response_model=PaginatedResponse[RotationResponse])
async def get_rotation_history(
    user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
):
    """Get the student's rotation history with pagination, newest first."""
    # Build query
    query = select(StudentRotation).where(StudentRotation.student_id == user.id)

    # Get total count
    count_subquery = query.subquery()
    count_query = select(func.count()).select_from(count_subquery)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering (use id as tiebreaker for stable pagination)
    query = query.order_by(StudentRotation.started_at.desc(), StudentRotation.id.desc())
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)

    rotations = result.scalars().all()

    return PaginatedResponse.create(rotations, total, limit, offset)


@router.get(
    "/students/{student_id}/current",
    response_model=RotationResponse | None,
)
async def get_student_rotation(
    student_id: UUID,
    _user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific student's current rotation. Supervisor/admin only."""
    result = await db.execute(
        select(StudentRotation).where(
            StudentRotation.student_id == student_id,
            StudentRotation.is_current.is_(True),
        )
    )
    return result.scalar_one_or_none()


@router.patch("/{rotation_id}/offset", response_model=RotationResponse)
async def update_rotation_offset(
    rotation_id: UUID,
    body: RotationOffsetUpdate,
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: set days_offset for a specific rotation record."""
    result = await db.execute(
        select(StudentRotation).where(StudentRotation.id == rotation_id)
    )
    rotation = result.scalar_one_or_none()
    if not rotation:
        raise HTTPException(status_code=404, detail="Rotation not found")
    rotation.days_offset = body.days_offset
    await db.commit()
    await db.refresh(rotation)
    return rotation


@router.post(
    "/students/{student_id}/override-department",
    response_model=RotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def override_student_department(
    student_id: UUID,
    body: DepartmentOverrideRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: override a student's current department rotation.

    Deactivates the student's current rotation (preserving history) and
    creates a new one in the specified department.
    """
    # Verify student exists
    student = await db.get(User, student_id)
    if not student or student.role != UserRole.student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Verify department exists and is active
    dept = await db.get(Department, body.department_id)
    if not dept or not dept.is_active:
        raise HTTPException(status_code=404, detail="Department not found or inactive")

    # Get current rotation (if any)
    current_result = await db.execute(
        select(StudentRotation).where(
            StudentRotation.student_id == student_id,
            StudentRotation.is_current.is_(True),
        )
    )
    current = current_result.scalar_one_or_none()

    old_values = None
    if current:
        old_values = {
            "is_current": True,
            "department_id": str(current.department_id),
        }
        current.is_current = False
        current.ended_at = func.now()
        await db.flush()

        await record_audit(
            db,
            user_id=admin.id,
            action="update",
            table_name="student_rotations",
            record_id=current.id,
            old_values=old_values,
            new_values={
                "is_current": False,
                "department_id": str(current.department_id),
            },
        )

    # Check for a prior rotation in the new department (resume logic)
    prior_result = await db.execute(
        select(StudentRotation)
        .where(
            StudentRotation.student_id == student_id,
            StudentRotation.department_id == body.department_id,
            StudentRotation.is_current.is_(False),
        )
        .order_by(StudentRotation.started_at.desc())
        .limit(1)
    )
    prior = prior_result.scalar_one_or_none()

    if prior and prior.ended_at:
        rotation = _resume_prior_rotation(prior)
    else:
        rotation = StudentRotation(
            student_id=student_id,
            department_id=body.department_id,
            is_current=True,
            days_offset=body.days_offset,
        )
        db.add(rotation)

    await db.flush()

    await record_audit(
        db,
        user_id=admin.id,
        action="create",
        table_name="student_rotations",
        record_id=rotation.id,
        old_values=None,
        new_values={
            "student_id": str(student_id),
            "department_id": str(body.department_id),
            "is_current": True,
            "days_offset": body.days_offset,
        },
    )

    await db.commit()
    await db.refresh(rotation)
    return rotation


@router.patch(
    "/students/{student_id}/day",
    response_model=RotationResponse,
)
async def adjust_student_day(
    student_id: UUID,
    body: DayAdjustmentRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: adjust a student's rotation day by setting the total effective day.

    Calculates the required days_offset so that (days_offset + elapsed) == total_day.
    """
    student = await db.get(User, student_id)
    if not student or student.role != UserRole.student:
        raise HTTPException(status_code=404, detail="Student not found")

    result = await db.execute(
        select(StudentRotation).where(
            StudentRotation.student_id == student_id,
            StudentRotation.is_current.is_(True),
        )
    )
    rotation = result.scalar_one_or_none()
    if not rotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student has no active rotation",
        )

    elapsed = max(
        0,
        int(
            (datetime.now(timezone.utc) - rotation.started_at).total_seconds()
            // SECONDS_PER_DAY
        ),
    )
    new_offset = max(0, body.total_day - elapsed)

    old_values = {"student_id": str(student_id), "days_offset": rotation.days_offset}
    rotation.days_offset = new_offset
    await db.flush()

    await record_audit(
        db,
        user_id=admin.id,
        action="update",
        table_name="student_rotations",
        record_id=rotation.id,
        old_values=old_values,
        new_values={
            "student_id": str(student_id),
            "days_offset": new_offset,
            "requested_total_day": body.total_day,
        },
    )
    await db.commit()
    await db.refresh(rotation)
    return rotation
