import pytest


@pytest.mark.asyncio
async def test_api_001_health(client):
    """TEST-API-001: Health endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "flags" in data


@pytest.mark.asyncio
async def test_api_002_flags(client):
    """TEST-API-002: Flags endpoint."""
    response = await client.get("/flags")
    assert response.status_code == 200
    data = response.json()
    assert "flags" in data
    assert "deep_ast_analysis" in data["flags"]


@pytest.mark.asyncio
async def test_api_003_toggle(client):
    """TEST-API-003: Toggle flag."""
    response = await client.post("/flags/strict_compliance_mode", params={"value": "true"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"

    response = await client.get("/flags")
    assert response.json()["flags"]["strict_compliance_mode"] is True


@pytest.mark.asyncio
async def test_api_004_analyze(client):
    """TEST-API-004: Analyze endpoint."""
    payload = {
        "code": 'password = "admin123"\ndef get_user(uid): return db.execute(f"SELECT * FROM users WHERE id={uid}")',
        "language": "python",
    }
    response = await client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "findings" in data
    assert "risk_level" in data
    assert len(data["findings"]) > 0
