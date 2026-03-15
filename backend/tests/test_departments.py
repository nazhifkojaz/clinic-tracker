import pytest
from sqlalchemy import select

from app.models.department import Department, TaskCategory
from tests.conftest import auth_header
from tests.factories import create_department, create_category


@pytest.mark.anyio
async def test_list_departments_includes_category_count(
    client, admin_token, db_session
):
    """Department list should include count of active categories."""
    # Create a department with 3 active categories
    dept = await create_department(db_session, name="Test Dept")
    await create_category(db_session, dept.id, name="Cat 1")
    await create_category(db_session, dept.id, name="Cat 2")
    await create_category(db_session, dept.id, name="Cat 3")

    # Create an inactive category (should not count)
    await create_category(db_session, dept.id, name="Inactive Cat", is_active=False)

    response = await client.get(
        "/api/departments",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()

    # Find our test department
    test_dept = next((d for d in data if d["name"] == "Test Dept"), None)
    assert test_dept is not None
    assert test_dept["category_count"] == 3


@pytest.mark.anyio
async def test_list_departments_empty_category_count(
    client, admin_token, db_session
):
    """Department with no categories should return count of 0."""
    dept = await create_department(db_session, name="Empty Dept")

    response = await client.get(
        "/api/departments",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()

    test_dept = next((d for d in data if d["name"] == "Empty Dept"), None)
    assert test_dept is not None
    assert test_dept["category_count"] == 0


@pytest.mark.anyio
async def test_list_departments_only_active_departments(
    client, student_token, db_session
):
    """Inactive departments should not appear in list."""
    # Create active department
    await create_department(db_session, name="Active Dept", is_active=True)

    # Create inactive department
    await create_department(db_session, name="Inactive Dept", is_active=False)

    response = await client.get(
        "/api/departments",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()

    names = [d["name"] for d in data]
    assert "Active Dept" in names
    assert "Inactive Dept" not in names
