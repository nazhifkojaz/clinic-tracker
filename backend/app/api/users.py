from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.utils.audit import record_audit

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return user


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    role: str | None = Query(None, description="Filter by role"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    pending_approval: bool | None = Query(
        None,
        description="Filter users awaiting admin approval (email verified, not active)",
    ),
    search: str | None = Query(
        None, description="Search by name, email, or institutional ID"
    ),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
):
    """List all users with pagination and filters (admin only)."""
    query = select(User)

    if pending_approval is True:
        query = query.where(User.email_verified.is_(True), User.is_active.is_(False))
    else:
        if role:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)

    if search:
        query = query.where(
            (User.full_name.ilike(f"%{search}%"))
            | (User.email.ilike(f"%{search}%"))
            | (User.institutional_id.ilike(f"%{search}%"))
        )

    count_subquery = query.subquery()
    count_query = select(func.count()).select_from(count_subquery)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(User.created_at.desc())
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)

    users = result.scalars().all()

    return PaginatedResponse.create(users, total, limit, offset)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (admin only). Created users are immediately active."""
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        institutional_id=body.institutional_id,
        department_id=body.department_id,
        role=body.role,
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    try:
        await db.flush()
        await record_audit(
            db,
            user_id=admin.id,
            action="create",
            table_name="users",
            record_id=user.id,
            new_values={
                "email": user.email,
                "full_name": user.full_name,
                "institutional_id": user.institutional_id,
                "role": user.role.value,
            },
        )
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email or institutional ID already exists",
        )

    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    old_values = {
        "email": user.email,
        "full_name": user.full_name,
        "institutional_id": user.institutional_id,
        "role": user.role.value if user.role else None,
        "is_active": user.is_active,
    }

    update_data = body.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    new_values = {
        "email": user.email,
        "full_name": user.full_name,
        "institutional_id": user.institutional_id,
        "role": user.role.value if user.role else None,
        "is_active": user.is_active,
    }

    try:
        await db.flush()
        await record_audit(
            db,
            user_id=admin.id,
            action="update",
            table_name="users",
            record_id=user.id,
            old_values=old_values,
            new_values=new_values,
        )
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email or institutional ID already exists",
        )

    return user
