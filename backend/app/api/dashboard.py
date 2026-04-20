# backend/app/api/dashboard.py

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_student, require_supervisor
from app.core.cache import categories_cache, departments_cache
from app.core.database import get_db
from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.department import Department, TaskCategory
from app.models.rotation import StudentRotation
from app.models.submission import CaseSubmission, SubmissionStatus
from app.models.user import User, UserRole, display_name
from app.schemas.dashboard import (
    CategoryProgress,
    DepartmentDashboardResponse,
    DepartmentProgress,
    DepartmentStudentProgress,
    DepartmentTrackerEntry,
    DepartmentTrackerResponse,
    ProgressDataPoint,
    RecentSubmission,
    StudentDashboardResponse,
    StudentSummary,
    SupervisorDashboardResponse,
)
from app.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def _build_student_dashboard(
    student: User, db: AsyncSession
) -> StudentDashboardResponse:
    """Build complete dashboard data for a student. Shared logic for both endpoints."""

    # 1. Get all active departments (with cache)
    CACHE_KEY_DEPTS = "all_active_departments"
    departments = await departments_cache.get(CACHE_KEY_DEPTS)

    if departments is None:
        dept_result = await db.execute(
            select(Department).where(Department.is_active.is_(True))
        )
        departments = dept_result.scalars().all()
        await departments_cache.set(CACHE_KEY_DEPTS, departments)

    # 2. Get all active task categories (with cache)
    CACHE_KEY_CATS = "all_active_categories"
    all_categories = await categories_cache.get(CACHE_KEY_CATS)

    if all_categories is None:
        cat_result = await db.execute(
            select(TaskCategory).where(TaskCategory.is_active.is_(True))
        )
        all_categories = cat_result.scalars().all()
        await categories_cache.set(CACHE_KEY_CATS, all_categories)

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
        .where(
            CaseSubmission.student_id == student.id,
            CaseSubmission.deleted_at.is_(None),
        )
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

    # 6. Current rotation with department name and rotation duration (single query with JOIN)
    rot_result = await db.execute(
        select(
            StudentRotation,
            Department.name,
            Department.rotation_duration_days,
        )
        .outerjoin(Department, StudentRotation.department_id == Department.id)
        .where(
            StudentRotation.student_id == student.id,
            StudentRotation.is_current.is_(True),
        )
    )
    row = rot_result.one_or_none()
    current_dept_name = row[1] if row else None
    rotation_duration_days = row[2] if row else None

    # 6b. Compute rotation time progress and warning
    show_rotation_warning = False
    rotation_days_active = 0
    rotation_time_pct = 0.0
    if row and rotation_duration_days is not None and rotation_duration_days > 0:
        current_rotation = row[0]
        now_utc = datetime.now(timezone.utc)
        elapsed = max(
            0, int((now_utc - current_rotation.started_at).total_seconds() // 86400)
        )
        rotation_days_active = current_rotation.days_offset + elapsed
        rotation_time_pct = (rotation_days_active / rotation_duration_days) * 100
        # Case progress for current department
        current_dept_approved = sum(
            counts.get((cat.id, SubmissionStatus.approved), 0)
            for cat in dept_categories.get(current_rotation.department_id, [])
        )
        current_dept_required = sum(
            cat.required_count
            for cat in dept_categories.get(current_rotation.department_id, [])
        )
        if current_dept_required > 0:
            case_pct = (current_dept_approved / current_dept_required) * 100
            show_rotation_warning = rotation_time_pct >= 50 and case_pct < 60

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
        .where(
            CaseSubmission.student_id == student.id,
            CaseSubmission.deleted_at.is_(None),
        )
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
            CaseSubmission.deleted_at.is_(None),
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
        student_name=display_name(student),
        current_department=current_dept_name,
        overall_completion_percentage=round(overall_pct, 1),
        total_required=grand_total_required,
        total_completed=grand_total_completed,
        departments=department_progresses,
        recent_submissions=recent_subs,
        progress_over_time=progress_points,
        show_rotation_warning=show_rotation_warning,
        rotation_days_active=rotation_days_active,
        rotation_duration_days=rotation_duration_days or 0,
        rotation_time_pct=round(min(rotation_time_pct, 100.0), 1),
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
) -> dict[UUID, str]:
    """Get all student IDs a supervisor is responsible for with their assignment type.

    Returns a dict mapping student_id -> assignment_type ("primary" or "department").
    Primary takes precedence if a student has both assignment types.

    Uses concurrent queries to fetch primary assignments and department assignments
    in parallel, reducing round-trips.
    """
    # Run primary and department queries concurrently
    primary_result, dept_result = await asyncio.gather(
        db.execute(
            select(SupervisorAssignment.student_id).where(
                SupervisorAssignment.supervisor_id == supervisor_id,
                SupervisorAssignment.assignment_type == AssignmentType.primary,
                SupervisorAssignment.student_id.isnot(None),
            )
        ),
        db.execute(
            select(SupervisorAssignment.department_id).where(
                SupervisorAssignment.supervisor_id == supervisor_id,
                SupervisorAssignment.assignment_type == AssignmentType.department,
            )
        ),
    )

    student_types: dict[UUID, str] = {}
    for row in primary_result.all():
        student_types[row[0]] = "primary"

    supervised_dept_ids = [row[0] for row in dept_result.all()]

    # Fetch students rotating in supervised departments
    if supervised_dept_ids:
        rot_result = await db.execute(
            select(StudentRotation.student_id).where(
                StudentRotation.department_id.in_(supervised_dept_ids),
                StudentRotation.is_current.is_(True),
            )
        )
        for row in rot_result.all():
            # Primary takes precedence over department
            if row[0] not in student_types:
                student_types[row[0]] = "department"

    return student_types


@router.get("/supervisor", response_model=SupervisorDashboardResponse)
async def get_supervisor_dashboard(
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Students per page"),
    offset: int = Query(0, ge=0, description="Students to skip"),
):
    """Get supervisor's overview dashboard with student statuses.

    Supports pagination to handle large student cohorts efficiently.
    Status counts are computed from ALL students, not just the paginated subset.
    """

    # Determine student scope
    if user.role == UserRole.admin:
        # Build base query for counting
        base_students_query = select(User).where(
            User.role == UserRole.student,
            User.is_active.is_(True),
        )
    else:
        student_types = await _get_supervised_student_ids(user.id, db)
        if not student_types:
            return SupervisorDashboardResponse(
                total_students=0,
                on_track_count=0,
                at_risk_count=0,
                behind_count=0,
                students=PaginatedResponse.create([], 0, limit, offset),
            )
        # Build base query for counting
        base_students_query = select(User).where(
            User.id.in_(student_types),
            User.is_active.is_(True),
        )

    # Count total students for pagination metadata
    count_subquery = base_students_query.subquery()
    count_query = select(func.count()).select_from(count_subquery)
    total_result = await db.execute(count_query)
    total_students_count = total_result.scalar() or 0

    # Fetch paginated students (only needed columns)
    if user.role == UserRole.admin:
        students_query = select(
            User.id, User.full_name, User.email, User.institutional_id
        ).where(User.role == UserRole.student, User.is_active.is_(True))
    else:
        students_query = select(
            User.id, User.full_name, User.email, User.institutional_id
        ).where(User.id.in_(student_types), User.is_active.is_(True))

    # Apply pagination
    students_query = (
        students_query.order_by(User.full_name, User.id).limit(limit).offset(offset)
    )
    students_result = await db.execute(students_query)
    students = students_result.all()

    # Get all active categories for total required calculation
    cat_result = await db.execute(
        select(TaskCategory).where(TaskCategory.is_active.is_(True))
    )
    all_categories = cat_result.scalars().all()
    total_required_global = sum(c.required_count for c in all_categories)

    # Get approved submission totals for paginated students
    student_ids_list = [s[0] for s in students] if students else []
    if student_ids_list:
        agg_query = (
            select(
                CaseSubmission.student_id,
                func.sum(CaseSubmission.case_count).label("total_completed"),
            )
            .where(
                CaseSubmission.student_id.in_(student_ids_list),
                CaseSubmission.status == SubmissionStatus.approved,
                CaseSubmission.deleted_at.is_(None),
            )
            .group_by(CaseSubmission.student_id)
        )
        agg_result = await db.execute(agg_query)
        completed_map = {
            row.student_id: int(row.total_completed) for row in agg_result.all()
        }
    else:
        completed_map = {}

    # Get current rotations for paginated students
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

    # Build student summaries (paginated subset only)
    summaries: list[StudentSummary] = []

    for student_id, full_name, email, student_code in students:
        completed = completed_map.get(student_id, 0)
        pct = (
            (completed / total_required_global * 100)
            if total_required_global > 0
            else 0.0
        )
        status = _classify_status(pct)

        # Build display name from available fields
        student_name = full_name or student_code or email

        summaries.append(
            StudentSummary(
                student_id=student_id,
                student_name=student_name,
                student_email=email,
                student_code=student_code,
                current_department=rotation_map.get(student_id),
                overall_completion_percentage=round(pct, 1),
                total_required=total_required_global,
                total_completed=completed,
                status=status,
                assignment_type=student_types.get(student_id) if user.role == UserRole.supervisor else None,
            )
        )

    # Compute status counts for ALL students (not just paginated subset)
    # Get all student IDs for counting
    if user.role == UserRole.admin:
        all_student_ids_query = select(User.id).where(
            User.role == UserRole.student,
            User.is_active.is_(True),
        )
    else:
        all_student_ids_query = select(User.id).where(
            User.id.in_(student_types),
            User.is_active.is_(True),
        )

    all_ids_result = await db.execute(all_student_ids_query)
    all_student_ids = [row[0] for row in all_ids_result.all()]

    # Get completion data for ALL students (for accurate counts)
    if all_student_ids:
        all_agg_query = (
            select(
                CaseSubmission.student_id,
                func.sum(CaseSubmission.case_count).label("total_completed"),
            )
            .where(
                CaseSubmission.student_id.in_(all_student_ids),
                CaseSubmission.status == SubmissionStatus.approved,
                CaseSubmission.deleted_at.is_(None),
            )
            .group_by(CaseSubmission.student_id)
        )
        all_agg_result = await db.execute(all_agg_query)
        all_completed_map = {
            row.student_id: int(row.total_completed) for row in all_agg_result.all()
        }
    else:
        all_completed_map = {}

    # Compute status counts from all students
    on_track = at_risk = behind = 0
    for student_id in all_student_ids:
        completed = all_completed_map.get(student_id, 0)
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

    # Create paginated response
    paginated_students = PaginatedResponse.create(
        items=summaries,
        total=total_students_count,
        limit=limit,
        offset=offset,
    )

    return SupervisorDashboardResponse(
        total_students=paginated_students.total,
        on_track_count=on_track,
        at_risk_count=at_risk,
        behind_count=behind,
        students=paginated_students,
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
        .where(
            CaseSubmission.department_id == department_id,
            CaseSubmission.deleted_at.is_(None),
        )
        .distinct()
    )

    rot_student_ids = select(StudentRotation.student_id).where(
        StudentRotation.department_id == department_id,
        StudentRotation.is_current.is_(True),
    )

    # PERF-09: Select only required User columns to reduce data transfer
    student_result = await db.execute(
        select(
            User.id,
            User.full_name,
            User.email,
            User.institutional_id,
        ).where(
            User.id.in_(sub_student_ids) | User.id.in_(rot_student_ids),
            User.is_active.is_(True),
        )
    )
    students = student_result.all()  # Returns tuples instead of User objects

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
                CaseSubmission.deleted_at.is_(None),
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

    # PERF-09: Process student tuples (id, full_name, email, institutional_id)
    for student_id, full_name, email, institutional_id in students:
        completed = completed_map.get(student_id, 0)
        pct = (
            (completed / dept_total_required * 100) if dept_total_required > 0 else 0.0
        )
        # Build display name from available fields (consistent with display_name())
        student_name = full_name or institutional_id or email
        student_progresses.append(
            DepartmentStudentProgress(
                student_id=student_id,
                student_name=student_name,
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


@router.get("/tracker", response_model=DepartmentTrackerResponse)
async def get_rotation_tracker(
    user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """Per-department rotation tracker for the student. Student-only."""
    now = datetime.now(timezone.utc)

    # PERF-08: 1. Get all active departments (with cache, consistent with student dashboard)
    CACHE_KEY_DEPTS = "all_active_departments"
    departments = await departments_cache.get(CACHE_KEY_DEPTS)

    if departments is None:
        dept_result = await db.execute(
            select(Department).where(Department.is_active.is_(True))
        )
        departments = dept_result.scalars().all()
        await departments_cache.set(CACHE_KEY_DEPTS, departments)

    # PERF-08: 2. Get all active task categories (with cache, consistent with student dashboard)
    CACHE_KEY_CATS = "all_active_categories"
    all_cats = await categories_cache.get(CACHE_KEY_CATS)

    if all_cats is None:
        cat_result = await db.execute(
            select(TaskCategory).where(TaskCategory.is_active.is_(True))
        )
        all_cats = cat_result.scalars().all()
        await categories_cache.set(CACHE_KEY_CATS, all_cats)
    dept_required: dict[UUID, int] = {}
    for cat in all_cats:
        dept_required[cat.department_id] = (
            dept_required.get(cat.department_id, 0) + cat.required_count
        )

    # 3. Student's submission counts per department
    sub_result = await db.execute(
        select(
            CaseSubmission.department_id,
            CaseSubmission.status,
            func.sum(CaseSubmission.case_count).label("total"),
        )
        .where(
            CaseSubmission.student_id == user.id,
            CaseSubmission.deleted_at.is_(None),
        )
        .group_by(CaseSubmission.department_id, CaseSubmission.status)
    )
    approved_map: dict[UUID, int] = {}
    pending_map: dict[UUID, int] = {}
    for row in sub_result.all():
        if row.status == SubmissionStatus.approved:
            approved_map[row.department_id] = int(row.total)
        elif row.status == SubmissionStatus.pending:
            pending_map[row.department_id] = int(row.total)

    # 4. Student's rotation records (most recent per department)
    rot_result = await db.execute(
        select(StudentRotation)
        .where(StudentRotation.student_id == user.id)
        .order_by(StudentRotation.started_at.desc())
    )
    all_rotations = rot_result.scalars().all()
    rotation_by_dept: dict[UUID, StudentRotation] = {}
    for rot in all_rotations:
        if rot.department_id not in rotation_by_dept:
            rotation_by_dept[rot.department_id] = rot

    # 5. Current department
    current_dept_id = next(
        (r.department_id for r in all_rotations if r.is_current), None
    )

    # 6. Build entries
    entries: list[DepartmentTrackerEntry] = []
    show_warning = False

    for dept in departments:
        required = dept_required.get(dept.id, 0)
        if required == 0:
            continue

        approved = approved_map.get(dept.id, 0)
        pending = pending_map.get(dept.id, 0)
        case_pct = min((approved / required) * 100, 100.0) if required > 0 else 0.0

        if case_pct < 40:
            color = "red"
        elif case_pct < 60:
            color = "yellow"
        else:
            color = "green"

        rot = rotation_by_dept.get(dept.id)
        days_active = 0
        time_pct = 0.0
        if rot:
            elapsed = max(0, int((now - rot.started_at).total_seconds() // 86400))
            days_active = rot.days_offset + elapsed
            time_pct = (
                min((days_active / dept.rotation_duration_days) * 100, 100.0)
                if dept.rotation_duration_days > 0
                else 0.0
            )

        is_current = dept.id == current_dept_id

        if is_current and time_pct >= 50 and case_pct < 60:
            show_warning = True

        entries.append(
            DepartmentTrackerEntry(
                department_id=dept.id,
                department_name=dept.name,
                is_current=is_current,
                total_required=required,
                total_completed=approved,
                total_pending=pending,
                case_completion_percentage=round(case_pct, 1),
                case_status_color=color,
                rotation_duration_days=dept.rotation_duration_days,
                days_active=days_active,
                time_completion_percentage=round(time_pct, 1),
                started_at=rot.started_at if rot else None,
                rotation_id=rot.id if rot else None,
            )
        )

    entries.sort(key=lambda e: (0 if e.is_current else 1, e.department_name))

    return DepartmentTrackerResponse(
        current_department_id=current_dept_id,
        entries=entries,
        show_warning=show_warning,
    )
