import secrets
import string

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.invite_code import InviteCode, InviteCodeStatus
from app.models.user import User
from app.schemas.invite_code import (
    InviteCodeResponse,
    ValidateInviteCodeRequest,
    ValidateInviteCodeResponse,
)
from app.utils.audit import record_audit

router = APIRouter(prefix="/api/invite-codes", tags=["invite-codes"])


def _generate_code(length: int = 8) -> str:
    """Generate a random alphanumeric code."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("", response_model=InviteCodeResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def generate_code(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new one-time invite code (admin only)."""
    code = _generate_code()

    invite = InviteCode(
        code=code,
        created_by=admin.id,
        status=InviteCodeStatus.active,
    )
    db.add(invite)

    await db.flush()
    await record_audit(
        db,
        user_id=admin.id,
        action="generate_invite_code",
        table_name="invite_codes",
        record_id=invite.id,
        new_values={"code": code},
    )
    await db.commit()
    await db.refresh(invite)

    return invite


@router.get("", response_model=list[InviteCodeResponse])
@limiter.limit("30/minute")
async def list_codes(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all invite codes (admin only)."""
    result = await db.execute(select(InviteCode).order_by(InviteCode.created_at.desc()))
    codes = result.scalars().all()
    return codes


@router.post("/validate", response_model=ValidateInviteCodeResponse)
@limiter.limit("10/minute")
async def validate_code(
    request: Request,
    body: ValidateInviteCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate an invite code without authentication.

    Used by the registration page to check if a code is valid.
    Does NOT consume the code — that happens during registration.
    """
    result = await db.execute(
        select(InviteCode).where(
            InviteCode.code == body.code,
            InviteCode.status == InviteCodeStatus.active,
        )
    )
    invite = result.scalar_one_or_none()

    if invite is None:
        return ValidateInviteCodeResponse(valid=False)

    return ValidateInviteCodeResponse(valid=True, invite_code_id=invite.id)
