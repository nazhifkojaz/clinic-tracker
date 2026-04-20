from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_email_verification_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_email_verification_token,
    verify_password,
)
from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.department import Department
from app.models.invite_code import InviteCode, InviteCodeStatus
from app.models.user import UserRole, User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
)
from app.schemas.user import UserRegisterRequest
from app.utils.audit import record_audit
from app.utils.email import send_verification_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return access + refresh tokens.

    Accepts either email or institutional_id as the identifier.
    """
    result = await db.execute(
        select(User).where(
            (User.email == body.identifier) | (User.institutional_id == body.identifier)
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not await verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Distinguish between "email not verified" and "pending admin approval"
    if not user.is_active:
        if not user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email before logging in.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending admin approval.",
        )

    return TokenResponse(
        access_token=create_access_token(subject=str(user.id), role=user.role.value),
        refresh_token=create_refresh_token(subject=str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh_token(
    request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)
):
    """Exchange refresh token for new access + refresh tokens."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return TokenResponse(
        access_token=create_access_token(subject=str(user.id), role=user.role.value),
        refresh_token=create_refresh_token(subject=str(user.id)),
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def register(
    request: Request, body: UserRegisterRequest, db: AsyncSession = Depends(get_db)
):
    """Self-register a new account. Requires email verification and admin approval."""
    # Validate invite code when registering as admin
    invite: InviteCode | None = None
    if body.role == UserRole.admin:
        if not body.invite_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invite code is required for admin registration",
            )
        result = await db.execute(
            select(InviteCode)
            .where(
                InviteCode.code == body.invite_code,
                InviteCode.status == InviteCodeStatus.active,
            )
            .with_for_update()
        )
        invite = result.scalar_one_or_none()
        if invite is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired invite code",
            )

    # Validate department exists if provided
    if body.department_id is not None:
        dept = await db.get(Department, body.department_id)
        if not dept or not dept.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found or inactive",
            )

    user = User(
        email=body.email,
        password_hash=await hash_password(body.password),
        full_name=body.full_name,
        institutional_id=body.institutional_id,
        department_id=body.department_id,
        role=body.role,
        is_active=False,
        email_verified=False,
    )
    db.add(user)
    try:
        await db.flush()

        if user.role == UserRole.supervisor and user.department_id is not None:
            db.add(SupervisorAssignment(
                supervisor_id=user.id,
                department_id=user.department_id,
                assignment_type=AssignmentType.department,
            ))
            await db.flush()

        # Consume invite code if this is an admin registration
        if invite is not None:
            invite.status = InviteCodeStatus.used
            invite.used_by = user.id
            invite.used_at = datetime.now(timezone.utc)
            await record_audit(
                db,
                user_id=user.id,
                action="use_invite_code",
                table_name="invite_codes",
                record_id=invite.id,
                new_values={"code": invite.code, "used_by": str(user.id)},
            )

        await record_audit(
            db,
            user_id=user.id,
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

        token = create_email_verification_token(str(user.id))
        verification_link = f"{settings.FRONTEND_URL}/#/verify-email?token={token}"
        await send_verification_email(
            to=user.email,
            full_name=user.full_name,
            verification_link=verification_link,
        )

        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or institutional ID already registered",
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )

    return RegisterResponse(
        message="Registration successful. Please check your email to verify your account."
    )


@router.get("/verify-email")
async def verify_email(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Verify a user's email address using the token sent during registration."""
    try:
        user_id = verify_email_verification_token(token)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.email_verified:
        return {"message": "Email already verified."}

    user.email_verified = True
    await db.commit()

    return {"message": "Email verified. Your account is pending admin approval."}


@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resend email verification link. Always returns 200 to prevent user enumeration."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is not None and not user.email_verified:
        token = create_email_verification_token(str(user.id))
        verification_link = f"{settings.FRONTEND_URL}/#/verify-email?token={token}"
        await send_verification_email(
            to=user.email,
            full_name=user.full_name,
            verification_link=verification_link,
        )

    return {
        "message": "If your email is registered and unverified, a new verification link has been sent."
    }
