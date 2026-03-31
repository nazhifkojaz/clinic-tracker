import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

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
    role: Literal[UserRole.student, UserRole.supervisor]  # admin cannot self-register
    institutional_id: str = Field(..., min_length=1, max_length=50)
    department_id: uuid.UUID | None = None
