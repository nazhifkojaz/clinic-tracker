"""add_pending_profile_changes_table

Revision ID: 98c94a776559
Revises: 6320dcc3ee2c
Create Date: 2026-04-13 07:38:22.850294

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "98c94a776559"
down_revision: Union[str, Sequence[str], None] = "6320dcc3ee2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "pending_profile_changes",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("field_name", sa.String(length=50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                name="pending_change_status",
                create_constraint=True,
            ),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pending_changes_user_field_pending",
        "pending_profile_changes",
        ["user_id", "field_name"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        op.f("ix_pending_profile_changes_user_id"),
        "pending_profile_changes",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_pending_profile_changes_user_id"), table_name="pending_profile_changes"
    )
    op.drop_index(
        "ix_pending_changes_user_field_pending",
        table_name="pending_profile_changes",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_table("pending_profile_changes")
