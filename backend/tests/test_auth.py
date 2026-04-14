from app.models.user import User, UserRole
from tests.conftest import auth_header


async def test_login_success(client, student_user):
    """Valid credentials should return access + refresh tokens."""
    response = await client.post(
        "/api/auth/login",
        json={
            "identifier": "student@test.com",
            "password": "testpass123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["access_token"]
    assert data["refresh_token"]


async def test_login_wrong_password(client, student_user):
    """Wrong password should return 401."""
    response = await client.post(
        "/api/auth/login",
        json={
            "identifier": "student@test.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_login_nonexistent_user(client):
    """Nonexistent identifier should return 401 (don't leak existence)."""
    response = await client.post(
        "/api/auth/login",
        json={
            "identifier": "nobody@test.com",
            "password": "anything",
        },
    )
    assert response.status_code == 401


async def test_login_unverified_email(client, inactive_user):
    """Inactive user with unverified email should return 403 with email prompt."""
    response = await client.post(
        "/api/auth/login",
        json={
            "identifier": inactive_user.email,
            "password": "testpass123",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Please verify your email before logging in."


async def test_refresh_token(client, student_user):
    """Valid refresh token should return new token pair."""
    # First, login to get tokens
    login_resp = await client.post(
        "/api/auth/login",
        json={
            "identifier": "student@test.com",
            "password": "testpass123",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Refresh
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Verify we can decode the new access token
    from app.core.security import decode_token

    payload = decode_token(data["access_token"])
    assert payload["type"] == "access"


async def test_refresh_with_invalid_token(client):
    """Invalid refresh token should return 401."""
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code == 401


async def test_refresh_with_access_token_fails(client, student_token):
    """Using an access token as refresh token should fail."""
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": student_token},  # This is an access token, not refresh
    )
    assert response.status_code == 401


async def test_protected_endpoint_without_token(client):
    """Accessing protected endpoint without token should return 401/403."""
    response = await client.get("/api/users/me")
    assert response.status_code in (401, 403)


async def test_protected_endpoint_with_valid_token(client, student_user, student_token):
    """Valid token should grant access to protected endpoints."""
    response = await client.get(
        "/api/users/me",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    assert response.json()["email"] == "student@test.com"


async def test_admin_from_token_requires_db_revalidation(db_session):
    """require_admin_from_token should revalidate user status against DB."""
    from app.api.dependencies import require_admin_from_token

    # Create an admin user
    from tests.factories import _random_suffix

    suffix = _random_suffix()
    admin_user = User(
        email=f"admin_{suffix}@test.com",
        password_hash="hash",
        full_name="Test Admin",
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(admin_user)
    await db_session.commit()
    await db_session.refresh(admin_user)

    # First call should succeed (user is active admin)
    result = await require_admin_from_token(
        auth_data=(admin_user.id, UserRole.admin),
        db=db_session,
    )
    assert result == admin_user.id

    # Deactivate the user
    admin_user.is_active = False
    await db_session.commit()

    # Second call should fail (user is now inactive)
    import pytest

    with pytest.raises(Exception) as exc_info:
        await require_admin_from_token(
            auth_data=(admin_user.id, UserRole.admin),
            db=db_session,
        )
    assert exc_info.value.status_code == 403
    assert "inactive" in str(exc_info.value.detail).lower()


async def test_supervisor_from_token_requires_db_revalidation(db_session):
    """require_supervisor_from_token should revalidate user status against DB."""
    from app.api.dependencies import require_supervisor_from_token

    # Create a supervisor user
    from tests.factories import _random_suffix

    suffix = _random_suffix()
    supervisor_user = User(
        email=f"sup_{suffix}@test.com",
        password_hash="hash",
        full_name="Test Supervisor",
        role=UserRole.supervisor,
        is_active=True,
    )
    db_session.add(supervisor_user)
    await db_session.commit()
    await db_session.refresh(supervisor_user)

    # First call should succeed (user is active supervisor)
    result = await require_supervisor_from_token(
        auth_data=(supervisor_user.id, UserRole.supervisor),
        db=db_session,
    )
    assert result == supervisor_user.id

    # Demote the user to student
    supervisor_user.role = UserRole.student
    await db_session.commit()

    # Second call should fail (user is no longer supervisor/admin)
    import pytest

    with pytest.raises(Exception) as exc_info:
        await require_supervisor_from_token(
            auth_data=(supervisor_user.id, UserRole.supervisor),
            db=db_session,
        )
    assert exc_info.value.status_code == 403


async def test_admin_from_token_returns_404_for_deleted_user(db_session):
    """require_admin_from_token should return 404 for deleted user."""
    from app.api.dependencies import require_admin_from_token
    import uuid

    fake_user_id = uuid.uuid4()

    import pytest

    with pytest.raises(Exception) as exc_info:
        await require_admin_from_token(
            auth_data=(fake_user_id, UserRole.admin),
            db=db_session,
        )
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


# ---------------------------------------------------------------------------
# New tests: login by institutional_id, registration, email verification
# ---------------------------------------------------------------------------


async def test_login_with_institutional_id(client, student_user):
    """Login using institutional_id instead of email should succeed."""
    response = await client.post(
        "/api/auth/login",
        json={
            "identifier": "STU001",  # institutional_id of the seeded student
            "password": "testpass123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_login_pending_approval(client, db_session):
    """User with email_verified=True but is_active=False should get pending-approval 403."""
    from tests.factories import _random_suffix

    suffix = _random_suffix()
    from app.core.security import hash_password as _hp

    user = User(
        email=f"pending_{suffix}@test.com",
        password_hash=await _hp("testpass123"),
        full_name="Pending User",
        role=UserRole.student,
        is_active=False,
        email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"identifier": user.email, "password": "testpass123"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Your account is pending admin approval."


async def test_register_success(client, db_session):
    """Self-registration creates an inactive, unverified user and returns 201."""
    from tests.factories import _random_suffix
    from sqlalchemy import select

    suffix = _random_suffix()
    email = f"newuser_{suffix}@test.com"

    response = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "full_name": "New User",
            "role": "student",
            "institutional_id": f"NEW{suffix}",
        },
    )
    assert response.status_code == 201
    assert "verify" in response.json()["message"].lower()

    # User exists in DB but is inactive and unverified
    result = await db_session.execute(select(User).where(User.email == email))
    created = result.scalar_one_or_none()
    assert created is not None
    assert created.is_active is False
    assert created.email_verified is False


async def test_register_duplicate_email(client, db_session):
    """Registering with an already-taken email should return 409."""
    from tests.factories import _random_suffix

    suffix = _random_suffix()
    payload = {
        "email": f"dup_{suffix}@test.com",
        "password": "securepass123",
        "full_name": "User One",
        "role": "student",
        "institutional_id": f"DUP1{suffix}",
    }
    await client.post("/api/auth/register", json=payload)

    # Second registration with same email, different institutional_id
    payload["institutional_id"] = f"DUP2{suffix}"
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 409


async def test_register_admin_without_invite_code(client):
    """Admin registration without invite code should return 400."""
    from tests.factories import _random_suffix

    suffix = _random_suffix()
    response = await client.post(
        "/api/auth/register",
        json={
            "email": f"adminattempt_{suffix}@test.com",
            "password": "securepass123",
            "full_name": "Bad Actor",
            "role": "admin",
            "institutional_id": f"BADACTOR{suffix}",
        },
    )
    assert response.status_code == 400
    assert "invite code" in response.json()["detail"].lower()


async def test_verify_email_success(client, db_session):
    """Valid verification token sets email_verified=True."""
    from tests.factories import _random_suffix
    from app.core.security import create_email_verification_token, hash_password as _hp

    suffix = _random_suffix()
    user = User(
        email=f"verify_{suffix}@test.com",
        password_hash=await _hp("testpass123"),
        full_name="Verify Me",
        role=UserRole.student,
        is_active=False,
        email_verified=False,
        institutional_id=f"VER{suffix}",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_email_verification_token(str(user.id))
    response = await client.get(f"/api/auth/verify-email?token={token}")
    assert response.status_code == 200
    assert "verified" in response.json()["message"].lower()

    # Confirm DB state updated
    await db_session.refresh(user)
    assert user.email_verified is True


async def test_verify_email_invalid_token(client):
    """Invalid token should return 400."""
    response = await client.get("/api/auth/verify-email?token=this.is.garbage")
    assert response.status_code == 400


async def test_verify_email_already_verified(client, db_session):
    """Verifying an already-verified email should be idempotent (200, not an error)."""
    from tests.factories import _random_suffix
    from app.core.security import create_email_verification_token, hash_password as _hp

    suffix = _random_suffix()
    user = User(
        email=f"already_{suffix}@test.com",
        password_hash=await _hp("testpass123"),
        full_name="Already Verified",
        role=UserRole.student,
        is_active=False,
        email_verified=True,
        institutional_id=f"ALVR{suffix}",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_email_verification_token(str(user.id))
    response = await client.get(f"/api/auth/verify-email?token={token}")
    assert response.status_code == 200
    assert "already" in response.json()["message"].lower()
