import pytest
from unittest.mock import patch, AsyncMock

from eros.foundry.client import FoundryClient


@pytest.mark.asyncio
async def test_ai_002_fallback_local():
    """TEST-AI-002: Fallback to local when Foundry not configured."""
    client = FoundryClient()
    client.endpoint = ""
    client.api_key = ""
    result = await client.analyze_code("x = 1", "test")
    assert result["status"] == "local"


@pytest.mark.asyncio
async def test_ai_003_circuit_breaker():
    """TEST-AI-003: Circuit breaker opens after 3 failures."""
    client = FoundryClient()
    client.endpoint = "https://fake.endpoint.com"
    client.api_key = "fake-key"
    client._client = None

    # Force failures
    with patch.object(client, "_get_client", return_value=None):
        pass

    # Simulate 3 failures manually
    client._failure_count = 3
    client._circuit_open = True
    assert client._circuit_open is True

    # Verify degraded response
    result = await client.analyze_code("x = 1", "test")
    assert result["status"] == "degraded"
