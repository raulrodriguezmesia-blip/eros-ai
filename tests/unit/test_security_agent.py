import pytest

from eros.agents.security_agent import SecurityAgent


@pytest.mark.asyncio
async def test_sec_001_sql_injection():
    """TEST-SEC-001: Detect SQL Injection."""
    agent = SecurityAgent()
    code = 'query = f"SELECT * FROM users WHERE id = {user_id}"'
    findings = await agent.analyze(code, "python")
    assert len(findings) >= 1
    assert any(f.severity.value == "CRITICAL" for f in findings)
    assert any("sql" in f.description.lower() or "injection" in f.description.lower() for f in findings)


@pytest.mark.asyncio
async def test_sec_002_hardcoded_secret():
    """TEST-SEC-002: Detect Hardcoded Secret."""
    agent = SecurityAgent()
    code = 'password = "admin123"'
    findings = await agent.analyze(code, "python")
    assert len(findings) >= 1
    assert any(f.cwe == "CWE-798" for f in findings)


@pytest.mark.asyncio
async def test_sec_003_command_injection():
    """TEST-SEC-003: Detect Command Injection."""
    agent = SecurityAgent()
    code = "os.system(user_input)"
    findings = await agent.analyze(code, "python")
    assert len(findings) >= 1
    assert any("command" in f.description.lower() or f.cwe == "CWE-78" for f in findings)


@pytest.mark.asyncio
async def test_sec_004_clean_code():
    """TEST-SEC-004: Clean code returns no findings."""
    agent = SecurityAgent()
    code = "def add(a, b):\n    return a + b"
    findings = await agent.analyze(code, "python")
    assert len(findings) == 0
