"""Add rotation_duration_days, days_offset, last_reminder_sent

Revision ID: 2026_03_30_rotation_tracker
Revises: 2026_03_30_user_registration
Create Date: 2026-03-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2026_03_30_rotation_tracker"
down_revision: Union[str, None] = "2026_03_30_user_registration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "departments",
        sa.Column(
            "rotation_duration_days",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )
    op.add_column(
        "student_rotations",
        sa.Column(
            "days_offset",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "student_rotations",
        sa.Column("last_reminder_sent", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("student_rotations", "last_reminder_sent")
    op.drop_column("student_rotations", "days_offset")
    op.drop_column("departments", "rotation_duration_days")
