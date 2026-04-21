"""add_reason_column_to_pending_profile_changes

Revision ID: 416da156c56c
Revises: 20260420_add_target_sv
Create Date: 2026-04-21 03:45:03.588358

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "416da156c56c"
down_revision: Union[str, Sequence[str], None] = "20260420_add_target_sv"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "pending_profile_changes",
        sa.Column("reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("pending_profile_changes", "reason")
