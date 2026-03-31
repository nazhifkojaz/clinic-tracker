"""Add user registration support: rename student_id, add email_verified, department_id.

Revision ID: 2026_03_30_user_registration
Revises: 2026_03_30_add_deleted_at
Create Date: 2026-03-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_03_30_user_registration"
down_revision: Union[str, None] = "2026_03_30_add_deleted_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename student_id -> institutional_id
    op.alter_column("users", "student_id", new_column_name="institutional_id")

    # Add email_verified boolean (default false, not null)
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Add department_id FK (nullable, for supervisor self-registration)
    op.add_column(
        "users",
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_users_department_id",
        "users",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Normalize empty strings to NULL before creating the unique index
    op.execute(
        sa.text(
            "UPDATE users SET institutional_id = NULL WHERE institutional_id = ''"
        )
    )

    # Partial unique index on institutional_id where not null
    op.create_index(
        "ix_users_institutional_id_unique",
        "users",
        ["institutional_id"],
        unique=True,
        postgresql_where=sa.text("institutional_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_institutional_id_unique", table_name="users")
    op.drop_constraint("fk_users_department_id", "users", type_="foreignkey")
    op.drop_column("users", "department_id")
    op.drop_column("users", "email_verified")
    op.alter_column("users", "institutional_id", new_column_name="student_id")
