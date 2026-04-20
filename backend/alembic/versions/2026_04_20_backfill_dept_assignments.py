"""backfill department assignments for existing supervisors

Revision ID: 2026_04_20_backfill_dept
Revises: 2026_04_14_inst_id_idx
Create Date: 2026-04-20

"""

from alembic import op


revision = "2026_04_20_backfill_dept"
down_revision = "2026_04_14_inst_id_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO supervisor_assignments (id, supervisor_id, department_id, assignment_type, created_at)
        SELECT gen_random_uuid(), u.id, u.department_id, 'department', now()
        FROM users u
        WHERE u.role = 'supervisor'
          AND u.is_active = true
          AND u.department_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM supervisor_assignments sa
            WHERE sa.supervisor_id = u.id AND sa.assignment_type = 'department'
          )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM supervisor_assignments
        WHERE assignment_type = 'department'
          AND EXISTS (
            SELECT 1 FROM users u
            WHERE u.id = supervisor_assignments.supervisor_id
              AND u.role = 'supervisor'
              AND u.is_active = true
              AND u.department_id IS NOT NULL
          )
    """)
