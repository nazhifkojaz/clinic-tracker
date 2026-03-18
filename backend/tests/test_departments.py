from sqlalchemy import select

from app.models.department import Department
from tests.conftest import auth_header
from tests.factories import create_department, create_category


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


async def test_list_departments_empty_category_count(client, admin_token, db_session):
    """Department with no categories should return count of 0."""
    await create_department(db_session, name="Empty Dept")

    response = await client.get(
        "/api/departments",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()

    test_dept = next((d for d in data if d["name"] == "Empty Dept"), None)
    assert test_dept is not None
    assert test_dept["category_count"] == 0


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


async def test_list_departments_public(client, admin_token, db_session):
    """Authenticated users can list active departments."""
    await create_department(db_session, name="Public Dept")
    await create_department(db_session, name="Another Dept")

    response = await client.get(
        "/api/departments",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    names = [d["name"] for d in data]
    assert "Public Dept" in names
    assert "Another Dept" in names


async def test_list_departments_includes_categories(client, admin_token, db_session):
    """Department detail endpoint includes nested categories."""
    dept = await create_department(db_session, name="Cat Dept")
    await create_category(db_session, dept.id, name="Category 1")
    await create_category(db_session, dept.id, name="Category 2")

    response = await client.get(
        f"/api/departments/{dept.id}",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Cat Dept"
    assert "task_categories" in data
    assert len(data["task_categories"]) == 2
    category_names = [c["name"] for c in data["task_categories"]]
    assert "Category 1" in category_names
    assert "Category 2" in category_names


async def test_get_department_excludes_inactive_categories(
    client, admin_token, db_session
):
    """Department detail should only return active categories and match category_count."""
    dept = await create_department(db_session, name="Mixed Dept")
    await create_category(db_session, dept.id, name="Active 1")
    await create_category(db_session, dept.id, name="Active 2")
    await create_category(db_session, dept.id, name="Inactive Cat", is_active=False)

    response = await client.get(
        f"/api/departments/{dept.id}",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()

    # Should only return active categories
    assert len(data["task_categories"]) == 2
    assert data["category_count"] == 2
    category_names = [c["name"] for c in data["task_categories"]]
    assert "Active 1" in category_names
    assert "Active 2" in category_names
    assert "Inactive Cat" not in category_names


async def test_create_department_admin_only(client, student_token, db_session):
    """Non-admin users should get 403 when creating departments."""
    response = await client.post(
        "/api/departments",
        json={"name": "Unauthorized Dept"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_create_department_success(client, admin_token, db_session):
    """Admin can create department with all fields."""
    response = await client.post(
        "/api/departments",
        json={
            "name": "New Department",
            "description": "A test department",
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Department"
    assert data["description"] == "A test department"
    assert data["is_active"] is True

    # Verify in database
    result = await db_session.execute(
        select(Department).where(Department.name == "New Department")
    )
    dept = result.scalar_one()
    assert dept is not None


async def test_create_department_duplicate_name_returns_409(
    client, admin_token, db_session
):
    """Duplicate department names should be rejected."""
    await create_department(db_session, name="Existing Dept")

    response = await client.post(
        "/api/departments",
        json={"name": "Existing Dept"},  # Exact duplicate name
        headers=auth_header(admin_token),
    )
    assert response.status_code == 409


async def test_create_department_duplicate_after_hard_delete(
    client, admin_token, db_session
):
    """Can reuse a name after hard-deleting a department from database."""
    # Create an inactive department and hard-delete it from DB
    dept = await create_department(db_session, name="Reusable Name", is_active=False)
    await db_session.delete(dept)
    await db_session.commit()

    # Should be able to create a new one with the same name
    response = await client.post(
        "/api/departments",
        json={"name": "Reusable Name"},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Reusable Name"


async def test_create_department_validates_name_required(client, admin_token):
    """Missing name should return 422 validation error."""
    response = await client.post(
        "/api/departments",
        json={"description": "No name provided"},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 422


async def test_update_department_admin_only(client, student_token, db_session):
    """Non-admin users should get 403 when updating departments."""
    dept = await create_department(db_session, name="Admin Only Test Dept")

    response = await client.patch(
        f"/api/departments/{dept.id}",
        json={"name": "Updated Admin Only"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_update_department_success(client, admin_token, db_session):
    """Admin can update department fields."""
    dept = await create_department(db_session, name="Original Name Update")

    response = await client.patch(
        f"/api/departments/{dept.id}",
        json={
            "name": "Updated Name Success",
            "description": "Updated description",
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name Success"
    assert data["description"] == "Updated description"


async def test_update_department_duplicate_name_returns_409(
    client, admin_token, db_session
):
    """Duplicate names should be rejected on update."""
    await create_department(db_session, name="Dept One Dup")
    dept2 = await create_department(db_session, name="Dept Two Dup")

    response = await client.patch(
        f"/api/departments/{dept2.id}",
        json={"name": "Dept One Dup"},  # Exact duplicate of dept1
        headers=auth_header(admin_token),
    )
    assert response.status_code == 409


async def test_soft_delete_department_via_update(client, admin_token, db_session):
    """Soft deleting a department via PATCH sets is_active=False."""
    dept = await create_department(db_session, name="To Soft Delete")

    response = await client.patch(
        f"/api/departments/{dept.id}",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False

    # Verify still in database but inactive
    await db_session.refresh(dept)
    assert dept.is_active is False


async def test_soft_delete_department_admin_only(client, student_token, db_session):
    """Non-admin users should get 403 when soft deleting departments."""
    dept = await create_department(db_session, name="Protected Soft Delete")

    response = await client.patch(
        f"/api/departments/{dept.id}",
        json={"is_active": False},
        headers=auth_header(student_token),
    )
    assert response.status_code == 403

    # Verify department still exists and is active
    await db_session.refresh(dept)
    assert dept.is_active is True
