import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.submission import SubmissionStatus


class SubmissionCreate(BaseModel):
    department_id: uuid.UUID
    task_category_id: uuid.UUID
    case_count: int = Field(..., gt=0)
    proof_url: str = Field(..., min_length=1, max_length=1024)
    notes: str | None = None


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    department_id: uuid.UUID
    task_category_id: uuid.UUID
    case_count: int
    proof_url: str
    notes: str | None
    status: SubmissionStatus
    reviewed_by: uuid.UUID | None
    review_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubmissionWithDetailsResponse(SubmissionResponse):
    student_name: str
    department_name: str
    task_category_name: str
    reviewer_name: str | None = None


class SubmissionReview(BaseModel):
    status: SubmissionStatus = Field(
        ..., description="Must be 'approved' or 'rejected'"
    )
    review_notes: str | None = None


class UploadUrlRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., pattern=r"^image/(jpeg|png|gif|webp)$")


class UploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
