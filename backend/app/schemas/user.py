import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    student_id: str | None = None
    role: UserRole


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    student_id: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None  # Optional password reset


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    student_id: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
