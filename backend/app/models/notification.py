"""Notification model and pre-built email templates."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Notification(Base):
    """Email notification sent by a supervisor to a student."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )

    # Relationships
    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])


# Pre-built notification templates
# These are constants, not database records
NOTIFICATION_TEMPLATES = {
    "behind_department": {
        "subject": "Action Required: You are behind on {department} cases",
        "message": (
            "Dear {student_name},\n\n"
            "Our records show that you are behind on your required cases "
            "in the {department} department. You have completed {completed} "
            "out of {required} required cases.\n\n"
            "Please prioritize completing your remaining cases. "
            "Reach out if you need assistance.\n\n"
            "Best regards,\n{supervisor_name}"
        ),
    },
    "at_risk_overall": {
        "subject": "Progress Alert: You are at risk of not meeting requirements",
        "message": (
            "Dear {student_name},\n\n"
            "Your overall clinical progress is currently at {progress}%, "
            "which places you in the at-risk category. "
            "Please review your remaining requirements and take action.\n\n"
            "Best regards,\n{supervisor_name}"
        ),
    },
    "general_reminder": {
        "subject": "Reminder from your supervisor",
        "message": (
            "Dear {student_name},\n\n"
            "{custom_message}\n\n"
            "Best regards,\n{supervisor_name}"
        ),
    },
}
