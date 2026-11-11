"""
aegis-lite AgentRegistry
Central registry for agent discovery, health monitoring, and lifecycle management.
Respects RigorMode configuration for scope control.
"""

from __future__ import annotations
import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import logging

from .rigor import get_rigor_mode, AgentRegistryConfig

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    REGISTERED = "registered"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class AgentType(Enum):
    SENTRY = "sentry"           # Edge agent
    ROUTER = "router"           # Confidence router
    WAR_ROOM = "war_room"       # Cloud agent
    GUARDRAIL = "guardrail"     # Safety guardrail
    TRACER = "tracer"           # Reasoning trace


@dataclass
class AgentMetadata:
    agent_id: str
    name: str
    agent_type: AgentType
    endpoint: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat: Optional[datetime] = None
    status: AgentStatus = AgentStatus.REGISTERED
    health_check_failures: int = 0


class HealthCheck(ABC):
    """Abstract health check for agents."""
    
    @abstractmethod
    async def check(self, agent: AgentMetadata) -> bool:
        """Return True if healthy, False otherwise."""
        pass


class HTTPHealthCheck(HealthCheck):
    """HTTP-based health check."""
    
    def __init__(self, timeout_sec: float = 5.0):
        self.timeout_sec = timeout_sec
    
    async def check(self, agent: AgentMetadata) -> bool:
        if not agent.endpoint:
            return False
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_sec)) as session:
                async with session.get(f"{agent.endpoint}/health") as resp:
                    return resp.status == 200
        except Exception:
            return False


class AgentRegistry:
    """
    Thread-safe agent registry with health monitoring.
    Configuration driven by RigorMode (demo/standard/enterprise).
    """
    
    def __init__(self, config: Optional[AgentRegistryConfig] = None):
        self._config = config or get_rigor_mode().get_agent_registry_config()
        self._agents: Dict[str, AgentMetadata] = {}
        self._type_index: Dict[AgentType, Set[str]] = {t: set() for t in AgentType}
        self._lock = asyncio.Lock()
        self._health_checks: Dict[str, HealthCheck] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {
            "register": [],
            "unregister": [],
            "status_change": [],
            "health_change": [],
        }
    
    @property
    def max_agents(self) -> int:
        return self._config.max_agents
    
    @property
    def agent_count(self) -> int:
        return len(self._agents)
    
    async def start(self) -> None:
        """Start the registry and health monitoring."""
        if self._running:
            return
        self._running = True
        self._monitor_task = asyncio.create_task(self._health_monitor_loop())
        logger.info(f"AgentRegistry started (mode: {get_rigor_mode().mode}, max_agents: {self.max_agents})")
    
    async def stop(self) -> None:
        """Stop the registry and health monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Gracefully shutdown all agents
        for agent_id in list(self._agents.keys()):
            await self.unregister(agent_id)
        
        logger.info("AgentRegistry stopped")
    
    async def register(
        self,
        name: str,
        agent_type: AgentType,
        endpoint: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        health_check: Optional[HealthCheck] = None,
    ) -> str:
        """Register a new agent. Returns agent_id."""
        async with self._lock:
            if len(self._agents) >= self.max_agents:
                raise RuntimeError(f"Agent limit reached: {self.max_agents}")
            
            agent_id = str(uuid.uuid4())[:8]
            agent = AgentMetadata(
                agent_id=agent_id,
                name=name,
                agent_type=agent_type,
                endpoint=endpoint,
                capabilities=capabilities or [],
                metadata=metadata or {},
                status=AgentStatus.REGISTERED,
            )
            
            self._agents[agent_id] = agent
            self._type_index[agent_type].add(agent_id)
            
            if health_check:
                self._health_checks[agent_id] = health_check
            elif endpoint:
                self._health_checks[agent_id] = HTTPHealthCheck()
            
            # Trigger callbacks
            for cb in self._callbacks["register"]:
                try:
                    await cb(agent) if asyncio.iscoroutinefunction(cb) else cb(agent)
                except Exception as e:
                    logger.warning(f"Register callback failed: {e}")
            
            logger.info(f"Agent registered: {agent_id} ({name}, type={agent_type.value})")
            return agent_id
    
    async def unregister(self, agent_id: str) -> bool:
        """Unregister an agent."""
        async with self._lock:
            agent = self._agents.pop(agent_id, None)
            if not agent:
                return False
            
            self._type_index[agent.agent_type].discard(agent_id)
            self._health_checks.pop(agent_id, None)
            
            agent.status = AgentStatus.TERMINATED
            
            for cb in self._callbacks["unregister"]:
                try:
                    await cb(agent) if asyncio.iscoroutinefunction(cb) else cb(agent)
                except Exception as e:
                    logger.warning(f"Unregister callback failed: {e}")
            
            logger.info(f"Agent unregistered: {agent_id}")
            return True
    
    async def get(self, agent_id: str) -> Optional[AgentMetadata]:
        """Get agent by ID."""
        return self._agents.get(agent_id)
    
    async def list(self, agent_type: Optional[AgentType] = None) -> List[AgentMetadata]:
        """List all agents, optionally filtered by type."""
        if agent_type:
            ids = self._type_index.get(agent_type, set())
            return [self._agents[aid] for aid in ids if aid in self._agents]
        return list(self._agents.values())
    
    async def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        """Update agent status."""
        async with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False
            
            old_status = agent.status
            agent.status = status
            
            if old_status != status:
                for cb in self._callbacks["status_change"]:
                    try:
                        await cb(agent, old_status, status) if asyncio.iscoroutinefunction(cb) else cb(agent, old_status, status)
                    except Exception as e:
                        logger.warning(f"Status change callback failed: {e}")
            return True
    
    async def heartbeat(self, agent_id: str) -> bool:
        """Record agent heartbeat."""
        async with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False
            agent.last_heartbeat = datetime.now(UTC)
            agent.health_check_failures = 0
            if agent.status == AgentStatus.UNHEALTHY:
                await self.update_status(agent_id, AgentStatus.HEALTHY)
            return True
    
    def on_register(self, callback: Callable) -> None:
        self._callbacks["register"].append(callback)
    
    def on_unregister(self, callback: Callable) -> None:
        self._callbacks["unregister"].append(callback)
    
    def on_status_change(self, callback: Callable) -> None:
        self._callbacks["status_change"].append(callback)
    
    def on_health_change(self, callback: Callable) -> None:
        self._callbacks["health_change"].append(callback)
    
    async def _health_monitor_loop(self) -> None:
        """Background health monitoring loop."""
        while self._running:
            try:
                await self._run_health_checks()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
            await asyncio.sleep(self._config.health_check_interval_sec)
    
    async def _run_health_checks(self) -> None:
        """Run health checks on all registered agents."""
        async with self._lock:
            agents_to_check = list(self._agents.items())
        
        for agent_id, agent in agents_to_check:
            if agent.status in (AgentStatus.SHUTTING_DOWN, AgentStatus.TERMINATED):
                continue
            
            health_check = self._health_checks.get(agent_id)
            if not health_check:
                continue
            
            try:
                healthy = await health_check.check(agent)
                async with self._lock:
                    agent = self._agents.get(agent_id)
                    if not agent:
                        continue
                    
                    # Always fire health_change callback with current health status
                    for cb in self._callbacks["health_change"]:
                        try:
                            await cb(agent, healthy) if asyncio.iscoroutinefunction(cb) else cb(agent, healthy)
                        except Exception:
                            pass
                    
                    if healthy:
                        agent.health_check_failures = 0
                        if agent.status != AgentStatus.HEALTHY:
                            await self.update_status(agent_id, AgentStatus.HEALTHY)
                    else:
                        agent.health_check_failures += 1
                        if agent.health_check_failures >= 3:
                            await self.update_status(agent_id, AgentStatus.UNHEALTHY)
            except Exception as e:
                logger.warning(f"Health check failed for {agent_id}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        status_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        
        for agent in self._agents.values():
            status_counts[agent.status.value] = status_counts.get(agent.status.value, 0) + 1
            type_counts[agent.agent_type.value] = type_counts.get(agent.agent_type.value, 0) + 1
        
        return {
            "total_agents": len(self._agents),
            "max_agents": self.max_agents,
            "by_status": status_counts,
            "by_type": type_counts,
            "mode": get_rigor_mode().mode,
        }


# Global registry instance
_registry: Optional[AgentRegistry] = None


async def get_registry(config: Optional[AgentRegistryConfig] = None) -> AgentRegistry:
    """Get or create the global AgentRegistry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry(config)
        await _registry.start()
    return _registry


async def close_registry() -> None:
    """Close the global AgentRegistry instance."""
    global _registry
    if _registry:
        await _registry.stop()
        _registry = None