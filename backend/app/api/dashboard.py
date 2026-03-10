# backend/app/api/dashboard.py

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_student, require_supervisor
from app.core.database import get_db
from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.department import Department, TaskCategory
from app.models.rotation import StudentRotation
from app.models.submission import CaseSubmission, SubmissionStatus
from app.models.user import User, UserRole
from app.schemas.dashboard import (
    CategoryProgress,
    DepartmentDashboardResponse,
    DepartmentProgress,
    DepartmentStudentProgress,
    ProgressDataPoint,
    RecentSubmission,
    StudentDashboardResponse,
    StudentSummary,
    SupervisorDashboardResponse,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def _build_student_dashboard(
    student: User, db: AsyncSession
) -> StudentDashboardResponse:
    """Build complete dashboard data for a student. Shared logic for both endpoints."""

    # 1. Get all active departments with their categories
    dept_result = await db.execute(
        select(Department).where(Department.is_active.is_(True))
    )
    departments = dept_result.scalars().all()

    # 2. Get all active task categories
    cat_result = await db.execute(
        select(TaskCategory).where(TaskCategory.is_active.is_(True))
    )
    all_categories = cat_result.scalars().all()

    # Build a lookup: department_id -> [categories]
    dept_categories: dict[UUID, list] = {}
    for cat in all_categories:
        dept_categories.setdefault(cat.department_id, []).append(cat)

    # 3. Get aggregated submission counts grouped by (task_category_id, status)
    sub_query = (
        select(
            CaseSubmission.task_category_id,
            CaseSubmission.status,
            func.sum(CaseSubmission.case_count).label("total"),
        )
        .where(CaseSubmission.student_id == student.id)
        .group_by(CaseSubmission.task_category_id, CaseSubmission.status)
    )
    sub_result = await db.execute(sub_query)
    sub_rows = sub_result.all()

    # Build lookup: (category_id, status) -> count
    counts: dict[tuple, int] = {}
    for row in sub_rows:
        counts[(row.task_category_id, row.status)] = int(row.total)

    # 4. Build department progress
    department_progresses: list[DepartmentProgress] = []
    grand_total_required = 0
    grand_total_completed = 0

    for dept in departments:
        cats = dept_categories.get(dept.id, [])
        if not cats:
            continue

        cat_progresses: list[CategoryProgress] = []
        dept_required = 0
        dept_completed = 0

        for cat in cats:
            approved = counts.get((cat.id, SubmissionStatus.approved), 0)
            pending = counts.get((cat.id, SubmissionStatus.pending), 0)
            pct = (
                min((approved / cat.required_count) * 100, 100.0)
                if cat.required_count > 0
                else 0.0
            )

            cat_progresses.append(
                CategoryProgress(
                    category_id=cat.id,
                    category_name=cat.name,
                    required_count=cat.required_count,
                    completed_count=approved,
                    pending_count=pending,
                    completion_percentage=round(pct, 1),
                )
            )
            dept_required += cat.required_count
            dept_completed += approved

        dept_pct = (dept_completed / dept_required * 100) if dept_required > 0 else 0.0
        department_progresses.append(
            DepartmentProgress(
                department_id=dept.id,
                department_name=dept.name,
                categories=cat_progresses,
                total_required=dept_required,
                total_completed=dept_completed,
                completion_percentage=round(dept_pct, 1),
            )
        )
        grand_total_required += dept_required
        grand_total_completed += dept_completed

    # 5. Overall completion
    overall_pct = (
        (grand_total_completed / grand_total_required * 100)
        if grand_total_required > 0
        else 0.0
    )

    # 6. Current rotation
    rot_result = await db.execute(
        select(StudentRotation).where(
            StudentRotation.student_id == student.id,
            StudentRotation.is_current.is_(True),
        )
    )
    current_rotation = rot_result.scalar_one_or_none()
    current_dept_name = None
    if current_rotation:
        dept_obj = await db.get(Department, current_rotation.department_id)
        current_dept_name = dept_obj.name if dept_obj else None

    # 7. Recent submissions (last 10)
    recent_query = (
        select(
            CaseSubmission.id,
            CaseSubmission.case_count,
            CaseSubmission.status,
            CaseSubmission.created_at,
            Department.name.label("department_name"),
            TaskCategory.name.label("category_name"),
        )
        .join(Department, CaseSubmission.department_id == Department.id)
        .join(TaskCategory, CaseSubmission.task_category_id == TaskCategory.id)
        .where(CaseSubmission.student_id == student.id)
        .order_by(CaseSubmission.created_at.desc())
        .limit(10)
    )
    recent_result = await db.execute(recent_query)
    recent_subs = [
        RecentSubmission(
            id=row.id,
            department_name=row.department_name,
            category_name=row.category_name,
            case_count=row.case_count,
            status=row.status.value,
            created_at=row.created_at,
        )
        for row in recent_result.all()
    ]

    # 8. Progress over time (cumulative approved cases by date)
    pot_query = (
        select(
            func.date(CaseSubmission.created_at).label("submission_date"),
            func.sum(CaseSubmission.case_count).label("daily_cases"),
        )
        .where(
            CaseSubmission.student_id == student.id,
            CaseSubmission.status == SubmissionStatus.approved,
        )
        .group_by(func.date(CaseSubmission.created_at))
        .order_by(func.date(CaseSubmission.created_at))
    )
    pot_result = await db.execute(pot_query)
    pot_rows = pot_result.all()

    cumulative = 0
    progress_points: list[ProgressDataPoint] = []
    for row in pot_rows:
        cumulative += int(row.daily_cases)
        progress_points.append(
            ProgressDataPoint(
                date=str(row.submission_date),
                cumulative_cases=cumulative,
            )
        )

    return StudentDashboardResponse(
        student_id=student.id,
        student_name=student.full_name
        if student.full_name
        else (student.student_id or student.email),
        current_department=current_dept_name,
        overall_completion_percentage=round(overall_pct, 1),
        total_required=grand_total_required,
        total_completed=grand_total_completed,
        departments=department_progresses,
        recent_submissions=recent_subs,
        progress_over_time=progress_points,
    )


@router.get("/student", response_model=StudentDashboardResponse)
async def get_student_dashboard(
    user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """Get the logged-in student's dashboard data."""
    return await _build_student_dashboard(user, db)


@router.get("/student/{student_id}", response_model=StudentDashboardResponse)
async def get_student_dashboard_by_id(
    student_id: UUID,
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific student's dashboard data. Supervisor/admin only."""
    # Fetch the student
    student = await db.get(User, student_id)
    if not student or student.role != UserRole.student:
        raise HTTPException(status_code=404, detail="Student not found")

    # If supervisor (not admin), verify assignment authority
    if user.role == UserRole.supervisor:
        # Check primary assignment
        primary_check = await db.execute(
            select(SupervisorAssignment.id).where(
                SupervisorAssignment.supervisor_id == user.id,
                SupervisorAssignment.student_id == student_id,
                SupervisorAssignment.assignment_type == AssignmentType.primary,
            )
        )
        has_primary = primary_check.scalar_one_or_none() is not None

        if not has_primary:
            # Check department assignment: supervisor oversees a dept where student is rotating
            dept_check_query = (
                select(SupervisorAssignment.id)
                .join(
                    StudentRotation,
                    SupervisorAssignment.department_id == StudentRotation.department_id,
                )
                .where(
                    SupervisorAssignment.supervisor_id == user.id,
                    SupervisorAssignment.assignment_type == AssignmentType.department,
                    StudentRotation.student_id == student_id,
                    StudentRotation.is_current.is_(True),
                )
            )
            dept_result = await db.execute(dept_check_query)
            has_dept = dept_result.scalar_one_or_none() is not None

            if not has_dept:
                raise HTTPException(
                    status_code=403,
                    detail="You are not assigned to this student",
                )

    return await _build_student_dashboard(student, db)


def _classify_status(completion_percentage: float) -> str:
    """Classify student status based on overall completion percentage."""
    if completion_percentage >= 60:
        return "on_track"
    elif completion_percentage >= 30:
        return "at_risk"
    else:
        return "behind"


async def _get_supervised_student_ids(
    supervisor_id: UUID, db: AsyncSession
) -> list[UUID]:
    """Get all student IDs a supervisor is responsible for."""
    # 1. Primary assignments: direct student links
    primary_query = select(SupervisorAssignment.student_id).where(
        SupervisorAssignment.supervisor_id == supervisor_id,
        SupervisorAssignment.assignment_type == AssignmentType.primary,
        SupervisorAssignment.student_id.isnot(None),
    )
    primary_result = await db.execute(primary_query)
    primary_ids = {row[0] for row in primary_result.all()}

    # 2. Department assignments: students currently rotating in supervised depts
    dept_query = select(SupervisorAssignment.department_id).where(
        SupervisorAssignment.supervisor_id == supervisor_id,
        SupervisorAssignment.assignment_type == AssignmentType.department,
    )
    dept_result = await db.execute(dept_query)
    supervised_dept_ids = [row[0] for row in dept_result.all()]

    dept_student_ids: set[UUID] = set()
    if supervised_dept_ids:
        rot_query = select(StudentRotation.student_id).where(
            StudentRotation.department_id.in_(supervised_dept_ids),
            StudentRotation.is_current.is_(True),
        )
        rot_result = await db.execute(rot_query)
        dept_student_ids = {row[0] for row in rot_result.all()}

    return list(primary_ids | dept_student_ids)


@router.get("/supervisor", response_model=SupervisorDashboardResponse)
async def get_supervisor_dashboard(
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Get supervisor's overview dashboard with student statuses."""

    # Determine student scope
    if user.role == UserRole.admin:
        # Admins see all students
        all_students_result = await db.execute(
            select(User).where(
                User.role == UserRole.student,
                User.is_active.is_(True),
            )
        )
        students = all_students_result.scalars().all()
    else:
        student_ids = await _get_supervised_student_ids(user.id, db)
        if not student_ids:
            return SupervisorDashboardResponse(
                total_students=0,
                on_track_count=0,
                at_risk_count=0,
                behind_count=0,
                students=[],
            )
        students_result = await db.execute(
            select(User).where(
                User.id.in_(student_ids),
                User.is_active.is_(True),
            )
        )
        students = students_result.scalars().all()

    # Get all active categories for total required calculation
    cat_result = await db.execute(
        select(TaskCategory).where(TaskCategory.is_active.is_(True))
    )
    all_categories = cat_result.scalars().all()
    total_required_global = sum(c.required_count for c in all_categories)

    # Get all approved submission totals per student in one query
    student_ids_list = [s.id for s in students]
    if student_ids_list:
        agg_query = (
            select(
                CaseSubmission.student_id,
                func.sum(CaseSubmission.case_count).label("total_completed"),
            )
            .where(
                CaseSubmission.student_id.in_(student_ids_list),
                CaseSubmission.status == SubmissionStatus.approved,
            )
            .group_by(CaseSubmission.student_id)
        )
        agg_result = await db.execute(agg_query)
        completed_map = {
            row.student_id: int(row.total_completed) for row in agg_result.all()
        }
    else:
        completed_map = {}

    # Get current rotations for all students in one query
    if student_ids_list:
        rot_query = (
            select(StudentRotation.student_id, Department.name)
            .join(Department, StudentRotation.department_id == Department.id)
            .where(
                StudentRotation.student_id.in_(student_ids_list),
                StudentRotation.is_current.is_(True),
            )
        )
        rot_result = await db.execute(rot_query)
        rotation_map = {row.student_id: row.name for row in rot_result.all()}
    else:
        rotation_map = {}

    # Build student summaries
    summaries: list[StudentSummary] = []
    on_track = at_risk = behind = 0

    for student in students:
        completed = completed_map.get(student.id, 0)
        pct = (
            (completed / total_required_global * 100)
            if total_required_global > 0
            else 0.0
        )
        status = _classify_status(pct)

        if status == "on_track":
            on_track += 1
        elif status == "at_risk":
            at_risk += 1
        else:
            behind += 1

        # Use student_code or email as fallback if full_name is empty
        display_name = (
            student.full_name
            if student.full_name
            else (student.student_id or student.email)
        )

        summaries.append(
            StudentSummary(
                student_id=student.id,
                student_name=display_name,
                student_email=student.email,
                student_code=student.student_id,
                current_department=rotation_map.get(student.id),
                overall_completion_percentage=round(pct, 1),
                total_required=total_required_global,
                total_completed=completed,
                status=status,
            )
        )

    return SupervisorDashboardResponse(
        total_students=len(students),
        on_track_count=on_track,
        at_risk_count=at_risk,
        behind_count=behind,
        students=summaries,
    )


@router.get("/department/{department_id}", response_model=DepartmentDashboardResponse)
async def get_department_dashboard(
    department_id: UUID,
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Get department-specific dashboard. Supervisor (with dept assignment) or admin."""
    # Verify department exists
    department = await db.get(Department, department_id)
    if not department or not department.is_active:
        raise HTTPException(status_code=404, detail="Department not found")

    # Access control for non-admin supervisors
    if user.role == UserRole.supervisor:
        assignment_check = await db.execute(
            select(SupervisorAssignment.id).where(
                SupervisorAssignment.supervisor_id == user.id,
                SupervisorAssignment.assignment_type == AssignmentType.department,
                SupervisorAssignment.department_id == department_id,
            )
        )
        if not assignment_check.scalar_one_or_none():
            raise HTTPException(
                status_code=403,
                detail="You are not assigned to this department",
            )

    # Get task categories for this department
    cat_result = await db.execute(
        select(TaskCategory).where(
            TaskCategory.department_id == department_id,
            TaskCategory.is_active.is_(True),
        )
    )
    categories = cat_result.scalars().all()
    dept_total_required = sum(c.required_count for c in categories)

    # Find all students with submissions in this department or currently rotating here
    sub_student_ids = (
        select(CaseSubmission.student_id)
        .where(CaseSubmission.department_id == department_id)
        .distinct()
    )

    rot_student_ids = select(StudentRotation.student_id).where(
        StudentRotation.department_id == department_id,
        StudentRotation.is_current.is_(True),
    )

    student_result = await db.execute(
        select(User).where(
            User.id.in_(sub_student_ids) | User.id.in_(rot_student_ids),
            User.is_active.is_(True),
        )
    )
    students = student_result.scalars().all()

    # Get approved submission totals per student for this department
    if students:
        agg_query = (
            select(
                CaseSubmission.student_id,
                func.sum(CaseSubmission.case_count).label("total_completed"),
            )
            .where(
                CaseSubmission.student_id.in_([s.id for s in students]),
                CaseSubmission.department_id == department_id,
                CaseSubmission.status == SubmissionStatus.approved,
            )
            .group_by(CaseSubmission.student_id)
        )
        agg_result = await db.execute(agg_query)
        completed_map = {
            row.student_id: int(row.total_completed) for row in agg_result.all()
        }
    else:
        completed_map = {}

    # Build student progress list
    student_progresses: list[DepartmentStudentProgress] = []
    total_completion_sum = 0.0

    for student in students:
        completed = completed_map.get(student.id, 0)
        pct = (
            (completed / dept_total_required * 100) if dept_total_required > 0 else 0.0
        )
        display_name = (
            student.full_name
            if student.full_name
            else (student.student_id or student.email)
        )
        student_progresses.append(
            DepartmentStudentProgress(
                student_id=student.id,
                student_name=display_name,
                total_required=dept_total_required,
                total_completed=completed,
                completion_percentage=round(pct, 1),
                status=_classify_status(pct),
            )
        )
        total_completion_sum += pct

    avg_completion = (total_completion_sum / len(students)) if students else 0.0

    return DepartmentDashboardResponse(
        department_id=department.id,
        department_name=department.name,
        total_students=len(students),
        average_completion=round(avg_completion, 1),
        students=student_progresses,
    )
