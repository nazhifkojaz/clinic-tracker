"""Notification Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


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
