from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.models.department import Department, TaskCategory
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    DepartmentWithCategoriesResponse,
    TaskCategoryCreate,
    TaskCategoryResponse,
    TaskCategoryUpdate,
)
from app.utils.audit import record_audit

router = APIRouter(prefix="/api/departments", tags=["departments"])


# --- Department Endpoints ---

@router.get("", response_model=list[DepartmentResponse])
async def list_departments(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active departments. Available to all authenticated users."""
    result = await db.execute(
        select(Department)
        .where(Department.is_active.is_(True))
        .order_by(Department.name)
    )
    return result.scalars().all()


@router.get("/{department_id}", response_model=DepartmentWithCategoriesResponse)
async def get_department(
    department_id: UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a department with its task categories."""
    result = await db.execute(
        select(Department)
        .options(selectinload(Department.task_categories))
        .where(Department.id == department_id)
    )
    department = result.scalar_one_or_none()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new department. Admin only."""
    department = Department(**body.model_dump())
    db.add(department)
    try:
        await db.commit()
        await db.refresh(department)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Department with this name already exists"
        )

    # Audit log
    await record_audit(
        db,
        user_id=admin.id,
        action="create",
        table_name="departments",
        record_id=department.id,
        new_values={
            "name": department.name,
            "description": department.description,
        },
    )

    return department


@router.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: UUID,
    body: DepartmentUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a department. Admin only."""
    result = await db.execute(
        select(Department).where(Department.id == department_id)
    )
    department = result.scalar_one_or_none()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    # Store old values for audit
    old_values = {
        "name": department.name,
        "description": department.description,
        "is_active": department.is_active,
    }

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(department, field, value)

    try:
        await db.commit()
        await db.refresh(department)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Department with this name already exists"
        )

    # Audit log
    new_values = {
        "name": department.name,
        "description": department.description,
        "is_active": department.is_active,
    }
    await record_audit(
        db,
        user_id=admin.id,
        action="update",
        table_name="departments",
        record_id=department.id,
        old_values=old_values,
        new_values=new_values,
    )

    return department


# --- Task Category Endpoints ---

@router.get(
    "/{department_id}/categories", response_model=list[TaskCategoryResponse]
)
async def list_task_categories(
    department_id: UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active task categories for a department."""
    result = await db.execute(
        select(TaskCategory)
        .where(
            TaskCategory.department_id == department_id,
            TaskCategory.is_active.is_(True),
        )
        .order_by(TaskCategory.name)
    )
    return result.scalars().all()


@router.post(
    "/{department_id}/categories",
    response_model=TaskCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_category(
    department_id: UUID,
    body: TaskCategoryCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a task category in a department. Admin only."""
    # Verify department exists
    dept = await db.execute(
        select(Department).where(Department.id == department_id)
    )
    if not dept.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Department not found")

    category = TaskCategory(department_id=department_id, **body.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)

    # Audit log
    await record_audit(
        db,
        user_id=admin.id,
        action="create",
        table_name="task_categories",
        record_id=category.id,
        new_values={
            "department_id": str(department_id),
            "name": category.name,
            "required_count": category.required_count,
        },
    )

    return category


@router.patch(
    "/{department_id}/categories/{category_id}",
    response_model=TaskCategoryResponse,
)
async def update_task_category(
    department_id: UUID,
    category_id: UUID,
    body: TaskCategoryUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a task category. Admin only."""
    result = await db.execute(
        select(TaskCategory).where(
            TaskCategory.id == category_id,
            TaskCategory.department_id == department_id,
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Task category not found")

    # Store old values for audit
    old_values = {
        "name": category.name,
        "required_count": category.required_count,
        "description": category.description,
        "is_active": category.is_active,
    }

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    await db.commit()
    await db.refresh(category)

    # Audit log
    new_values = {
        "name": category.name,
        "required_count": category.required_count,
        "description": category.description,
        "is_active": category.is_active,
    }
    await record_audit(
        db,
        user_id=admin.id,
        action="update",
        table_name="task_categories",
        record_id=category.id,
        old_values=old_values,
        new_values=new_values,
    )

    return category
