"""Audit log Pydantic schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """Response schema for an audit log entry."""

    id: uuid.UUID
    user_id: uuid.UUID | None
    user_name: str | None
    action: str
    table_name: str
    record_id: uuid.UUID
    old_values: dict | None
    new_values: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Response schema for paginated audit log list."""

    items: list[AuditLogResponse]
    total: int
