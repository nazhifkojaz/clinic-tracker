import enum
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    create_email_verification_token,
    hash_password,
    verify_password,
)
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
from app.utils.email import send_verification_email

router = APIRouter(prefix="/api/users", tags=["users"])
logger = logging.getLogger(__name__)


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


STUDENT_REQUESTABLE_FIELDS = {
    "full_name",
    "institutional_id",
    "email",
    "department_id",
    "supervisor_id",
}
SUPERVISOR_REQUESTABLE_FIELDS = {
    "full_name",
    "institutional_id",
    "department_id",
    "remove_student_id",
}


async def _resolve_department_name(db: AsyncSession, dept_id: uuid.UUID | None) -> str:
    if dept_id is None:
        return "None"
    dept = await db.get(Department, dept_id)
    return dept.name if dept else str(dept_id)


async def _resolve_supervisor_name(
    db: AsyncSession, supervisor_id: uuid.UUID | None
) -> str:
    if supervisor_id is None:
        return "None"
    sup = await db.get(User, supervisor_id)
    return sup.full_name if sup else str(supervisor_id)


async def _resolve_student_name(db: AsyncSession, student_id: uuid.UUID | None) -> str:
    if student_id is None:
        return "None"
    stu = await db.get(User, student_id)
    return stu.full_name if stu else str(student_id)


@router.patch("/me/profile", response_model=UserResponse)
async def update_own_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile. Non-admins queue changes for approval."""
    update_data = body.model_dump(exclude_unset=True)
    # Extract reason separately — not a field to track as a pending change
    reason = update_data.pop("reason", None)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No changes provided",
        )

    if user.role == UserRole.admin:
        # Admin changes apply immediately; only allow direct user fields
        admin_fields = {
            k: v
            for k, v in update_data.items()
            if k in {"full_name", "institutional_id", "department_id"}
        }
        for field, value in admin_fields.items():
            setattr(user, field, value)
        try:
            await db.flush()
            await record_audit(
                db,
                user_id=user.id,
                action="self_update",
                table_name="users",
                record_id=user.id,
                new_values=admin_fields,
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

    # --- Non-admin: validate field permissions ---
    allowed = (
        STUDENT_REQUESTABLE_FIELDS
        if user.role == UserRole.student
        else SUPERVISOR_REQUESTABLE_FIELDS
    )
    disallowed = set(update_data.keys()) - allowed
    if disallowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot request changes to: {', '.join(sorted(disallowed))}",
        )

    # --- Field-specific validation ---
    # Students: validate department_id target
    if "department_id" in update_data and user.role == UserRole.student:
        new_dept_id = update_data["department_id"]
        if new_dept_id is not None:
            dept = await db.get(Department, new_dept_id)
            if dept is None or not dept.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected department not found or inactive.",
                )

    # Students: validate supervisor_id target
    if "supervisor_id" in update_data and user.role == UserRole.student:
        sup_id = update_data["supervisor_id"]
        if sup_id is not None:
            sup = await db.get(User, sup_id)
            if sup is None or not sup.is_active or sup.role != UserRole.supervisor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected supervisor not found, inactive, or not a supervisor.",
                )

    # Students/supervisors: validate email uniqueness
    if "email" in update_data:
        new_email = update_data["email"]
        if new_email and new_email != user.email:
            existing = await db.execute(select(User).where(User.email == new_email))
            if existing.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email address already in use by another user.",
                )

    # Supervisors: validate remove_student_id
    if "remove_student_id" in update_data and user.role == UserRole.supervisor:
        student_id = update_data["remove_student_id"]
        if student_id is not None:
            assignment = await db.execute(
                select(SupervisorAssignment).where(
                    SupervisorAssignment.supervisor_id == user.id,
                    SupervisorAssignment.student_id == student_id,
                    SupervisorAssignment.assignment_type == AssignmentType.primary,
                )
            )
            if assignment.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This student is not assigned to you.",
                )

    # --- Check for duplicate pending requests ---
    pending_result = await db.execute(
        select(PendingProfileChange.field_name).where(
            PendingProfileChange.user_id == user.id,
            PendingProfileChange.field_name.in_(update_data.keys()),
            PendingProfileChange.status == PendingChangeStatus.pending,
        )
    )
    already_pending = {row[0] for row in pending_result.all()}
    if already_pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have a pending request for: {', '.join(sorted(already_pending))}. "
            "Please wait for it to be reviewed before submitting a new one.",
        )

    # --- Create PendingProfileChange records ---
    for field, new_value in update_data.items():
        # Resolve old_value to a human-readable string
        if field == "department_id":
            old_value = await _resolve_department_name(db, user.department_id)
        elif field == "supervisor_id":
            # Get student's current academic supervisor
            current_sup = await db.execute(
                select(SupervisorAssignment.supervisor_id).where(
                    SupervisorAssignment.student_id == user.id,
                    SupervisorAssignment.assignment_type == AssignmentType.primary,
                )
            )
            current_sup_id = current_sup.scalar_one_or_none()
            old_value = await _resolve_supervisor_name(db, current_sup_id)
        elif field == "remove_student_id":
            old_value = user.full_name
        elif field == "email":
            old_value = user.email
        else:
            old_value = str(getattr(user, field) or "")

        db.add(
            PendingProfileChange(
                user_id=user.id,
                field_name=field,
                old_value=old_value,
                new_value=str(new_value) if new_value is not None else None,
                reason=reason,
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
                reason=change.reason,
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
        if new_val is not None:
            dept = await db.get(Department, new_val)
            if dept is None or not dept.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Department not found or inactive. Reject this change and ask the user to resubmit.",
                )
        setattr(target_user, change.field_name, new_val)

        if target_user.role == UserRole.supervisor:
            await sync_department_assignment(db, target_user.id, new_val)
        elif target_user.role == UserRole.student:
            from app.api.rotations import perform_department_override

            await perform_department_override(db, target_user.id, new_val, admin.id)

    elif change.field_name == "email":
        new_email = change.new_value
        # Re-check uniqueness at approval time
        existing = await db.execute(
            select(User).where(User.email == new_email, User.id != target_user.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email address is already in use by another user",
            )
        target_user.email = new_email
        target_user.email_verified = False

    elif change.field_name == "supervisor_id":
        new_supervisor_id = uuid.UUID(change.new_value)
        new_supervisor = await db.get(User, new_supervisor_id)
        if (
            not new_supervisor
            or new_supervisor.role != UserRole.supervisor
            or not new_supervisor.is_active
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target supervisor no longer exists or is inactive. Reject this change.",
            )
        # Find and delete existing primary assignment
        existing_assignment = await db.execute(
            select(SupervisorAssignment).where(
                SupervisorAssignment.student_id == target_user.id,
                SupervisorAssignment.assignment_type == AssignmentType.primary,
            )
        )
        old_assignment = existing_assignment.scalar_one_or_none()
        if old_assignment:
            await record_audit(
                db,
                user_id=admin.id,
                action="delete",
                table_name="supervisor_assignments",
                record_id=old_assignment.id,
                old_values={
                    "supervisor_id": str(old_assignment.supervisor_id),
                    "student_id": str(target_user.id),
                    "assignment_type": "primary",
                },
                new_values=None,
            )
            await db.delete(old_assignment)
            await db.flush()

        new_assignment = SupervisorAssignment(
            supervisor_id=new_supervisor_id,
            student_id=target_user.id,
            assignment_type=AssignmentType.primary,
        )
        db.add(new_assignment)
        await db.flush()
        await record_audit(
            db,
            user_id=admin.id,
            action="create",
            table_name="supervisor_assignments",
            record_id=new_assignment.id,
            old_values=None,
            new_values={
                "supervisor_id": str(new_supervisor_id),
                "student_id": str(target_user.id),
                "assignment_type": "primary",
            },
        )

    elif change.field_name == "remove_student_id":
        student_id = uuid.UUID(change.new_value)
        assignment_result = await db.execute(
            select(SupervisorAssignment).where(
                SupervisorAssignment.supervisor_id == target_user.id,
                SupervisorAssignment.student_id == student_id,
                SupervisorAssignment.assignment_type == AssignmentType.primary,
            )
        )
        assignment = assignment_result.scalar_one_or_none()
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Primary assignment no longer exists. The student may have already been removed.",
            )
        await record_audit(
            db,
            user_id=admin.id,
            action="delete",
            table_name="supervisor_assignments",
            record_id=assignment.id,
            old_values={
                "supervisor_id": str(target_user.id),
                "student_id": str(student_id),
                "assignment_type": "primary",
            },
            new_values=None,
        )
        await db.delete(assignment)

    else:
        # Default: simple field assignment (full_name, institutional_id)
        setattr(target_user, change.field_name, change.new_value)

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

    # Post-commit: send verification email for email changes
    if change.field_name == "email" and change.new_value:
        try:
            token = create_email_verification_token(str(target_user.id))
            verification_link = f"{settings.FRONTEND_URL}/#/verify-email?token={token}"
            await send_verification_email(
                to=change.new_value,
                full_name=target_user.full_name,
                verification_link=verification_link,
            )
        except Exception:
            logger.exception(
                "Failed to send verification email after email change approval"
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
