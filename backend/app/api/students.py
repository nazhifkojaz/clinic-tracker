from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_student
from app.core.database import get_db
from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.user import User, display_name
from app.schemas.submission import AcademicSupervisorResponse, ReviewerInfo

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("/me/academic-supervisor", response_model=AcademicSupervisorResponse)
async def get_academic_supervisor(
    user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """Get the student's academic (primary) supervisor."""
    result = await db.execute(
        select(User)
        .join(SupervisorAssignment, SupervisorAssignment.supervisor_id == User.id)
        .where(
            SupervisorAssignment.student_id == user.id,
            SupervisorAssignment.assignment_type == AssignmentType.primary,
            User.is_active.is_(True),
        )
    )
    supervisor = result.scalar_one_or_none()

    if not supervisor:
        return AcademicSupervisorResponse(supervisor=None)

    return AcademicSupervisorResponse(
        supervisor=ReviewerInfo(
            id=supervisor.id,
            full_name=display_name(supervisor),
        )
    )
