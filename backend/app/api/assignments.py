from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, union
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.dependencies import get_current_user, require_admin, require_supervisor
from app.core.database import get_db
from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.department import Department
from app.models.rotation import StudentRotation
from app.models.user import User, UserRole
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentWithDetailsResponse,
)
from app.utils.audit import record_audit

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


@router.get("", response_model=list[AssignmentWithDetailsResponse])
async def list_assignments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    assignment_type: AssignmentType | None = Query(None),
    supervisor_id: UUID | None = Query(None),
    student_id: UUID | None = Query(None),
):
    """List assignments. Admins see all; supervisors see their own."""
    # Build query with joined user names
    supervisor_alias = User.__table__.alias("sup")
    student_alias = User.__table__.alias("stu")

    query = (
        select(
            SupervisorAssignment,
            supervisor_alias.c.full_name.label("supervisor_name"),
            student_alias.c.full_name.label("student_name"),
            Department.name.label("department_name"),
        )
        .join(supervisor_alias, SupervisorAssignment.supervisor_id == supervisor_alias.c.id)
        .outerjoin(student_alias, SupervisorAssignment.student_id == student_alias.c.id)
        .outerjoin(Department, SupervisorAssignment.department_id == Department.id)
    )

    # Role-based filtering
    if user.role == UserRole.supervisor:
        query = query.where(SupervisorAssignment.supervisor_id == user.id)
    elif user.role == UserRole.student:
        raise HTTPException(status_code=403, detail="Students cannot view assignments")

    # Optional filters
    if assignment_type:
        query = query.where(SupervisorAssignment.assignment_type == assignment_type)
    if supervisor_id:
        query = query.where(SupervisorAssignment.supervisor_id == supervisor_id)
    if student_id:
        query = query.where(SupervisorAssignment.student_id == student_id)

    query = query.order_by(SupervisorAssignment.created_at.desc())
    result = await db.execute(query)

    assignments = []
    for row in result.all():
        assignment = row[0]
        assignments.append(
            AssignmentWithDetailsResponse(
                id=assignment.id,
                supervisor_id=assignment.supervisor_id,
                student_id=assignment.student_id,
                assignment_type=assignment.assignment_type,
                department_id=assignment.department_id,
                created_at=assignment.created_at,
                supervisor_name=row.supervisor_name,
                student_name=row.student_name,
                department_name=row.department_name,
            )
        )
    return assignments


@router.post(
    "", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED
)
async def create_assignment(
    body: AssignmentCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a supervisor assignment. Admin only."""
    # Validate assignment_type + field consistency
    if body.assignment_type == AssignmentType.primary:
        if body.student_id is None:
            raise HTTPException(
                status_code=400,
                detail="Primary assignments must have a student_id",
            )
        if body.department_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Primary assignments must not have a department_id",
            )
    elif body.assignment_type == AssignmentType.department:
        if body.department_id is None:
            raise HTTPException(
                status_code=400,
                detail="Department assignments must have a department_id",
            )
        if body.student_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Department assignments must not have a student_id",
            )

    # Validate supervisor exists and has supervisor/admin role
    sup_result = await db.execute(
        select(User).where(User.id == body.supervisor_id, User.is_active.is_(True))
    )
    supervisor = sup_result.scalar_one_or_none()
    if not supervisor:
        raise HTTPException(status_code=404, detail="Supervisor not found or inactive")
    if supervisor.role not in (UserRole.supervisor, UserRole.admin):
        raise HTTPException(
            status_code=400, detail="Assigned user is not a supervisor or admin"
        )

    # Validate student exists and has student role (only for primary assignments)
    if body.student_id:
        stu_result = await db.execute(
            select(User).where(User.id == body.student_id, User.is_active.is_(True))
        )
        student = stu_result.scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found or inactive")
        if student.role != UserRole.student:
            raise HTTPException(status_code=400, detail="Assigned user is not a student")

    # Validate department exists (if department-type)
    if body.department_id:
        dept_result = await db.execute(
            select(Department).where(
                Department.id == body.department_id,
                Department.is_active.is_(True),
            )
        )
        if not dept_result.scalar_one_or_none():
            raise HTTPException(
                status_code=404, detail="Department not found or inactive"
            )

    assignment = SupervisorAssignment(**body.model_dump())
    db.add(assignment)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="This assignment already exists"
        )

    await db.refresh(assignment)

    # Audit log
    await record_audit(
        db,
        user_id=admin.id,
        action="create",
        table_name="supervisor_assignments",
        record_id=assignment.id,
        new_values={
            "supervisor_id": str(assignment.supervisor_id),
            "student_id": str(assignment.student_id) if assignment.student_id else None,
            "assignment_type": assignment.assignment_type.value,
            "department_id": str(assignment.department_id) if assignment.department_id else None,
        },
    )

    return assignment


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove a supervisor assignment. Admin only."""
    result = await db.execute(
        select(SupervisorAssignment).where(SupervisorAssignment.id == assignment_id)
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Store old values for audit
    old_values = {
        "supervisor_id": str(assignment.supervisor_id),
        "student_id": str(assignment.student_id) if assignment.student_id else None,
        "assignment_type": assignment.assignment_type.value,
        "department_id": str(assignment.department_id) if assignment.department_id else None,
    }

    await db.delete(assignment)
    await db.commit()

    # Audit log
    await record_audit(
        db,
        user_id=admin.id,
        action="delete",
        table_name="supervisor_assignments",
        record_id=assignment_id,
        old_values=old_values,
    )


@router.get("/my-students", response_model=list[dict])
async def get_my_students(
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Get the supervisor's assigned students with assignment details.

    Returns:
    - Students with primary assignments to this supervisor
    - Students currently rotating in departments this supervisor oversees
    """
    # Use aliased for proper ORM joins
    student_user = aliased(User)

    # Get departments this supervisor oversees (department-type assignments)
    supervised_depts_result = await db.execute(
        select(SupervisorAssignment.department_id).where(
            SupervisorAssignment.supervisor_id == user.id,
            SupervisorAssignment.assignment_type == AssignmentType.department,
        )
    )
    supervised_dept_ids = [row[0] for row in supervised_depts_result.all()]

    # Query 1: Primary assignment students (direct assignment)
    primary_query = (
        select(
            SupervisorAssignment.id.label("assignment_id"),
            student_user.id.label("student_id"),
            student_user.full_name.label("student_name"),
            student_user.email.label("student_email"),
            student_user.student_id.label("student_code"),
            StudentRotation.department_id.label("dept_id"),
            Department.name.label("dept_name"),
            SupervisorAssignment.assignment_type.label("assignment_type"),
        )
        .join(student_user, SupervisorAssignment.student_id == student_user.id)
        .outerjoin(StudentRotation, (StudentRotation.student_id == student_user.id) & StudentRotation.is_current.is_(True))
        .outerjoin(Department, StudentRotation.department_id == Department.id)
        .where(
            SupervisorAssignment.supervisor_id == user.id,
            SupervisorAssignment.assignment_type == AssignmentType.primary,
        )
    )

    # Query 2: Students currently rotating in supervised departments
    dept_students_query = None
    if supervised_dept_ids:
        dept_students_query = (
            select(
                SupervisorAssignment.id.label("assignment_id"),
                student_user.id.label("student_id"),
                student_user.full_name.label("student_name"),
                student_user.email.label("student_email"),
                student_user.student_id.label("student_code"),
                StudentRotation.department_id.label("dept_id"),
                Department.name.label("dept_name"),
                SupervisorAssignment.assignment_type.label("assignment_type"),
            )
            .join(SupervisorAssignment, SupervisorAssignment.department_id == StudentRotation.department_id)
            .join(student_user, StudentRotation.student_id == student_user.id)
            .join(Department, StudentRotation.department_id == Department.id)
            .where(
                SupervisorAssignment.supervisor_id == user.id,
                SupervisorAssignment.assignment_type == AssignmentType.department,
                StudentRotation.is_current.is_(True),
                StudentRotation.department_id.in_(supervised_dept_ids),
            )
        )

    # Combine queries using subquery for proper ordering
    if dept_students_query is not None:
        combined = union(primary_query, dept_students_query)
        combined_subquery = combined.subquery()
        final_query = (
            select(combined_subquery)
            .order_by(combined_subquery.c.student_name)
        )
    else:
        final_query = primary_query.order_by(student_user.full_name)

    result = await db.execute(final_query)
    students = []
    seen_student_depts = set()

    for row in result:
        student_dept_key = (str(row.student_id), str(row.dept_id) if row.dept_id else "primary")
        if student_dept_key in seen_student_depts:
            continue
        seen_student_depts.add(student_dept_key)

        students.append({
            "assignment_id": str(row.assignment_id),
            "student_id": str(row.student_id),
            "student_name": row.student_name,
            "student_email": row.student_email,
            "student_code": row.student_code,
            "assignment_type": row.assignment_type,
            "department_id": str(row.dept_id) if row.dept_id else None,
            "department_name": row.dept_name,
        })
    return students
