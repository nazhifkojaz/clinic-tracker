import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.pending_profile_change import PendingChangeStatus
from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=200)
    institutional_id: str | None = Field(None, max_length=50)
    department_id: uuid.UUID | None = None
    role: UserRole


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(None, max_length=200)
    institutional_id: str | None = Field(None, max_length=50)
    department_id: uuid.UUID | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8, max_length=100)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    institutional_id: str | None
    department_id: uuid.UUID | None
    role: UserRole
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=200)
    role: Literal[UserRole.student, UserRole.supervisor, UserRole.admin]
    institutional_id: str = Field(..., min_length=1, max_length=50)
    department_id: uuid.UUID | None = None
    invite_code: str | None = Field(None, description="Required when role is admin")

    @model_validator(mode="after")
    def _validate_admin_invite_code(self) -> "UserRegisterRequest":
        if self.role == UserRole.admin and not self.invite_code:
            raise ValueError("invite_code is required when role is admin")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=200)
    institutional_id: str | None = Field(None, min_length=1, max_length=50)
    department_id: uuid.UUID | None = None


class PendingChangeResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    field_name: str
    old_value: str | None
    new_value: str | None
    status: PendingChangeStatus
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PendingChangeWithUserResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    user_email: str
    field_name: str
    old_value: str | None
    new_value: str | None
    status: PendingChangeStatus
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
