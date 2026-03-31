"""Add deleted_at soft-delete column to case_submissions.

Revision ID: 2026_03_30_add_deleted_at
Revises: 20260317_add_single_col_indexes
Create Date: 2026-03-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2026_03_30_add_deleted_at"
down_revision: Union[str, None] = "20260317_add_single_col_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "case_submissions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_submissions_deleted_at", "case_submissions", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_submissions_deleted_at", table_name="case_submissions")
    op.drop_column("case_submissions", "deleted_at")
