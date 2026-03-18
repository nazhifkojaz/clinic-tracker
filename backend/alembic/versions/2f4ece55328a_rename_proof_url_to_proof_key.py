"""rename proof_url to proof_key

Revision ID: 2f4ece55328a
Revises: 9d81710b9cee
Create Date: 2026-03-17 01:25:37.411368

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2f4ece55328a'
down_revision: Union[str, Sequence[str], None] = '9d81710b9cee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename proof_url column to proof_key."""
    op.alter_column('case_submissions', 'proof_url', new_column_name='proof_key')


def downgrade() -> None:
    """Rename proof_key column back to proof_url."""
    op.alter_column('case_submissions', 'proof_key', new_column_name='proof_url')
