import uuid
from datetime import datetime

from pydantic import BaseModel


class RotationCreate(BaseModel):
    department_id: uuid.UUID


class RotationResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    department_id: uuid.UUID
    is_current: bool
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class RotationWithDetailsResponse(RotationResponse):
    department_name: str
    student_name: str
