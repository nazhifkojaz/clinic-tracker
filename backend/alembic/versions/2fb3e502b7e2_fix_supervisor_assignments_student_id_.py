"""fix supervisor_assignments student_id nullable and index

Revision ID: 2fb3e502b7e2
Revises: 89b866e8aacc
Create Date: 2026-03-10 13:47:43.686943

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2fb3e502b7e2'
down_revision: Union[str, Sequence[str], None] = '89b866e8aacc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old department index (includes student_id)
    op.execute("DROP INDEX IF EXISTS uq_department_assignment")

    # Make student_id nullable
    op.alter_column(
        'supervisor_assignments',
        'student_id',
        existing_type=sa.UUID(),
        nullable=True
    )

    # Recreate the department index without student_id
    op.execute("""
        CREATE UNIQUE INDEX uq_department_assignment
        ON supervisor_assignments (supervisor_id, department_id)
        WHERE assignment_type = 'department'
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the new index
    op.execute("DROP INDEX IF EXISTS uq_department_assignment")

    # Make student_id not null again
    op.alter_column(
        'supervisor_assignments',
        'student_id',
        existing_type=sa.UUID(),
        nullable=False
    )

    # Recreate the old index (with student_id)
    op.execute("""
        CREATE UNIQUE INDEX uq_department_assignment
        ON supervisor_assignments (supervisor_id, student_id, department_id)
        WHERE assignment_type = 'department'
    """)
