from app.models.assignment import AssignmentType, SupervisorAssignment
from tests.conftest import auth_header


async def test_get_academic_supervisor_returns_assigned(
    client, student_user, student_token, supervisor_user, db_session
):
    """Student with a primary supervisor gets their info returned."""
    assignment = SupervisorAssignment(
        supervisor_id=supervisor_user.id,
        student_id=student_user.id,
        assignment_type=AssignmentType.primary,
    )
    db_session.add(assignment)
    await db_session.commit()

    response = await client.get(
        "/api/students/me/academic-supervisor",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["supervisor"] is not None
    assert data["supervisor"]["id"] == str(supervisor_user.id)
    assert "full_name" in data["supervisor"]


async def test_get_academic_supervisor_returns_null_when_none(client, student_token):
    """Student with no primary supervisor gets supervisor: null."""
    response = await client.get(
        "/api/students/me/academic-supervisor",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["supervisor"] is None


async def test_get_academic_supervisor_requires_student_role(client, supervisor_token):
    """Non-student users get 403."""
    response = await client.get(
        "/api/students/me/academic-supervisor",
        headers=auth_header(supervisor_token),
    )
    assert response.status_code == 403


async def test_get_academic_supervisor_requires_auth(client):
    """Unauthenticated request returns 401."""
    response = await client.get("/api/students/me/academic-supervisor")
    assert response.status_code == 401
