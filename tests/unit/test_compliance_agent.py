import pytest

from eros.agents.compliance_agent import ComplianceAgent
from eros.config.feature_flags import FeatureFlag, FeatureFlags


@pytest.mark.asyncio
async def test_cmp_001_strict_off():
    """TEST-CMP-001: Strict OFF → warnings."""
    FeatureFlags.clear_override(FeatureFlag.STRICT_COMPLIANCE_MODE)
    agent = ComplianceAgent()
    code = 'api_key = "secret"'
    findings = await agent.analyze(code, "python")
    # In non-strict mode, OWASP rules still fire but as HIGH
    for f in findings:
        assert f.severity.value in ("HIGH", "MEDIUM", "LOW")


@pytest.mark.asyncio
async def test_cmp_002_strict_on():
    """TEST-CMP-002: Strict ON → critical."""
    FeatureFlags.set_override(FeatureFlag.STRICT_COMPLIANCE_MODE, True)
    agent = ComplianceAgent()
    code = 'password = "secret123"'
    findings = await agent.analyze(code, "python")
    assert any(f.severity.value == "CRITICAL" for f in findings)


@pytest.mark.asyncio
async def test_cmp_003_clean_code():
    """TEST-CMP-003: Clean code → pass."""
    agent = ComplianceAgent()
    code = "def add(a, b):\n    return a + b"
    findings = await agent.analyze(code, "python")
    assert len(findings) == 0
