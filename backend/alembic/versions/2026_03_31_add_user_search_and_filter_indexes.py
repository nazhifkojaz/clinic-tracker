"""Add indexes for user search and common filter patterns.

Revision ID: 20260331_add_user_search_filter_indexes
Revises: 2026_03_30_add_deleted_at
Create Date: 2026-03-31

This migration addresses PERF-03, PERF-04, PERF-05, and PERF-06 from the
performance audit by adding indexes to optimize:
- User.role and User.is_active filters (PERF-03)
- User search with ilike on full_name, email, institutional_id (PERF-04)
- TaskCategory.department_id and is_active filters (PERF-05)
- Department.is_active filters (PERF-06)
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260331_user_search_indexes"
down_revision: Union[str, None] = "2026_03_30_rotation_tracker"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create indexes for user search and common filter patterns."""

    # PERF-04: Enable pg_trgm extension for trigram indexes (must be first)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # PERF-04: Add GIN trigram indexes for user search
    # These optimize ilike queries with leading wildcards on:
    # - User.full_name
    # - User.email
    # - User.institutional_id
    op.execute(
        "CREATE INDEX ix_users_full_name_trgm ON users "
        "USING gin (full_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_users_email_trgm ON users USING gin (email gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_users_institutional_id_trgm ON users "
        "USING gin (institutional_id gin_trgm_ops)"
    )

    # PERF-03: Add single-column indexes on User.role and User.is_active
    # These optimize queries filtering on only one of these columns
    op.create_index(
        "ix_users_role",
        "users",
        ["role"],
    )
    op.create_index(
        "ix_users_is_active",
        "users",
        ["is_active"],
    )

    # PERF-03: Add composite index on User(role, is_active)
    # This optimizes dashboard queries that filter on both columns
    # Used in: supervisor dashboard, scheduler, user listing
    op.create_index(
        "ix_users_role_is_active",
        "users",
        ["role", "is_active"],
    )

    # PERF-05: Add composite index on TaskCategory(department_id, is_active)
    # This optimizes queries filtering categories by department and active status
    # Used in: department dashboard, scheduler, category listing
    op.create_index(
        "ix_task_categories_dept_is_active",
        "task_categories",
        ["department_id", "is_active"],
    )

    # PERF-06: Add index on Department.is_active
    # This optimizes queries filtering active departments
    # Used in: student dashboard, department listing, scheduler
    op.create_index(
        "ix_departments_is_active",
        "departments",
        ["is_active"],
    )


def downgrade() -> None:
    """Remove all created indexes and extension."""

    # PERF-06: Remove Department.is_active index
    op.drop_index("ix_departments_is_active", table_name="departments")

    # PERF-05: Remove TaskCategory composite index
    op.drop_index("ix_task_categories_dept_is_active", table_name="task_categories")

    # PERF-03: Remove User composite and single-column indexes
    op.drop_index("ix_users_role_is_active", table_name="users")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_role", table_name="users")

    # PERF-04: Remove trigram indexes
    op.drop_index("ix_users_institutional_id_trgm", table_name="users")
    op.drop_index("ix_users_email_trgm", table_name="users")
    op.drop_index("ix_users_full_name_trgm", table_name="users")

    # PERF-04: Remove pg_trgm extension
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
