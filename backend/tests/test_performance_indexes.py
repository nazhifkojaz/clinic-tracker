"""Test that performance indexes exist and are properly configured.

These tests verify PERF-03, PERF-04, PERF-05, and PERF-06 indexes
from the performance audit.
"""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_pg_trgm_extension_enabled(db_session):
    """Verify pg_trgm extension is enabled (PERF-04)."""
    result = await db_session.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
    )
    assert result.scalar() == 1, "pg_trgm extension not enabled"


@pytest.mark.asyncio
async def test_user_role_is_active_index_exists(db_session):
    """Verify ix_users_role_is_active composite index was created (PERF-03)."""
    result = await db_session.execute(
        text("""
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'users'
            AND indexname = 'ix_users_role_is_active'
        """)
    )
    assert result.scalar() == 1, "Index ix_users_role_is_active not found"


@pytest.mark.asyncio
async def test_user_role_index_exists(db_session):
    """Verify ix_users_role index was created (PERF-03)."""
    result = await db_session.execute(
        text("""
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'users'
            AND indexname = 'ix_users_role'
        """)
    )
    assert result.scalar() == 1, "Index ix_users_role not found"


@pytest.mark.asyncio
async def test_user_is_active_index_exists(db_session):
    """Verify ix_users_is_active index was created (PERF-03)."""
    result = await db_session.execute(
        text("""
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'users'
            AND indexname = 'ix_users_is_active'
        """)
    )
    assert result.scalar() == 1, "Index ix_users_is_active not found"


@pytest.mark.asyncio
async def test_user_trigram_indexes_exist(db_session):
    """Verify trigram indexes on users were created (PERF-04)."""
    result = await db_session.execute(
        text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'users'
            AND indexname LIKE '%_trgm'
        """)
    )
    index_names = [row[0] for row in result.fetchall()]
    assert "ix_users_full_name_trgm" in index_names, "ix_users_full_name_trgm not found"
    assert "ix_users_email_trgm" in index_names, "ix_users_email_trgm not found"
    assert "ix_users_institutional_id_trgm" in index_names, (
        "ix_users_institutional_id_trgm not found"
    )


@pytest.mark.asyncio
async def test_task_category_composite_index_exists(db_session):
    """Verify ix_task_categories_dept_is_active index was created (PERF-05)."""
    result = await db_session.execute(
        text("""
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'task_categories'
            AND indexname = 'ix_task_categories_dept_is_active'
        """)
    )
    assert result.scalar() == 1, "Index ix_task_categories_dept_is_active not found"


@pytest.mark.asyncio
async def test_department_is_active_index_exists(db_session):
    """Verify ix_departments_is_active index was created (PERF-06)."""
    result = await db_session.execute(
        text("""
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'departments'
            AND indexname = 'ix_departments_is_active'
        """)
    )
    assert result.scalar() == 1, "Index ix_departments_is_active not found"


@pytest.mark.asyncio
async def test_all_performance_indexes_present(db_session):
    """Comprehensive test ensuring all PERF-03 through PERF-06 indexes exist."""
    result = await db_session.execute(
        text("""
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname IN (
                'ix_users_role',
                'ix_users_is_active',
                'ix_users_role_is_active',
                'ix_users_full_name_trgm',
                'ix_users_email_trgm',
                'ix_users_institutional_id_trgm',
                'ix_task_categories_dept_is_active',
                'ix_departments_is_active'
            )
            ORDER BY indexname
        """)
    )
    found_indexes = [row[0] for row in result.fetchall()]

    expected_indexes = [
        "ix_users_role",
        "ix_users_is_active",
        "ix_users_role_is_active",
        "ix_users_full_name_trgm",
        "ix_users_email_trgm",
        "ix_users_institutional_id_trgm",
        "ix_task_categories_dept_is_active",
        "ix_departments_is_active",
    ]

    for expected in expected_indexes:
        assert expected in found_indexes, f"Expected index {expected} not found"

    assert len(found_indexes) == len(expected_indexes), (
        f"Expected {len(expected_indexes)} indexes, found {len(found_indexes)}"
    )
