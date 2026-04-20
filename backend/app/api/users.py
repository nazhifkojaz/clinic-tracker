import enum
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.department import Department
from app.models.pending_profile_change import PendingChangeStatus, PendingProfileChange
from app.models.user import User, UserRole
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import (
    ChangePasswordRequest,
    PendingChangeResponse,
    PendingChangeWithUserResponse,
    ProfileUpdateRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.utils.audit import record_audit

router = APIRouter(prefix="/api/users", tags=["users"])


class DeleteMode(str, enum.Enum):
    soft = "soft"
    hard = "hard"


async def sync_department_assignment(
    db: AsyncSession, supervisor_id: uuid.UUID, new_dept_id: uuid.UUID | None
):
    result = await db.execute(
        select(SupervisorAssignment).where(
            SupervisorAssignment.supervisor_id == supervisor_id,
            SupervisorAssignment.assignment_type == AssignmentType.department,
        )
    )
    existing = result.scalar_one_or_none()

    if new_dept_id is not None:
        if existing:
            existing.department_id = new_dept_id
        else:
            db.add(
                SupervisorAssignment(
                    supervisor_id=supervisor_id,
                    department_id=new_dept_id,
                    assignment_type=AssignmentType.department,
                )
            )
    else:
        if existing:
            await db.delete(existing)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return user


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change current user's password. Requires current password confirmation."""
    if not await verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    user.password_hash = await hash_password(body.new_password)
    await db.flush()
    await record_audit(
        db,
        user_id=user.id,
        action="change_password",
        table_name="users",
        record_id=user.id,
    )
    await db.commit()


@router.patch("/me/profile", response_model=UserResponse)
async def update_own_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile. Non-admins queue changes for approval."""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No changes provided",
        )

    if user.role == UserRole.admin:
        for field, value in update_data.items():
            setattr(user, field, value)
        try:
            await db.flush()
            await record_audit(
                db,
                user_id=user.id,
                action="self_update",
                table_name="users",
                record_id=user.id,
                new_values=update_data,
            )
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="institutional_id already in use",
            )
        await db.refresh(user)
        return user

    # Students cannot change department via self-service
    if user.role == UserRole.student and "department_id" in update_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students cannot change their department. Contact an administrator.",
        )

    # Non-admin: queue each changed field as a PendingProfileChange
    for field, new_value in update_data.items():
        old_value = str(getattr(user, field) or "")

        # Replace existing pending change for the same field
        existing_result = await db.execute(
            select(PendingProfileChange).where(
                PendingProfileChange.user_id == user.id,
                PendingProfileChange.field_name == field,
                PendingProfileChange.status == PendingChangeStatus.pending,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.old_value = old_value
            existing.new_value = str(new_value) if new_value is not None else None
        else:
            db.add(
                PendingProfileChange(
                    user_id=user.id,
                    field_name=field,
                    old_value=old_value,
                    new_value=str(new_value) if new_value is not None else None,
                )
            )

    await db.flush()
    await record_audit(
        db,
        user_id=user.id,
        action="request_profile_change",
        table_name="pending_profile_changes",
        record_id=user.id,
        new_values=update_data,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me/pending-changes", response_model=list[PendingChangeResponse])
async def get_my_pending_changes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's pending profile changes (all statuses)."""
    result = await db.execute(
        select(PendingProfileChange)
        .where(PendingProfileChange.user_id == user.id)
        .order_by(PendingProfileChange.created_at.desc())
    )
    return result.scalars().all()


@router.get(
    "/pending-changes", response_model=PaginatedResponse[PendingChangeWithUserResponse]
)
async def list_pending_changes(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    status_filter: PendingChangeStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all pending profile changes (admin only)."""
    # Count query (no join needed for counting)
    count_base = select(PendingProfileChange)
    if status_filter is not None:
        count_base = count_base.where(PendingProfileChange.status == status_filter)
    count_subquery = count_base.subquery()
    count_query = select(func.count()).select_from(count_subquery)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Data query with join to avoid N+1
    query = select(PendingProfileChange, User.full_name, User.email).join(
        User, PendingProfileChange.user_id == User.id, isouter=True
    )
    if status_filter is not None:
        query = query.where(PendingProfileChange.status == status_filter)
    query = query.order_by(PendingProfileChange.created_at.desc())
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()

    items: list[PendingChangeWithUserResponse] = []
    for row in rows:
        change = row[0]
        user_name = row[1] or "Unknown"
        user_email = row[2] or ""
        items.append(
            PendingChangeWithUserResponse(
                id=change.id,
                user_id=change.user_id,
                user_name=user_name,
                user_email=user_email,
                field_name=change.field_name,
                old_value=change.old_value,
                new_value=change.new_value,
                status=change.status,
                reviewed_by=change.reviewed_by,
                reviewed_at=change.reviewed_at,
                created_at=change.created_at,
            )
        )

    return PaginatedResponse.create(items, total, limit, offset)


@router.post(
    "/pending-changes/{change_id}/approve", status_code=status.HTTP_204_NO_CONTENT
)
async def approve_pending_change(
    change_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending profile change and apply it to the user."""
    result = await db.execute(
        select(PendingProfileChange)
        .where(PendingProfileChange.id == change_id)
        .with_for_update()
    )
    change = result.scalar_one_or_none()
    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Change request not found"
        )
    if change.status != PendingChangeStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Change has already been reviewed",
        )

    target_user = await db.get(User, change.user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found"
        )

    # Apply the change
    if change.field_name == "department_id":
        new_val = uuid.UUID(change.new_value) if change.new_value else None
        # Validate department exists and is active
        if new_val is not None:
            dept = await db.get(Department, new_val)
            if dept is None or not dept.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Department not found or inactive. Reject this change and ask the user to resubmit.",
                )
    else:
        new_val = change.new_value
    setattr(target_user, change.field_name, new_val)

    if change.field_name == "department_id" and target_user.role == UserRole.supervisor:
        await sync_department_assignment(db, target_user.id, new_val)

    change.status = PendingChangeStatus.approved
    change.reviewed_by = admin.id
    change.reviewed_at = datetime.now(timezone.utc)

    try:
        await db.flush()
        await record_audit(
            db,
            user_id=admin.id,
            action="approve_profile_change",
            table_name="pending_profile_changes",
            record_id=change.id,
            old_values={"field": change.field_name, "old_value": change.old_value},
            new_values={"field": change.field_name, "new_value": change.new_value},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not apply change: value already in use by another user",
        )


@router.post(
    "/pending-changes/{change_id}/reject", status_code=status.HTTP_204_NO_CONTENT
)
async def reject_pending_change(
    change_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending profile change."""
    result = await db.execute(
        select(PendingProfileChange)
        .where(PendingProfileChange.id == change_id)
        .with_for_update()
    )
    change = result.scalar_one_or_none()
    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Change request not found"
        )
    if change.status != PendingChangeStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Change has already been reviewed",
        )

    change.status = PendingChangeStatus.rejected
    change.reviewed_by = admin.id
    change.reviewed_at = datetime.now(timezone.utc)

    await db.flush()
    await record_audit(
        db,
        user_id=admin.id,
        action="reject_profile_change",
        table_name="pending_profile_changes",
        record_id=change.id,
        old_values={"field": change.field_name, "old_value": change.old_value},
        new_values={"field": change.field_name, "status": "rejected"},
    )
    await db.commit()


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
        password_hash=await hash_password(body.password),
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
        update_data["password_hash"] = await hash_password(update_data.pop("password"))

    original_role = user.role
    for field, value in update_data.items():
        setattr(user, field, value)

    role_changed = "role" in update_data and original_role != user.role
    if (
        "department_id" in update_data or role_changed
    ) and user.role == UserRole.supervisor:
        await sync_department_assignment(db, user.id, user.department_id)

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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    mode: DeleteMode = Query(DeleteMode.soft),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user (admin only). Soft = deactivate. Hard = anonymize."""
    try:
        target_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    if admin.id == target_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    result = await db.execute(select(User).where(User.id == target_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check if user is already hard-deleted (anonymized)
    if user.email.startswith("deleted_") and user.email.endswith("@deleted"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has already been permanently deleted",
        )

    # Auto-reject any pending profile changes for this user
    await db.execute(
        sa_update(PendingProfileChange)
        .where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
        .values(
            status=PendingChangeStatus.rejected,
            reviewed_by=admin.id,
            reviewed_at=datetime.now(timezone.utc),
        )
    )

    if mode == DeleteMode.soft:
        old_values = {"is_active": user.is_active}
        user.is_active = False
        await db.flush()
        await record_audit(
            db,
            user_id=admin.id,
            action="soft_delete",
            table_name="users",
            record_id=user.id,
            old_values=old_values,
            new_values={"is_active": False},
        )
        await db.commit()

    elif mode == DeleteMode.hard:
        old_values = {
            "email": user.email,
            "full_name": user.full_name,
            "institutional_id": user.institutional_id,
        }
        user.email = f"deleted_{user.id}@deleted"
        user.full_name = (
            f"{user.full_name} (Deleted User)" if user.full_name else "Deleted User"
        )
        user.institutional_id = None
        user.password_hash = await hash_password(str(uuid.uuid4()))
        user.is_active = False
        user.email_verified = False
        await db.flush()
        await record_audit(
            db,
            user_id=admin.id,
            action="hard_delete",
            table_name="users",
            record_id=user.id,
            old_values=old_values,
            new_values={
                "email": user.email,
                "full_name": user.full_name,
                "note": "PII anonymized",
            },
        )
        await db.commit()
