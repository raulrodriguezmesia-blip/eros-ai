"""
aegis-lite StressTest
Load testing, fault injection, and chaos engineering for agent systems.
Configuration driven by RigorMode.
"""

from __future__ import annotations
import asyncio
import random
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict

from .rigor import get_rigor_mode, StressTestConfig
from .agent_registry import AgentStatus, get_registry

logger = logging.getLogger(__name__)


class StressScenario(Enum):
    LOAD = "load"
    LATENCY = "latency"
    FAULT_INJECTION = "fault_injection"
    CHAOS = "chaos"
    SOAK = "soak"
    SPIKE = "spike"


class FaultType(Enum):
    NETWORK_DELAY = "network_delay"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    AGENT_CRASH = "agent_crash"
    HIGH_LATENCY = "high_latency"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


@dataclass
class StressResult:
    scenario: StressScenario
    start_time: datetime
    end_time: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    max_latency_ms: float
    min_latency_ms: float
    throughput_rps: float
    error_rate: float
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    sla_violations: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAThresholds:
    p99_latency_ms: float = 500
    error_rate: float = 0.001
    throughput_rps: float = 1000


class LoadGenerator(ABC):
    """Abstract load generator."""
    
    @abstractmethod
    async def generate_load(
        self,
        target: Callable,
        concurrent: int,
        duration_sec: int,
        ramp_up_sec: int = 0,
    ) -> List[Dict[str, Any]]:
        pass


class SimpleLoadGenerator(LoadGenerator):
    """Simple concurrent load generator."""
    
    async def generate_load(
        self,
        target: Callable,
        concurrent: int,
        duration_sec: int,
        ramp_up_sec: int = 0,
    ) -> List[Dict[str, Any]]:
        results = []
        semaphore = asyncio.Semaphore(concurrent)
        start_time = time.time()
        end_time = start_time + duration_sec
        
        async def worker(worker_id: int):
            # Ramp up delay
            if ramp_up_sec > 0:
                delay = random.uniform(0, ramp_up_sec)
                await asyncio.sleep(delay)
            
            while time.time() < end_time:
                async with semaphore:
                    request_start = time.time()
                    try:
                        result = await target()
                        latency_ms = (time.time() - request_start) * 1000
                        results.append({
                            "worker_id": worker_id,
                            "timestamp": request_start,
                            "latency_ms": latency_ms,
                            "success": True,
                            "result": result,
                        })
                    except Exception as e:
                        latency_ms = (time.time() - request_start) * 1000
                        results.append({
                            "worker_id": worker_id,
                            "timestamp": request_start,
                            "latency_ms": latency_ms,
                            "success": False,
                            "error": str(e),
                        })
                
                # Small delay to prevent tight loop
                await asyncio.sleep(0.001)
        
        tasks = [worker(i) for i in range(concurrent)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results


class FaultInjector:
    """Injects faults into the system for chaos testing."""
    
    def __init__(self):
        self._active_faults: Dict[str, Dict[str, Any]] = {}
        self._fault_probability: Dict[FaultType, float] = {}
    
    def set_fault_probability(self, fault_type: FaultType, probability: float) -> None:
        self._fault_probability[fault_type] = max(0.0, min(1.0, probability))
    
    async def maybe_inject(self, fault_type: FaultType, context: Dict[str, Any]) -> bool:
        """Randomly inject fault based on probability."""
        prob = self._fault_probability.get(fault_type, 0.0)
        if prob <= 0 or random.random() > prob:
            return False
        
        return await self._inject_fault(fault_type, context)
    
    async def _inject_fault(self, fault_type: FaultType, context: Dict[str, Any]) -> bool:
        """Inject specific fault type."""
        try:
            if fault_type == FaultType.NETWORK_DELAY:
                delay = random.uniform(0.1, 2.0)
                await asyncio.sleep(delay)
                logger.warning(f"Injected network delay: {delay:.2f}s")
            
            elif fault_type == FaultType.NETWORK_ERROR:
                raise ConnectionError("Injected network error")
            
            elif fault_type == FaultType.TIMEOUT:
                await asyncio.sleep(10)  # Longer than typical timeout
            
            elif fault_type == FaultType.AGENT_CRASH:
                agent_id = context.get("agent_id")
                if agent_id:
                    registry = await get_registry()
                    await registry.update_status(agent_id, AgentStatus.UNHEALTHY)
                    logger.warning(f"Injected agent crash: {agent_id}")
            
            elif fault_type == FaultType.HIGH_LATENCY:
                await asyncio.sleep(random.uniform(1.0, 5.0))
            
            elif fault_type == FaultType.RESOURCE_EXHAUSTION:
                # Simulate memory/CPU pressure
                await asyncio.sleep(0.5)
            
            return True
        except Exception as e:
            logger.error(f"Fault injection failed: {e}")
            return False


class StressTest:
    """
    Comprehensive stress testing framework.
    Supports load, latency, fault injection, chaos, soak, and spike scenarios.
    """
    
    def __init__(self, config: Optional[StressTestConfig] = None):
        self._config = config or get_rigor_mode().get_stress_test_config()
        self._load_generator = SimpleLoadGenerator()
        self._fault_injector = FaultInjector()
        self._sla_thresholds = SLAThresholds(**self._config.sla_thresholds)
        self._results: List[StressResult] = []
        self._running = False
    
    @property
    def config(self) -> StressTestConfig:
        return self._config
    
    async def run_scenario(
        self,
        scenario: StressScenario,
        target: Callable,
        custom_params: Optional[Dict[str, Any]] = None,
    ) -> StressResult:
        """Run a specific stress scenario."""
        params = custom_params or {}
        concurrent = params.get("concurrent", self._config.max_concurrent)
        duration = params.get("duration_sec", self._config.duration_sec)
        ramp_up = params.get("ramp_up_sec", self._config.ramp_up_sec)
        
        logger.info(f"Starting stress scenario: {scenario.value} (concurrent={concurrent}, duration={duration}s)")
        
        self._running = True
        start_time = datetime.now(UTC)
        
        # Configure fault injection for this scenario
        self._configure_faults(scenario)
        
        # Wrap target with fault injection
        async def fault_wrapped_target(*args, **kwargs):
            await self._fault_injector.maybe_inject(FaultType.NETWORK_DELAY, kwargs)
            await self._fault_injector.maybe_inject(FaultType.NETWORK_ERROR, kwargs)
            return await target(*args, **kwargs)
        
        # Generate load
        raw_results = await self._load_generator.generate_load(
            fault_wrapped_target,
            concurrent=concurrent,
            duration_sec=duration,
            ramp_up_sec=ramp_up,
        )
        
        end_time = datetime.now(UTC)
        
        # Analyze results
        result = self._analyze_results(scenario, start_time, end_time, raw_results)
        self._results.append(result)
        
        self._running = False
        logger.info(f"Completed stress scenario: {scenario.value} - "
                   f"success_rate={(result.successful_requests/result.total_requests*100):.1f}%, "
                   f"p99={result.latency_p99_ms:.1f}ms, throughput={result.throughput_rps:.1f} rps")
        
        return result
    
    def _configure_faults(self, scenario: StressScenario) -> None:
        """Configure fault injection probabilities per scenario."""
        self._fault_injector._fault_probability.clear()
        
        if scenario in (StressScenario.FAULT_INJECTION, StressScenario.CHAOS):
            self._fault_injector.set_fault_probability(FaultType.NETWORK_DELAY, 0.1)
            self._fault_injector.set_fault_probability(FaultType.NETWORK_ERROR, 0.05)
            self._fault_injector.set_fault_probability(FaultType.TIMEOUT, 0.02)
        
        if scenario == StressScenario.CHAOS:
            self._fault_injector.set_fault_probability(FaultType.AGENT_CRASH, 0.01)
            self._fault_injector.set_fault_probability(FaultType.HIGH_LATENCY, 0.1)
            self._fault_injector.set_fault_probability(FaultType.RESOURCE_EXHAUSTION, 0.05)
        
        if scenario == StressScenario.SPIKE:
            # Spike scenario handled by load generator pattern
            pass
    
    def _analyze_results(
        self,
        scenario: StressScenario,
        start_time: datetime,
        end_time: datetime,
        raw_results: List[Dict[str, Any]],
    ) -> StressResult:
        if not raw_results:
            return StressResult(
                scenario=scenario,
                start_time=start_time,
                end_time=end_time,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                latency_p50_ms=0,
                latency_p95_ms=0,
                latency_p99_ms=0,
                max_latency_ms=0,
                min_latency_ms=0,
                throughput_rps=0,
                error_rate=0,
            )
        
        successful = [r for r in raw_results if r["success"]]
        failed = [r for r in raw_results if not r["success"]]
        latencies = [r["latency_ms"] for r in successful]
        
        total_requests = len(raw_results)
        duration_sec = (end_time - start_time).total_seconds()
        
        # Calculate percentiles
        latencies_sorted = sorted(latencies) if latencies else [0]
        
        def percentile(p: float) -> float:
            if not latencies_sorted:
                return 0
            idx = int(len(latencies_sorted) * p / 100)
            return latencies_sorted[min(idx, len(latencies_sorted) - 1)]
        
        # Error categorization
        errors_by_type = defaultdict(int)
        for r in failed:
            error = r.get("error", "unknown")
            errors_by_type[error] += 1
        
        # SLA violations
        sla_violations = []
        if percentile(99) > self._sla_thresholds.p99_latency_ms:
            sla_violations.append({
                "metric": "p99_latency_ms",
                "threshold": self._sla_thresholds.p99_latency_ms,
                "actual": percentile(99),
            })
        
        error_rate = len(failed) / total_requests if total_requests > 0 else 0
        if error_rate > self._sla_thresholds.error_rate:
            sla_violations.append({
                "metric": "error_rate",
                "threshold": self._sla_thresholds.error_rate,
                "actual": error_rate,
            })
        
        throughput = total_requests / duration_sec if duration_sec > 0 else 0
        if throughput < self._sla_thresholds.throughput_rps:
            sla_violations.append({
                "metric": "throughput_rps",
                "threshold": self._sla_thresholds.throughput_rps,
                "actual": throughput,
            })
        
        return StressResult(
            scenario=scenario,
            start_time=start_time,
            end_time=end_time,
            total_requests=total_requests,
            successful_requests=len(successful),
            failed_requests=len(failed),
            latency_p50_ms=percentile(50),
            latency_p95_ms=percentile(95),
            latency_p99_ms=percentile(99),
            max_latency_ms=max(latencies_sorted) if latencies_sorted else 0,
            min_latency_ms=min(latencies_sorted) if latencies_sorted else 0,
            throughput_rps=throughput,
            error_rate=error_rate,
            errors_by_type=dict(errors_by_type),
            sla_violations=sla_violations,
        )
    
    async def run_all_scenarios(self, target: Callable) -> List[StressResult]:
        """Run all configured scenarios."""
        results = []
        for scenario_name in self._config.scenarios:
            try:
                scenario = StressScenario(scenario_name)
                result = await self.run_scenario(scenario, target)
                results.append(result)
            except ValueError:
                logger.warning(f"Unknown scenario: {scenario_name}")
        return results
    
    def get_results(self) -> List[StressResult]:
        return self._results.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        if not self._results:
            return {"scenarios_run": 0}
        
        return {
            "scenarios_run": len(self._results),
            "total_requests": sum(r.total_requests for r in self._results),
            "total_successful": sum(r.successful_requests for r in self._results),
            "total_failed": sum(r.failed_requests for r in self._results),
            "overall_error_rate": sum(r.failed_requests for r in self._results) / 
                                  sum(r.total_requests for r in self._results) if self._results else 0,
            "scenarios": {
                r.scenario.value: {
                    "success_rate": r.successful_requests / r.total_requests if r.total_requests > 0 else 0,
                    "p99_latency_ms": r.latency_p99_ms,
                    "throughput_rps": r.throughput_rps,
                    "sla_violations": len(r.sla_violations),
                }
                for r in self._results
            },
        }


# Global stress test instance
_stress_test: Optional[StressTest] = None


def get_stress_test(config: Optional[StressTestConfig] = None) -> StressTest:
    """Get or create the global StressTest instance."""
    global _stress_test
    if _stress_test is None:
        _stress_test = StressTest(config)
    return _stress_test


def set_stress_test(test: StressTest) -> None:
    """Set the global StressTest instance (for testing)."""
    global _stress_test
    _stress_test = test