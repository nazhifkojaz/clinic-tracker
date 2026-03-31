import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.submission import SubmissionStatus


class SubmissionCreate(BaseModel):
    department_id: uuid.UUID
    task_category_id: uuid.UUID
    case_count: int = Field(..., gt=0)
    proof_key: str = Field(..., min_length=1, max_length=1024)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("proof_key")
    @classmethod
    def validate_proof_key(cls, v: str) -> str:
        """Validate proof_key follows expected pattern."""
        pattern = r"^submissions/[a-zA-Z0-9._-]+$"
        if not re.match(pattern, v):
            raise ValueError(
                "proof_key must match pattern: submissions/<filename> "
                "(alphanumeric, dots, dashes, underscores only)"
            )
        return v


class StudentInfo(BaseModel):
    """Basic student information for submission responses."""

    id: uuid.UUID
    full_name: str
    student_id: str | None
    email: str


class ReviewerInfo(BaseModel):
    """Basic reviewer information for submission responses."""

    id: uuid.UUID
    full_name: str


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    department_id: uuid.UUID
    task_category_id: uuid.UUID
    case_count: int
    proof_key: str
    notes: str | None
    status: SubmissionStatus
    reviewed_by: uuid.UUID | None
    review_notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = {"from_attributes": True}


class SubmissionListResponse(BaseModel):
    """Response for submission list that includes student info."""

    id: uuid.UUID
    student_id: uuid.UUID
    student: StudentInfo | None
    department_id: uuid.UUID
    task_category_id: uuid.UUID
    case_count: int
    proof_key: str
    notes: str | None
    status: SubmissionStatus
    reviewed_by: uuid.UUID | None
    reviewer: ReviewerInfo | None
    review_notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class DeletedSubmissionListResponse(SubmissionListResponse):
    """Submission list entry for the deleted submissions admin page."""

    deleted_by_id: uuid.UUID | None
    deleted_by_name: str | None


class SubmissionWithDetailsResponse(SubmissionResponse):
    student_name: str
    department_name: str
    task_category_name: str
    reviewer_name: str | None = None


class SubmissionReview(BaseModel):
    status: Literal["approved", "rejected"] = Field(
        ..., description="Must be 'approved' or 'rejected'"
    )
    review_notes: str | None = None


class UploadUrlRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=100)


class UploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
