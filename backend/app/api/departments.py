from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user, require_admin
from app.core.cache import categories_cache, departments_cache
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
    db: AsyncSession = Depends(get_db),
):
    """List all active departments with category counts."""
    result = await db.execute(
        select(
            Department,
            func.count(TaskCategory.id)
            .filter(TaskCategory.is_active.is_(True))
            .label("category_count"),
        )
        .outerjoin(TaskCategory, TaskCategory.department_id == Department.id)
        .where(Department.is_active.is_(True))
        .group_by(Department.id)
        .order_by(Department.name)
    )
    rows = result.all()

    return [
        DepartmentResponse(
            id=dept.id,
            name=dept.name,
            description=dept.description,
            is_active=dept.is_active,
            rotation_duration_days=dept.rotation_duration_days,
            category_count=count,
            created_at=dept.created_at,
            updated_at=dept.updated_at,
        )
        for dept, count in rows
    ]


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

    # Compute active category count
    count_result = await db.execute(
        select(func.count(TaskCategory.id)).where(
            TaskCategory.department_id == department_id,
            TaskCategory.is_active.is_(True),
        )
    )
    category_count = count_result.scalar() or 0

    # Filter to active categories only for consistency with category_count
    active_categories = [c for c in department.task_categories if c.is_active]

    return DepartmentWithCategoriesResponse(
        id=department.id,
        name=department.name,
        description=department.description,
        is_active=department.is_active,
        rotation_duration_days=department.rotation_duration_days,
        category_count=category_count,
        created_at=department.created_at,
        updated_at=department.updated_at,
        task_categories=active_categories,
    )


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
        await db.flush()  # Get server-generated UUID before audit
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
        await db.commit()
        await db.refresh(department)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Department with this name already exists"
        )

    # Invalidate cache
    await departments_cache.invalidate("all_active_departments")

    # New department has 0 categories
    return DepartmentResponse(
        id=department.id,
        name=department.name,
        description=department.description,
        is_active=department.is_active,
        rotation_duration_days=department.rotation_duration_days,
        category_count=0,
        created_at=department.created_at,
        updated_at=department.updated_at,
    )


@router.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: UUID,
    body: DepartmentUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a department. Admin only."""
    result = await db.execute(select(Department).where(Department.id == department_id))
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

    # New values for audit
    new_values = {
        "name": department.name,
        "description": department.description,
        "is_active": department.is_active,
    }

    try:
        await db.flush()  # Ensure changes are staged
        await record_audit(
            db,
            user_id=admin.id,
            action="update",
            table_name="departments",
            record_id=department.id,
            old_values=old_values,
            new_values=new_values,
        )
        await db.commit()
        await db.refresh(department)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Department with this name already exists"
        )

    # Invalidate cache
    await departments_cache.invalidate("all_active_departments")

    # Compute active category count
    count_result = await db.execute(
        select(func.count(TaskCategory.id)).where(
            TaskCategory.department_id == department_id,
            TaskCategory.is_active.is_(True),
        )
    )
    category_count = count_result.scalar() or 0

    return DepartmentResponse(
        id=department.id,
        name=department.name,
        description=department.description,
        is_active=department.is_active,
        rotation_duration_days=department.rotation_duration_days,
        category_count=category_count,
        created_at=department.created_at,
        updated_at=department.updated_at,
    )


# --- Task Category Endpoints ---


@router.get("/{department_id}/categories", response_model=list[TaskCategoryResponse])
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
    dept = await db.execute(select(Department).where(Department.id == department_id))
    if not dept.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Department not found")

    category = TaskCategory(department_id=department_id, **body.model_dump())
    db.add(category)

    try:
        await db.flush()  # Get server-generated UUID before audit
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
        await db.commit()
        await db.refresh(category)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Task category with this name already exists"
        )

    # Invalidate cache
    await categories_cache.invalidate("all_active_categories")
    await departments_cache.invalidate("all_active_departments")

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

    # New values for audit
    new_values = {
        "name": category.name,
        "required_count": category.required_count,
        "description": category.description,
        "is_active": category.is_active,
    }

    await db.flush()  # Ensure changes are staged
    await record_audit(
        db,
        user_id=admin.id,
        action="update",
        table_name="task_categories",
        record_id=category.id,
        old_values=old_values,
        new_values=new_values,
    )
    await db.commit()
    await db.refresh(category)

    # Invalidate cache
    await categories_cache.invalidate("all_active_categories")
    await departments_cache.invalidate("all_active_departments")

    return category
