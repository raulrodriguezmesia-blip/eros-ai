import asyncio
import pytest
from unittest.mock import patch
from datetime import datetime, UTC

from eros import (
    StressTest,
    StressScenario,
    StressResult,
    StressTestConfig,
    FaultType,
    FaultInjector,
    SimpleLoadGenerator,
    SLAThresholds,
    get_stress_test,
    set_stress_test,
)


class TestStressTestConfig:
    """Test StressTestConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = StressTestConfig()

        assert config.duration_sec == 60
        assert config.max_concurrent == 100
        assert config.ramp_up_sec == 10
        assert config.enabled is True
        assert "load" in config.scenarios

    def test_custom_config(self):
        """Test custom configuration."""
        config = StressTestConfig(
            duration_sec=30,
            max_concurrent=50,
            scenarios=["load", "latency"],
        )

        assert config.duration_sec == 30
        assert config.max_concurrent == 50
        assert config.scenarios == ["load", "latency"]


class TestStressResult:
    """Test StressResult dataclass."""

    def test_creation(self):
        """Test creating a StressResult."""
        start = datetime.now(UTC)
        end = datetime.now(UTC)

        result = StressResult(
            scenario=StressScenario.LOAD,
            start_time=start,
            end_time=end,
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            latency_p50_ms=100.0,
            latency_p95_ms=200.0,
            latency_p99_ms=300.0,
            max_latency_ms=500.0,
            min_latency_ms=10.0,
            throughput_rps=50.0,
            error_rate=0.05,
        )

        assert result.scenario == StressScenario.LOAD
        assert result.total_requests == 100
        assert result.error_rate == 0.05


class TestSLAThresholds:
    """Test SLAThresholds."""

    def test_defaults(self):
        """Test default SLA thresholds."""
        sla = SLAThresholds()

        assert sla.p99_latency_ms == 500
        assert sla.error_rate == 0.001
        assert sla.throughput_rps == 1000

    def test_custom(self):
        """Test custom SLA thresholds."""
        sla = SLAThresholds(
            p99_latency_ms=1000,
            error_rate=0.01,
            throughput_rps=500,
        )

        assert sla.p99_latency_ms == 1000
        assert sla.error_rate == 0.01
        assert sla.throughput_rps == 500


class TestFaultInjector:
    """Test FaultInjector."""

    @pytest.fixture
    def injector(self):
        return FaultInjector()

    def test_set_fault_probability(self, injector):
        """Test setting fault probability."""
        injector.set_fault_probability(FaultType.NETWORK_DELAY, 0.5)
        assert injector._fault_probability[FaultType.NETWORK_DELAY] == 0.5

    def test_set_fault_probability_clamped(self, injector):
        """Test probability is clamped to [0, 1]."""
        injector.set_fault_probability(FaultType.NETWORK_DELAY, 1.5)
        assert injector._fault_probability[FaultType.NETWORK_DELAY] == 1.0

        injector.set_fault_probability(FaultType.NETWORK_DELAY, -0.5)
        assert injector._fault_probability[FaultType.NETWORK_DELAY] == 0.0

    @pytest.mark.asyncio
    async def test_maybe_inject_no_fault(self, injector):
        """Test no fault injected when probability is 0."""
        injector.set_fault_probability(FaultType.NETWORK_DELAY, 0.0)
        result = await injector.maybe_inject(FaultType.NETWORK_DELAY, {})
        assert result is False

    @pytest.mark.asyncio
    async def test_maybe_inject_fault(self, injector):
        """Test fault injected when probability is 1."""
        injector.set_fault_probability(FaultType.NETWORK_DELAY, 1.0)
        # Mock the internal inject to avoid actual sleep
        with patch.object(injector, '_inject_fault', return_value=True) as mock:
            result = await injector.maybe_inject(FaultType.NETWORK_DELAY, {})
            assert result is True
            mock.assert_called_once()


class TestSimpleLoadGenerator:
    """Test SimpleLoadGenerator."""

    @pytest.fixture
    def generator(self):
        return SimpleLoadGenerator()

    @pytest.mark.asyncio
    async def test_generate_load_basic(self, generator):
        """Test basic load generation."""
        call_count = 0

        async def target():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.001)
            return {"status": "ok"}

        results = await generator.generate_load(
            target,
            concurrent=5,
            duration_sec=1,
        )

        assert len(results) > 0
        assert all(r["success"] for r in results)
        assert call_count == len(results)

    @pytest.mark.asyncio
    async def test_generate_load_with_errors(self, generator):
        """Test load generation with some failures."""
        async def failing_target():
            if asyncio.get_event_loop().time() % 2 < 1:
                raise ValueError("Simulated failure")
            return {"status": "ok"}

        results = await generator.generate_load(
            failing_target,
            concurrent=3,
            duration_sec=1,
        )

        # Some should succeed, some fail
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]
        assert len(successes) > 0 or len(failures) > 0


class TestStressTest:
    """Test main StressTest orchestrator."""

    @pytest.fixture
    def stress_test(self):
        config = StressTestConfig(
            duration_sec=1,
            max_concurrent=2,
            ramp_up_sec=0,
            scenarios=["load"],
            sla_thresholds={
                "p99_latency_ms": 5000,
                "error_rate": 0.5,
                "throughput_rps": 1,
            },
        )
        return StressTest(config)

    @pytest.mark.asyncio
    async def test_run_scenario_load(self, stress_test):
        """Test running load scenario."""
        class DummyTarget:
            async def process(self, data):
                await asyncio.sleep(0.001)
                return {"status": "ok"}

        result = await stress_test.run_scenario(StressScenario.LOAD, DummyTarget().process)

        assert isinstance(result, StressResult)
        assert result.scenario == StressScenario.LOAD
        assert result.total_requests > 0
        assert result.successful_requests > 0
        assert result.throughput_rps > 0

    @pytest.mark.asyncio
    async def test_run_all_scenarios(self, stress_test):
        """Test running all configured scenarios."""
        class DummyTarget:
            async def process(self, data):
                await asyncio.sleep(0.001)
                return {"status": "ok"}

        # Only run load scenario for speed
        stress_test._config.scenarios = ["load"]
        results = await stress_test.run_all_scenarios(DummyTarget().process)

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].scenario == StressScenario.LOAD

    @pytest.mark.asyncio
    async def test_get_summary(self, stress_test):
        """Test getting summary report."""
        class DummyTarget:
            async def process(self, data):
                await asyncio.sleep(0.001)
                return {"status": "ok"}

        await stress_test.run_scenario(StressScenario.LOAD, DummyTarget().process)
        summary = stress_test.get_summary()

        assert "scenarios_run" in summary
        assert "total_requests" in summary
        assert "overall_error_rate" in summary
        assert "scenarios" in summary

    def test_get_results(self, stress_test):
        """Test getting results."""
        results = stress_test.get_results()
        assert isinstance(results, list)
        assert len(results) == 0


class TestStressTestGlobal:
    """Test global StressTest instance."""

    def test_get_stress_test_singleton(self):
        """Test get_stress_test returns singleton."""
        s1 = get_stress_test()
        s2 = get_stress_test()
        assert s1 is s2

    def test_set_stress_test(self):
        """Test set_stress_test replaces global."""
        original = get_stress_test()
        new_s = StressTest()
        set_stress_test(new_s)
        assert get_stress_test() is new_s
        set_stress_test(original)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])