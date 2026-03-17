"""Add single-column indexes for edge-case query patterns.

Revision ID: 20260317_add_single_col_indexes
Revises: 20260317_add_perf_indexes
Create Date: 2026-03-17

This migration adds single-column indexes for queries that filter on only
one column without a leading column match in the composite indexes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "20260317_add_single_col_indexes"
down_revision: Union[str, None] = "20260317_add_perf_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add single-column indexes for edge-case query patterns."""

    # CaseSubmission.status - queries like "all pending submissions"
    op.create_index(
        "ix_submissions_status",
        "case_submissions",
        ["status"],
    )

    # StudentRotation.is_current - queries for all active rotations
    # Use partial index since we only care about true values
    op.create_index(
        "ix_rotations_is_current",
        "student_rotations",
        ["is_current"],
        postgresql_where=text("is_current = true"),
    )

    # AuditLog.action - security searches like "all DELETE actions"
    op.create_index(
        "ix_audit_logs_action",
        "audit_logs",
        ["action"],
    )

    # Notification.sent_at - time-range queries without sender/recipient filter
    op.create_index(
        "ix_notifications_sent_at",
        "notifications",
        ["sent_at"],
    )


def downgrade() -> None:
    """Remove single-column indexes."""

    op.drop_index("ix_notifications_sent_at", table_name="notifications")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_rotations_is_current", table_name="student_rotations")
    op.drop_index("ix_submissions_status", table_name="case_submissions")
