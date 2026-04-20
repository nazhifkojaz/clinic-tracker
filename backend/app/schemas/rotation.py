import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RotationCreate(BaseModel):
    department_id: uuid.UUID
    days_offset: int = Field(default=0, ge=0)


class DepartmentOverrideRequest(BaseModel):
    department_id: uuid.UUID
    days_offset: int = Field(default=0, ge=0)


class RotationResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    department_id: uuid.UUID
    is_current: bool
    started_at: datetime
    ended_at: datetime | None
    days_offset: int

    model_config = {"from_attributes": True}


class RotationWithDetailsResponse(RotationResponse):
    department_name: str
    student_name: str


class RotationOffsetUpdate(BaseModel):
    days_offset: int = Field(..., ge=0)


class DayAdjustmentRequest(BaseModel):
    total_day: int = Field(..., ge=0)
