"""
Unit tests for AgentRegistry component.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from eros import (
    AgentRegistry,
    AgentMetadata,
    AgentType,
    AgentStatus,
    HealthCheck,
    HTTPHealthCheck,
    get_registry,
    close_registry,
)


class MockHealthCheck(HealthCheck):
    """Mock health check for testing."""
    
    def __init__(self, should_pass: bool = True):
        self.should_pass = should_pass
        self.call_count = 0
    
    async def check(self, agent: AgentMetadata) -> bool:
        self.call_count += 1
        return self.should_pass


@pytest.fixture
async def registry():
    """Create a fresh registry for each test."""
    reg = AgentRegistry()
    await reg.start()
    yield reg
    await reg.stop()


@pytest.fixture
async def clean_registry():
    """Ensure registry is clean before and after test."""
    await close_registry()
    yield
    await close_registry()


class TestAgentRegistry:
    """Test AgentRegistry functionality."""
    
    @pytest.mark.asyncio
    async def test_register_agent(self, registry):
        """Test agent registration."""
        agent_id = await registry.register(
            name="TestAgent",
            agent_type=AgentType.SENTRY,
            endpoint="http://test:8080",
            capabilities=["cap1", "cap2"],
        )
        
        assert agent_id is not None
        assert len(agent_id) == 8
        
        agent = await registry.get(agent_id)
        assert agent is not None
        assert agent.name == "TestAgent"
        assert agent.agent_type == AgentType.SENTRY
        assert agent.endpoint == "http://test:8080"
        assert agent.capabilities == ["cap1", "cap2"]
        assert agent.status == AgentStatus.REGISTERED
    
    @pytest.mark.asyncio
    async def test_register_without_endpoint(self, registry):
        """Test registration without endpoint."""
        agent_id = await registry.register(
            name="NoEndpointAgent",
            agent_type=AgentType.ROUTER,
        )
        
        agent = await registry.get(agent_id)
        assert agent.endpoint is None
    
    @pytest.mark.asyncio
    async def test_unregister_agent(self, registry):
        """Test agent unregistration."""
        agent_id = await registry.register(
            name="ToRemove",
            agent_type=AgentType.GUARDRAIL,
        )
        
        result = await registry.unregister(agent_id)
        assert result is True
        
        agent = await registry.get(agent_id)
        assert agent is None
    
    @pytest.mark.asyncio
    async def test_unregister_nonexistent(self, registry):
        """Test unregistering non-existent agent."""
        result = await registry.unregister("nonexistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_list_agents(self, registry):
        """Test listing all agents."""
        await registry.register("Agent1", AgentType.SENTRY)
        await registry.register("Agent2", AgentType.ROUTER)
        await registry.register("Agent3", AgentType.WAR_ROOM)
        
        agents = await registry.list()
        assert len(agents) == 3
    
    @pytest.mark.asyncio
    async def test_list_agents_by_type(self, registry):
        """Test listing agents filtered by type."""
        await registry.register("Sentry1", AgentType.SENTRY)
        await registry.register("Sentry2", AgentType.SENTRY)
        await registry.register("Router1", AgentType.ROUTER)
        
        sentries = await registry.list(AgentType.SENTRY)
        assert len(sentries) == 2
        
        routers = await registry.list(AgentType.ROUTER)
        assert len(routers) == 1
    
    @pytest.mark.asyncio
    async def test_max_agents_limit(self, registry):
        """Test max agents limit is enforced."""
        # Register up to max
        for i in range(registry.max_agents):
            await registry.register(f"Agent{i}", AgentType.SENTRY)
        
        # Next should fail
        with pytest.raises(RuntimeError, match="Agent limit reached"):
            await registry.register("Overflow", AgentType.SENTRY)
    
    @pytest.mark.asyncio
    async def test_update_status(self, registry):
        """Test updating agent status."""
        agent_id = await registry.register("StatusTest", AgentType.SENTRY)
        
        result = await registry.update_status(agent_id, AgentStatus.HEALTHY)
        assert result is True
        
        agent = await registry.get(agent_id)
        assert agent.status == AgentStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_heartbeat(self, registry):
        """Test agent heartbeat."""
        agent_id = await registry.register("HeartbeatTest", AgentType.SENTRY)
        
        # Initial heartbeat
        result = await registry.heartbeat(agent_id)
        assert result is True
        
        agent = await registry.get(agent_id)
        assert agent.last_heartbeat is not None
        assert agent.health_check_failures == 0
    
    @pytest.mark.asyncio
    async def test_health_check_callback(self, registry):
        """Test health check callback registration."""
        callback_called = []
        
        def callback(agent, healthy):
            callback_called.append((agent.agent_id, healthy))
        
        registry.on_health_change(callback)
        
        # Register with failing health check
        failing_check = MockHealthCheck(should_pass=False)
        agent_id = await registry.register(
            "FailingAgent",
            AgentType.SENTRY,
            health_check=failing_check,
        )
        
        # Manually trigger health check
        await registry._run_health_checks()
        
        # Should have been called
        assert len(callback_called) > 0
    
    @pytest.mark.asyncio
    async def test_get_stats(self, registry):
        """Test registry statistics."""
        await registry.register("StatAgent1", AgentType.SENTRY)
        await registry.register("StatAgent2", AgentType.ROUTER)
        
        stats = registry.get_stats()
        
        assert stats["total_agents"] == 2
        assert stats["by_type"]["sentry"] == 1
        assert stats["by_type"]["router"] == 1
        assert "mode" in stats
    
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test registry start/stop lifecycle."""
        reg = AgentRegistry()
        assert not reg._running
        
        await reg.start()
        assert reg._running
        
        await reg.stop()
        assert not reg._running


class TestAgentMetadata:
    """Test AgentMetadata dataclass."""
    
    def test_metadata_creation(self):
        """Test metadata creation with all fields."""
        meta = AgentMetadata(
            agent_id="test123",
            name="TestAgent",
            agent_type=AgentType.SENTRY,
            endpoint="http://test:8080",
            capabilities=["cap1"],
            metadata={"key": "value"},
        )
        
        assert meta.agent_id == "test123"
        assert meta.name == "TestAgent"
        assert meta.agent_type == AgentType.SENTRY
        assert meta.endpoint == "http://test:8080"
        assert meta.capabilities == ["cap1"]
        assert meta.metadata == {"key": "value"}
        assert meta.status == AgentStatus.REGISTERED
        assert meta.health_check_failures == 0


class TestHTTPHealthCheck:
    """Test HTTPHealthCheck."""
    
    @pytest.mark.asyncio
    async def test_check_no_endpoint(self):
        """Test check with agent without endpoint."""
        check = HTTPHealthCheck()
        agent = AgentMetadata(
            agent_id="test",
            name="Test",
            agent_type=AgentType.SENTRY,
        )
        
        result = await check.check(agent)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_timeout(self):
        """Test check with timeout configuration."""
        check = HTTPHealthCheck(timeout_sec=0.1)
        assert check.timeout_sec == 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])