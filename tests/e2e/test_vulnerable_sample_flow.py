import pytest


@pytest.mark.asyncio
async def test_e2e_001_vulnerable_sample(client):
    """TEST-E2E-001: Full vulnerable sample flow."""
    vulnerable_code = '''password = "admin123"
api_key = "sk-1234567890abcdef"

def get_user(user_id):
    return db.execute(f"SELECT * FROM users WHERE id={user_id}")

def run_command(cmd):
    import os
    os.system(cmd)

def load_data():
    import pickle
    data = pickle.loads(user_input)
'''
    response = await client.post("/analyze", json={"code": vulnerable_code, "language": "python"})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ("HIGH", "CRITICAL")
    assert len(data["findings"]) >= 3
    assert "security_agent" in data["agents_executed"]
    assert "compliance_agent" in data["agents_executed"]


@pytest.mark.asyncio
async def test_e2e_002_flag_governance(client):
    """TEST-E2E-002: Feature flag changes behavior."""
    code = 'password = "admin123"\ndef get_user(uid): return db.execute(f"SELECT * FROM users WHERE id={uid}")'

    # Strict OFF
    await client.post("/flags/strict_compliance_mode", params={"value": "false"})
    r1 = await client.post("/analyze", json={"code": code, "language": "python"})
    findings_normal = len(r1.json()["findings"])

    # Strict ON
    await client.post("/flags/strict_compliance_mode", params={"value": "true"})
    r2 = await client.post("/analyze", json={"code": code, "language": "python"})
    findings_strict = len(r2.json()["findings"])

    assert findings_strict >= findings_normal
    assert r2.json()["risk_level"] in ("HIGH", "CRITICAL")
