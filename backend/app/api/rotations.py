from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_student, require_supervisor
from app.core.database import get_db
from app.models.department import Department
from app.models.rotation import StudentRotation
from app.models.user import User
from app.schemas.rotation import RotationCreate, RotationResponse

router = APIRouter(prefix="/api/rotations", tags=["rotations"])


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
    """Set the student's current rotation. Deactivates any existing rotation."""
    # Verify department exists and is active
    dept_result = await db.execute(
        select(Department).where(
            Department.id == body.department_id,
            Department.is_active.is_(True),
        )
    )
    if not dept_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Department not found or inactive")

    # Deactivate current rotation (if any) in a single UPDATE
    await db.execute(
        update(StudentRotation)
        .where(
            StudentRotation.student_id == user.id,
            StudentRotation.is_current.is_(True),
        )
        .values(is_current=False, ended_at=func.now())
    )

    # Create new rotation
    rotation = StudentRotation(
        student_id=user.id,
        department_id=body.department_id,
        is_current=True,
    )
    db.add(rotation)
    await db.commit()
    await db.refresh(rotation)
    return rotation


@router.get("/history", response_model=list[RotationResponse])
async def get_rotation_history(
    user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """Get the student's full rotation history, newest first."""
    result = await db.execute(
        select(StudentRotation)
        .where(StudentRotation.student_id == user.id)
        .order_by(StudentRotation.started_at.desc())
    )
    return result.scalars().all()


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
