import pytest
from httpx import ASGITransport, AsyncClient

from eros.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def reset_flags():
    """Reset feature flags before each test."""
    from eros.config.feature_flags import FeatureFlag, FeatureFlags

    for flag in FeatureFlag:
        FeatureFlags.clear_override(flag)
    yield
    for flag in FeatureFlag:
        FeatureFlags.clear_override(flag)
