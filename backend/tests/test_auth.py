import pytest

from tests.conftest import auth_header


@pytest.mark.anyio
async def test_login_success(client, student_user):
    """Valid credentials should return access + refresh tokens."""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "student@test.com",
            "password": "testpass123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["access_token"]
    assert data["refresh_token"]


@pytest.mark.anyio
async def test_login_wrong_password(client, student_user):
    """Wrong password should return 401."""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "student@test.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


@pytest.mark.anyio
async def test_login_nonexistent_user(client):
    """Nonexistent email should return 401 (don't leak existence)."""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "nobody@test.com",
            "password": "anything",
        },
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_login_inactive_user(client, student_user, db_session):
    """Inactive user should return 403."""
    from sqlalchemy import select
    from app.models.user import User

    # Fetch and update the user in the database
    result = await db_session.execute(select(User).where(User.id == student_user.id))
    user = result.scalar_one()
    user.is_active = False
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={
            "email": "student@test.com",
            "password": "testpass123",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Account is deactivated"

    # Restore user to active for other tests
    user.is_active = True
    await db_session.commit()


@pytest.mark.anyio
async def test_refresh_token(client, student_user):
    """Valid refresh token should return new token pair."""
    # First, login to get tokens
    login_resp = await client.post(
        "/api/auth/login",
        json={
            "email": "student@test.com",
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


@pytest.mark.anyio
async def test_refresh_with_invalid_token(client):
    """Invalid refresh token should return 401."""
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_refresh_with_access_token_fails(client, student_token):
    """Using an access token as refresh token should fail."""
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": student_token},  # This is an access token, not refresh
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_protected_endpoint_without_token(client):
    """Accessing protected endpoint without token should return 401/403."""
    response = await client.get("/api/users/me")
    assert response.status_code in (401, 403)


@pytest.mark.anyio
async def test_protected_endpoint_with_valid_token(client, student_user, student_token):
    """Valid token should grant access to protected endpoints."""
    response = await client.get(
        "/api/users/me",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    assert response.json()["email"] == "student@test.com"
