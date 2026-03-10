import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# --- Task Category Schemas ---


class TaskCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    required_count: int = Field(..., gt=0)
    description: str | None = None


class TaskCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    required_count: int | None = Field(None, gt=0)
    description: str | None = None
    is_active: bool | None = None


class TaskCategoryResponse(BaseModel):
    id: uuid.UUID
    department_id: uuid.UUID
    name: str
    required_count: int
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Department Schemas ---


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DepartmentWithCategoriesResponse(DepartmentResponse):
    task_categories: list[TaskCategoryResponse] = []
