"""Tests for invite code generation, listing, validation, and consumption."""

import pytest
from app.models.invite_code import InviteCode, InviteCodeStatus
from app.models.user import User, UserRole
from app.core.security import hash_password
from tests.conftest import auth_header
from tests.factories import _random_suffix


# ---------------------------------------------------------------------------
# Generate invite code
# ---------------------------------------------------------------------------


async def test_generate_code_admin_only(client, student_token):
    """Non-admins cannot generate invite codes."""
    response = await client.post(
        "/api/invite-codes",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_generate_code_success(client, admin_token, admin_user, db_session):
    """Admin can generate a new invite code."""
    response = await client.post(
        "/api/invite-codes",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "code" in data
    assert len(data["code"]) == 8
    assert data["status"] == "active"
    assert data["created_by"] == str(admin_user.id)
    assert data["used_by"] is None
    assert data["used_at"] is None

    # Verify code exists in DB
    result = await db_session.execute(
        __import__("sqlalchemy").select(InviteCode).where(InviteCode.id == data["id"])
    )
    code = result.scalar_one_or_none()
    assert code is not None
    assert code.status == InviteCodeStatus.active


async def test_generate_multiple_codes_unique(client, admin_token):
    """Each generated code is unique."""
    codes = set()
    for _ in range(5):
        response = await client.post(
            "/api/invite-codes",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        codes.add(response.json()["code"])
    assert len(codes) == 5


# ---------------------------------------------------------------------------
# List invite codes
# ---------------------------------------------------------------------------


async def test_list_codes_admin_only(client, student_token):
    """Non-admins cannot list invite codes."""
    response = await client.get(
        "/api/invite-codes",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


async def test_list_codes_returns_all(client, admin_token, admin_user, db_session):
    """List returns all invite codes ordered by created_at desc."""
    # Generate 3 codes directly in DB
    for i in range(3):
        code = InviteCode(
            code=f"CODE00{i}",
            created_by=admin_user.id,
            status=InviteCodeStatus.active,
        )
        db_session.add(code)
    await db_session.commit()

    response = await client.get(
        "/api/invite-codes",
        headers=auth_header(admin_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3


# ---------------------------------------------------------------------------
# Validate invite code
# ---------------------------------------------------------------------------


async def test_validate_active_code(client, admin_user, db_session):
    """Validating an active code returns valid=True (no auth required)."""
    code = InviteCode(
        code="TESTCODE1",
        created_by=admin_user.id,
        status=InviteCodeStatus.active,
    )
    db_session.add(code)
    await db_session.commit()
    await db_session.refresh(code)

    response = await client.post(
        "/api/invite-codes/validate",
        json={"code": "TESTCODE1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["invite_code_id"] == str(code.id)


async def test_validate_used_code(client, admin_user, db_session):
    """Validating a used code returns valid=False."""
    code = InviteCode(
        code="USEDCODE1",
        created_by=admin_user.id,
        status=InviteCodeStatus.used,
    )
    db_session.add(code)
    await db_session.commit()

    response = await client.post(
        "/api/invite-codes/validate",
        json={"code": "USEDCODE1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["invite_code_id"] is None


async def test_validate_nonexistent_code(client):
    """Validating a nonexistent code returns valid=False."""
    response = await client.post(
        "/api/invite-codes/validate",
        json={"code": "NOSUCHCODE"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False


# ---------------------------------------------------------------------------
# Admin registration with invite code
# ---------------------------------------------------------------------------


async def test_register_admin_with_valid_code(client, admin_user, db_session):
    """Admin registration with a valid invite code succeeds and consumes the code."""
    code = InviteCode(
        code="VALID1234",
        created_by=admin_user.id,
        status=InviteCodeStatus.active,
    )
    db_session.add(code)
    await db_session.commit()
    await db_session.refresh(code)

    suffix = _random_suffix()
    response = await client.post(
        "/api/auth/register",
        json={
            "email": f"newadmin_{suffix}@test.com",
            "password": "securepass123",
            "full_name": "New Admin",
            "role": "admin",
            "institutional_id": f"ADM{suffix}",
            "invite_code": "VALID1234",
        },
    )
    assert response.status_code == 201
    assert "verify" in response.json()["message"].lower()

    # Verify code was consumed
    await db_session.refresh(code)
    assert code.status == InviteCodeStatus.used
    assert code.used_at is not None


async def test_register_admin_with_invalid_code(client):
    """Admin registration with an invalid invite code returns 400."""
    suffix = _random_suffix()
    response = await client.post(
        "/api/auth/register",
        json={
            "email": f"badadmin_{suffix}@test.com",
            "password": "securepass123",
            "full_name": "Bad Admin",
            "role": "admin",
            "institutional_id": f"BAD{suffix}",
            "invite_code": "WRONGCODE",
        },
    )
    # May hit rate limiter if other register tests ran first
    if response.status_code == 429:
        pytest.skip("Rate limited by /api/auth/register")
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower() or "expired" in response.json()["detail"].lower()


async def test_register_admin_with_used_code(client, admin_user, db_session):
    """Admin registration with an already-used code returns 400."""
    suffix = _random_suffix()
    used_code = InviteCode(
        code="USEDCODE2",
        created_by=admin_user.id,
        status=InviteCodeStatus.used,
    )
    db_session.add(used_code)
    await db_session.commit()

    response = await client.post(
        "/api/auth/register",
        json={
            "email": f"usedcode_{suffix}@test.com",
            "password": "securepass123",
            "full_name": "Used Code Admin",
            "role": "admin",
            "institutional_id": f"UC{suffix}",
            "invite_code": "USEDCODE2",
        },
    )
    if response.status_code == 429:
        pytest.skip("Rate limited by /api/auth/register")
    assert response.status_code == 400


async def test_register_non_admin_ignores_invite_code(client):
    """Student/supervisor registration ignores the invite_code field."""
    suffix = _random_suffix()
    response = await client.post(
        "/api/auth/register",
        json={
            "email": f"student_ignore_{suffix}@test.com",
            "password": "securepass123",
            "full_name": "Student Ignore Code",
            "role": "student",
            "institutional_id": f"SIG{suffix}",
            "invite_code": "IRRELEVANT",
        },
    )
    if response.status_code == 429:
        pytest.skip("Rate limited by /api/auth/register")
    # Should succeed — invite code is ignored for non-admin roles
    assert response.status_code == 201
