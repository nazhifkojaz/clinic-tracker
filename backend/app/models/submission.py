from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.department import Department, TaskCategory
    from app.models.user import User


class SubmissionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class CaseSubmission(Base):
    __tablename__ = "case_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    proof_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status", create_constraint=True),
        nullable=False,
        server_default=text("'pending'"),
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_submissions_student_status", "student_id", "status"),
        Index("ix_submissions_dept_status", "department_id", "status"),
        Index("ix_submissions_category_student", "task_category_id", "student_id"),
    )

    # Relationships
    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    department: Mapped["Department"] = relationship()
    task_category: Mapped["TaskCategory"] = relationship()
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by])
