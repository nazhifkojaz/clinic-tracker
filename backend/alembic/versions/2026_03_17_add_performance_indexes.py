"""Add performance indexes for common query patterns.

Revision ID: 20260317_add_perf_indexes
Revises: 2f4ece55328a
Create Date: 2026-03-17

This migration adds composite indexes to optimize frequently-executed queries
in the dashboard, notifications, and audit log endpoints.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260317_add_perf_indexes"
down_revision: Union[str, None] = "2f4ece55328a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes for common query patterns."""

    # CaseSubmission indexes - dashboard and list queries
    # These optimize the most common query patterns: filtering by student/status
    # and department/status, used on every dashboard load.
    op.create_index(
        "ix_submissions_student_status",
        "case_submissions",
        ["student_id", "status"],
    )
    op.create_index(
        "ix_submissions_dept_status",
        "case_submissions",
        ["department_id", "status"],
    )
    op.create_index(
        "ix_submissions_category_student",
        "case_submissions",
        ["task_category_id", "student_id"],
    )

    # StudentRotation indexes - rotation lookups in dashboard
    # Optimizes queries for current rotation by student or department
    op.create_index(
        "ix_rotations_student_current",
        "student_rotations",
        ["student_id", "is_current"],
    )
    op.create_index(
        "ix_rotations_dept_current",
        "student_rotations",
        ["department_id", "is_current"],
    )

    # SupervisorAssignment indexes - supervisor authorization checks
    # Optimizes queries checking supervisor assignments by type
    op.create_index(
        "ix_assignments_supervisor_type",
        "supervisor_assignments",
        ["supervisor_id", "assignment_type"],
    )

    # AuditLog indexes - audit log filtering
    # Optimizes metadata queries and filtering by table/user with date
    op.create_index(
        "ix_audit_logs_table_created",
        "audit_logs",
        ["table_name", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_user_created",
        "audit_logs",
        ["user_id", "created_at"],
    )

    # Notification indexes - notification history
    # Optimizes queries for notifications sent by or to a user
    op.create_index(
        "ix_notifications_sender_sent",
        "notifications",
        ["sender_id", "sent_at"],
    )
    op.create_index(
        "ix_notifications_recipient_sent",
        "notifications",
        ["recipient_id", "sent_at"],
    )


def downgrade() -> None:
    """Remove performance indexes."""

    # CaseSubmission
    op.drop_index("ix_submissions_student_status", table_name="case_submissions")
    op.drop_index("ix_submissions_dept_status", table_name="case_submissions")
    op.drop_index("ix_submissions_category_student", table_name="case_submissions")

    # StudentRotation
    op.drop_index("ix_rotations_student_current", table_name="student_rotations")
    op.drop_index("ix_rotations_dept_current", table_name="student_rotations")

    # SupervisorAssignment
    op.drop_index("ix_assignments_supervisor_type", table_name="supervisor_assignments")

    # AuditLog
    op.drop_index("ix_audit_logs_table_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")

    # Notification
    op.drop_index("ix_notifications_sender_sent", table_name="notifications")
    op.drop_index("ix_notifications_recipient_sent", table_name="notifications")
