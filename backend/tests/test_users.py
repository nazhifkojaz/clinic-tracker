from app.models.user import User, UserRole
from app.core.security import hash_password, verify_password
from tests.conftest import auth_header
from tests.factories import _random_suffix


async def test_list_users_admin_only(client, student_token):
    """Non-admins get 403 when listing users."""
    response = await client.get(
        "/api/users",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_list_users_pagination(client, admin_token):
    """List users returns paginated response."""
    response = await client.get(
        "/api/users",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert isinstance(data["items"], list)
    # Should have at least the 3 seeded users (admin, student, supervisor)
    assert len(data["items"]) >= 3
    assert "total" in data
    assert data["total"] >= 3


async def test_list_users_filters_by_role(client, admin_token, db_session):
    """Test filtering users by role parameter."""
    suffix = _random_suffix()
    # Create users with different roles
    student = User(
        email=f"filter_student_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Filter Student",
        student_id=f"FS{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    supervisor = User(
        email=f"filter_supervisor_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Filter Supervisor",
        role=UserRole.supervisor,
        is_active=True,
    )
    db_session.add_all([student, supervisor])
    await db_session.commit()

    # Filter by student role
    response = await client.get(
        "/api/users?role=student",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    items = data["items"]
    # All returned items should have role=student
    assert all(item["role"] == "student" for item in items)
    # Our created student should be in the results
    assert any(item["email"] == f"filter_student_{suffix}@test.com" for item in items)
    # Supervisor should NOT be in the results
    assert not any(
        item["email"] == f"filter_supervisor_{suffix}@test.com" for item in items
    )


async def test_list_users_filters_by_active(client, admin_token, db_session):
    """Test filtering users by is_active parameter."""
    suffix = _random_suffix()
    inactive = User(
        email=f"inactive_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Inactive User",
        student_id=f"INACT{suffix}",
        role=UserRole.student,
        is_active=False,
    )
    db_session.add(inactive)
    await db_session.commit()

    # Filter for active users only
    response = await client.get(
        "/api/users?is_active=true",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    items = data["items"]
    # All returned items should be active
    assert all(item["is_active"] is True for item in items)
    # Inactive user should NOT be in the results
    assert not any(item["email"] == f"inactive_{suffix}@test.com" for item in items)

    # Filter for inactive users only
    response = await client.get(
        "/api/users?is_active=false",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    # Our created inactive user should be in the results
    assert any(item["email"] == f"inactive_{suffix}@test.com" for item in items)
    # All returned items should be inactive
    assert all(item["is_active"] is False for item in items)


async def test_create_user_admin_only(client, student_token):
    """Non-admins cannot create users."""
    suffix = _random_suffix()
    response = await client.post(
        "/api/users",
        json={
            "email": f"unauth_{suffix}@test.com",
            "password": "testpass123",
            "full_name": "Unauthorized User",
            "role": "student",
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_create_user_success(client, admin_token, db_session):
    """Admin creates each role type (student, supervisor, admin)."""
    # Create student
    suffix = _random_suffix()
    student_resp = await client.post(
        "/api/users",
        json={
            "email": f"new_student_{suffix}@test.com",
            "password": "testpass123",
            "full_name": "New Student",
            "student_id": f"NS{suffix}",
            "role": "student",
        },
        headers=auth_header(admin_token),
    )
    assert student_resp.status_code == 201
    student_data = student_resp.json()
    assert student_data["role"] == "student"
    assert student_data["student_id"] == f"NS{suffix}"

    # Create supervisor
    sup_resp = await client.post(
        "/api/users",
        json={
            "email": f"new_sup_{suffix}@test.com",
            "password": "testpass123",
            "full_name": "New Supervisor",
            "role": "supervisor",
        },
        headers=auth_header(admin_token),
    )
    assert sup_resp.status_code == 201
    sup_data = sup_resp.json()
    assert sup_data["role"] == "supervisor"
    assert sup_data["student_id"] is None

    # Create admin
    admin_resp = await client.post(
        "/api/users",
        json={
            "email": f"new_admin_{suffix}@test.com",
            "password": "testpass123",
            "full_name": "New Admin",
            "role": "admin",
        },
        headers=auth_header(admin_token),
    )
    assert admin_resp.status_code == 201
    admin_data = admin_resp.json()
    assert admin_data["role"] == "admin"


async def test_create_user_duplicate_email_returns_409(client, admin_token, db_session):
    """Duplicate emails should be rejected with 409."""
    suffix = _random_suffix()
    email = f"dup_{suffix}@test.com"

    # Create first user
    first = User(
        email=email,
        password_hash=hash_password("testpass123"),
        full_name="First User",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(first)
    await db_session.commit()

    # Try to create duplicate
    response = await client.post(
        "/api/users",
        json={
            "email": email,
            "password": "testpass123",
            "full_name": "Duplicate User",
            "role": "student",
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


async def test_create_user_validates_email_format(client, admin_token):
    """Invalid email format should return 422."""
    response = await client.post(
        "/api/users",
        json={
            "email": "not-an-email",
            "password": "testpass123",
            "full_name": "Invalid Email User",
            "role": "student",
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 422


async def test_create_user_student_requires_student_id(client, admin_token, db_session):
    """Students can be created without student_id (it's optional in schema)."""
    suffix = _random_suffix()
    response = await client.post(
        "/api/users",
        json={
            "email": f"student_no_id_{suffix}@test.com",
            "password": "testpass123",
            "full_name": "Student Without ID",
            "role": "student",
            # student_id is optional, so this should work
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] is None


async def test_update_user_admin_only(client, student_token, db_session):
    """Non-admins cannot update users."""
    suffix = _random_suffix()
    user = User(
        email=f"to_update_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Original Name",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    response = await client.patch(
        f"/api/users/{user.id}",
        json={"full_name": "Updated Name"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_update_user_success(client, admin_token, db_session):
    """Admin can update user fields."""
    suffix = _random_suffix()
    user = User(
        email=f"update_success_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Original Name",
        student_id=f"ORIG{suffix}",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    response = await client.patch(
        f"/api/users/{user.id}",
        json={
            "full_name": "Updated Name",
            "student_id": f"UPD{suffix}",
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Name"
    assert data["student_id"] == f"UPD{suffix}"
    assert data["email"] == f"update_success_{suffix}@test.com"  # Unchanged


async def test_update_user_email_duplicate_returns_409(client, admin_token, db_session):
    """Email conflict on update should return 409."""
    suffix = _random_suffix()
    user1 = User(
        email=f"user1_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="User One",
        role=UserRole.student,
        is_active=True,
    )
    user2 = User(
        email=f"user2_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="User Two",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add_all([user1, user2])
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)

    # Try to update user2's email to user1's email
    response = await client.patch(
        f"/api/users/{user2.id}",
        json={"email": f"user1_{suffix}@test.com"},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 409


async def test_deactivate_user_soft_delete(client, admin_token, db_session):
    """Deactivating a user via PATCH sets is_active=False."""
    suffix = _random_suffix()
    user = User(
        email=f"to_deactivate_{suffix}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="To Deactivate",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    response = await client.patch(
        f"/api/users/{user.id}",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False

    # Verify in database
    await db_session.refresh(user)
    assert user.is_active is False


async def test_deactivated_user_cannot_login(client, inactive_user):
    """Inactive user cannot login (uses inactive_user fixture)."""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": inactive_user.email,
            "password": "testpass123",
        },
    )
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"].lower()


async def test_get_me_returns_current_user(client, student_token, student_user):
    """Returns authenticated user's data."""
    response = await client.get(
        "/api/users/me",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(student_user.id)
    assert data["email"] == student_user.email


async def test_get_me_includes_correct_fields(client, student_token):
    """All expected fields are present in /me response."""
    response = await client.get(
        "/api/users/me",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    expected_fields = [
        "id",
        "email",
        "full_name",
        "student_id",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    ]
    for field in expected_fields:
        assert field in data, f"Field {field} missing from response"


async def test_change_password_requires_current_password(
    client, admin_token, db_session
):
    """Admin can update user password (no self-service change in current implementation)."""
    suffix = _random_suffix()
    user = User(
        email=f"pwd_change_{suffix}@test.com",
        password_hash=hash_password("oldpassword123"),
        full_name="Password Change User",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Admin updates the user's password
    response = await client.patch(
        f"/api/users/{user.id}",
        json={"password": "newpassword123"},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200

    # Verify password was changed
    await db_session.refresh(user)
    assert verify_password("newpassword123", user.password_hash)
    assert not verify_password("oldpassword123", user.password_hash)


async def test_change_password_success(client, admin_token, db_session):
    """Password updated successfully, user can login with new password."""
    suffix = _random_suffix()
    user = User(
        email=f"pwd_success_{suffix}@test.com",
        password_hash=hash_password("oldpass123"),
        full_name="Password Success User",
        role=UserRole.student,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Verify old password works
    old_login = await client.post(
        "/api/auth/login",
        json={
            "email": user.email,
            "password": "oldpass123",
        },
    )
    assert old_login.status_code == 200

    # Admin updates password
    response = await client.patch(
        f"/api/users/{user.id}",
        json={"password": "newpass123"},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200

    # Verify new password works
    new_login = await client.post(
        "/api/auth/login",
        json={
            "email": user.email,
            "password": "newpass123",
        },
    )
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()

    # Verify old password no longer works
    old_login_after = await client.post(
        "/api/auth/login",
        json={
            "email": user.email,
            "password": "oldpass123",
        },
    )
    assert old_login_after.status_code == 401
