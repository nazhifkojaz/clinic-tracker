import uuid
import random
import string
from datetime import datetime, timezone

from app.models.department import Department, TaskCategory
from app.models.rotation import StudentRotation
from app.models.submission import CaseSubmission, SubmissionStatus


def _random_suffix() -> str:
    """Generate a random suffix for unique names."""
    return "".join(random.choices(string.ascii_lowercase, k=8))


async def create_department(
    db,
    name: str | None = None,
    description: str = "",
    is_active: bool = True,
    rotation_duration_days: int | None = None,
) -> Department:
    """Create a test department."""
    if name is None:
        name = f"Test Department {_random_suffix()}"
    dept = Department(
        name=name,
        description=description,
        is_active=is_active,
        rotation_duration_days=rotation_duration_days,
    )
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return dept


async def create_category(
    db,
    department_id: uuid.UUID,
    name: str | None = None,
    required_count: int = 10,
    is_active: bool = True,
) -> TaskCategory:
    """Create a test task category."""
    if name is None:
        name = f"Test Category {_random_suffix()}"
    cat = TaskCategory(
        department_id=department_id,
        name=name,
        required_count=required_count,
        is_active=is_active,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def create_submission(
    db,
    student_id: uuid.UUID,
    department_id: uuid.UUID,
    task_category_id: uuid.UUID,
    case_count: int = 1,
    status: SubmissionStatus = SubmissionStatus.pending,
    proof_key: str = "submissions/proof.jpg",
    notes: str | None = None,
) -> CaseSubmission:
    """Create a test case submission."""
    sub = CaseSubmission(
        student_id=student_id,
        department_id=department_id,
        task_category_id=task_category_id,
        case_count=case_count,
        proof_key=proof_key,
        status=status,
        notes=notes,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def create_rotation(
    db,
    student_id: uuid.UUID,
    department_id: uuid.UUID,
    is_current: bool = True,
    started_at: datetime | None = None,
    days_offset: int = 0,
) -> StudentRotation:
    """Create a test student rotation."""
    if started_at is None:
        started_at = datetime.now(timezone.utc)
    rot = StudentRotation(
        student_id=student_id,
        department_id=department_id,
        is_current=is_current,
        started_at=started_at,
        days_offset=days_offset,
    )
    db.add(rot)
    await db.commit()
    await db.refresh(rot)
    return rot
