"""Optimize deleted_at index to be partial (PERF-10).

Revision ID: 20260331_partial_deleted_at_index
Revises: 20260331_user_search_indexes
Create Date: 2026-03-31

This migration addresses PERF-10 from the performance audit by replacing
the full ix_submissions_deleted_at index with a partial index that only
includes rows where deleted_at IS NOT NULL.

Benefits:
- Reduces index size by ~95% (assuming 5% deletion rate)
- Faster INSERT operations (no index maintenance for NULL values)
- Faster queries filtering on deleted_at IS NOT NULL
- Same query performance for deleted_at IS NULL (table scan)
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260331_partial_deleted_idx"
down_revision: Union[str, None] = "20260331_user_search_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace full deleted_at index with partial index."""

    # Step 1: Drop the existing full index
    op.drop_index("ix_submissions_deleted_at", table_name="case_submissions")

    # Step 2: Create partial index (only indexes non-NULL values)
    # This optimizes queries that filter on deleted_at IS NOT NULL
    op.execute(
        "CREATE INDEX ix_submissions_deleted_partial "
        "ON case_submissions (deleted_at) "
        "WHERE deleted_at IS NOT NULL"
    )


def downgrade() -> None:
    """Revert to full deleted_at index."""

    # Step 1: Drop the partial index
    op.drop_index("ix_submissions_deleted_partial", table_name="case_submissions")

    # Step 2: Recreate the full index
    op.create_index(
        "ix_submissions_deleted_at",
        "case_submissions",
        ["deleted_at"],
    )
