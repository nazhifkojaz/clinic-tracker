"""add target_supervisor_id to case_submissions

Revision ID: 20260420_add_target_sv
Revises: 2026_04_20_backfill_dept
Create Date: 2026-04-20

"""

import sqlalchemy as sa
from alembic import op

revision = "20260420_add_target_sv"
down_revision = "2026_04_20_backfill_dept"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_submissions",
        sa.Column("target_supervisor_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_case_submissions_target_supervisor_id",
        "case_submissions",
        "users",
        ["target_supervisor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_submissions_target_supervisor_status",
        "case_submissions",
        ["target_supervisor_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_submissions_target_supervisor_status",
        table_name="case_submissions",
    )
    op.drop_constraint(
        "fk_case_submissions_target_supervisor_id",
        "case_submissions",
        type_="foreignkey",
    )
    op.drop_column("case_submissions", "target_supervisor_id")
