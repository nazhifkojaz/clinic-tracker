"""add_invite_codes_table

Revision ID: 6320dcc3ee2c
Revises: 20260331_partial_deleted_idx
Create Date: 2026-04-13 06:45:30.257220

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6320dcc3ee2c'
down_revision: Union[str, Sequence[str], None] = '20260331_partial_deleted_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('invite_codes',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('code', sa.String(length=12), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('active', 'used', name='invite_code_status', create_constraint=True), server_default=sa.text("'active'"), nullable=False),
    sa.Column('used_by', sa.UUID(), nullable=True),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['used_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invite_codes_code'), 'invite_codes', ['code'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_invite_codes_code'), table_name='invite_codes')
    op.drop_table('invite_codes')
