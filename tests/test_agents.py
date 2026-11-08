import pytest
from httpx import ASGITransport, AsyncClient

from eros.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "flags" in data


@pytest.mark.asyncio
async def test_analyze_sql_injection(client):
    payload = {
        "code": 'def get_user(user_id): return db.execute(f"SELECT * FROM users WHERE id={user_id}")',
        "language": "python",
    }
    response = await client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ("HIGH", "CRITICAL")
    assert len(data["findings"]) > 0
    assert "security_agent" in data["agents_executed"]


@pytest.mark.asyncio
async def test_analyze_clean_code(client):
    payload = {
        "code": "def add(a: int, b: int) -> int:\n    return a + b",
        "language": "python",
    }
    response = await client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "LOW"


@pytest.mark.asyncio
async def test_flags_toggle(client):
    # Enable auto patch
    await client.post("/flags/auto_patch_generation", params={"value": "true"})
    response = await client.get("/flags")
    assert response.json()["flags"]["auto_patch_generation"] is True

    # Reset
    await client.post("/flags/auto_patch_generation", params={"value": "false"})
