import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

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

    @model_validator(mode="after")
    def validate_assignment_fields(self) -> "AssignmentCreate":
        """Validate that type-specific required fields are provided."""
        if self.assignment_type == AssignmentType.primary:
            if self.student_id is None:
                raise ValueError("student_id is required for primary assignments")
            if self.department_id is not None:
                raise ValueError("department_id must be null for primary assignments")
        elif self.assignment_type == AssignmentType.department:
            if self.department_id is None:
                raise ValueError("department_id is required for department assignments")
            if self.student_id is not None:
                raise ValueError("student_id must be null for department assignments")
        return self


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


class MyStudentResponse(BaseModel):
    """Response for get_my_students endpoint."""

    assignment_id: str
    student_id: str
    student_name: str
    student_email: str
    student_code: str | None
    assignment_type: str
    department_id: str | None
    department_name: str | None
