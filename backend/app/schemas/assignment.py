import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.assignment import AssignmentType


class AssignmentCreate(BaseModel):
    supervisor_id: uuid.UUID
    student_id: uuid.UUID | None = Field(
        None,
        description="Required when assignment_type is 'primary', must be null for 'department'",
    )
    assignment_type: AssignmentType
    department_id: uuid.UUID | None = Field(
        None,
        description="Required when assignment_type is 'department', must be null for 'primary'",
    )


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    supervisor_id: uuid.UUID
    student_id: uuid.UUID | None
    assignment_type: AssignmentType
    department_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AssignmentWithDetailsResponse(AssignmentResponse):
    supervisor_name: str
    student_name: str | None = None
    department_name: str | None = None
