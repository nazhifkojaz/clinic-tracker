import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.invite_code import InviteCodeStatus


class InviteCodeResponse(BaseModel):
    id: uuid.UUID
    code: str
    created_by: uuid.UUID
    status: InviteCodeStatus
    used_by: uuid.UUID | None = None
    used_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ValidateInviteCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=12)


class ValidateInviteCodeResponse(BaseModel):
    valid: bool
    invite_code_id: uuid.UUID | None = None
