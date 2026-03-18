

async def test_health_check(client):
    """Health endpoint should return 200 with status ok."""
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data
