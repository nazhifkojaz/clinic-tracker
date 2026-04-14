"""add_institutional_id_btree_index

Revision ID: 2026_04_14_inst_id_idx
Revises: 98c94a776559
Create Date: 2026-04-14

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2026_04_14_inst_id_idx"
down_revision: Union[str, Sequence[str], None] = "98c94a776559"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add B-tree index on users.institutional_id for equality lookups (login by institutional_id)."""
    op.create_index(
        op.f("ix_users_institutional_id"), "users", ["institutional_id"], unique=False
    )


def downgrade() -> None:
    """Drop B-tree index on users.institutional_id."""
    op.drop_index(op.f("ix_users_institutional_id"), table_name="users")
