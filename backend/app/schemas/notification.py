"""Notification Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NotificationSend(BaseModel):
    """Request schema for sending a notification."""

    recipient_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=20)
    subject: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=5000)
    template_key: str | None = None
    template_vars: dict[str, str] | None = None


class NotificationResponse(BaseModel):
    """Response schema for a notification record."""

    id: uuid.UUID
    sender_id: uuid.UUID
    sender_name: str
    recipient_id: uuid.UUID
    recipient_name: str
    subject: str
    message: str
    sent_at: datetime

    model_config = {"from_attributes": True}


class NotificationTemplateResponse(BaseModel):
    """Response schema for a notification template."""

    key: str
    subject: str
    message: str
