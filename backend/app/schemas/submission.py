import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.submission import SubmissionStatus


_PROOF_KEY_PATTERN = re.compile(r"^submissions/[a-zA-Z0-9._-]+$")
_PROOF_KEY_ERROR = (
    "proof_key must match pattern: submissions/<filename> "
    "(alphanumeric, dots, dashes, underscores only)"
)


def _validate_proof_key(v: str | None) -> str | None:
    if v is not None and not _PROOF_KEY_PATTERN.match(v):
        raise ValueError(_PROOF_KEY_ERROR)
    return v


class SubmissionCreate(BaseModel):
    department_id: uuid.UUID
    target_supervisor_id: uuid.UUID
    task_category_id: uuid.UUID
    case_count: int = Field(..., gt=0)
    proof_key: str = Field(..., min_length=1, max_length=1024)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("proof_key")
    @classmethod
    def validate_proof_key(cls, v: str) -> str:
        return _validate_proof_key(v)  # type: ignore[return-value]


class SubmissionUpdate(BaseModel):
    case_count: int | None = Field(None, gt=0)
    proof_key: str | None = Field(None, min_length=1, max_length=1024)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("proof_key")
    @classmethod
    def validate_proof_key(cls, v: str | None) -> str | None:
        return _validate_proof_key(v)


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
    target_supervisor_id: uuid.UUID | None = None
    target_supervisor: ReviewerInfo | None = None
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
    target_supervisor_id: uuid.UUID | None = None
    target_supervisor: ReviewerInfo | None = None
    reviewed_by: uuid.UUID | None
    reviewer: ReviewerInfo | None
    review_notes: str | None
    can_review: bool = False
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class DeletedSubmissionListResponse(SubmissionListResponse):
    """Submission list entry for the deleted submissions admin page."""

    deleted_by_id: uuid.UUID | None
    deleted_by_name: str | None


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


class AcademicSupervisorResponse(BaseModel):
    """Student's academic (primary) supervisor."""

    supervisor: ReviewerInfo | None = None
