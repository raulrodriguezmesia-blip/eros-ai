"""
Unit tests for ConfidenceGate component.
"""

import pytest
from unittest.mock import patch

from eros import (
    ConfidenceGate,
    ConfidenceScore,
    ConfidenceLevel,
    FallbackAction,
    LLMSelfConsistencyScorer,
    ProbabilisticScorer,
    CalibrationModel,
    get_confidence_gate,
    set_confidence_gate,
    ConfidenceGateConfig,
)


class TestCalibrationModel:
    """Test CalibrationModel functionality."""
    
    def test_initial_state(self):
        """Test initial calibration state."""
        model = CalibrationModel()
        
        assert model._calibrated is False
        assert model._slope == 1.0
        assert model._intercept == 0.0
        assert len(model._history) == 0
    
    def test_add_sample_before_calibration(self):
        """Test adding samples before calibration threshold."""
        model = CalibrationModel()
        
        for i in range(50):
            model.add_sample(0.8, True)
        
        assert not model._calibrated
        assert len(model._history) == 50
    
    def test_calibration_after_threshold(self):
        """Test calibration triggers after 100 samples."""
        model = CalibrationModel()
        
        for i in range(100):
            model.add_sample(0.8, True)
        
        assert model._calibrated
    
    def test_calibration_calculation(self):
        """Test Platt scaling calculation."""
        model = CalibrationModel()
        
        # Perfect correlation: confidence 0.5 -> correct 0, 1.0 -> correct 1
        model.add_sample(0.5, False)
        model.add_sample(1.0, True)
        # Need 98 more
        for _ in range(98):
            model.add_sample(0.75, True)
        
        assert model._calibrated
        assert model._slope > 0  # Positive correlation
    
    def test_calibrate_uncalibrated(self):
        """Test calibration returns original when not calibrated."""
        model = CalibrationModel()
        
        result = model.calibrate(0.8)
        assert result == 0.8
    
    def test_calibrate_calibrated(self):
        """Test calibration modifies values when calibrated."""
        model = CalibrationModel()
        
        # Force calibration with perfect data
        for _ in range(100):
            model.add_sample(0.8, True)
        
        result = model.calibrate(0.5)
        # Should be transformed by slope/intercept
        assert 0 <= result <= 1
    
    def test_bounds_clamping(self):
        """Test calibration clamps to [0, 1]."""
        model = CalibrationModel()
        
        # Force calibration with extreme values
        model._calibrated = True
        model._slope = 10.0
        model._intercept = -5.0
        
        result = model.calibrate(1.0)
        assert result == 1.0
        
        result = model.calibrate(0.0)
        assert result == 0.0


class TestLLMSelfConsistencyScorer:
    """Test LLMSelfConsistencyScorer."""
    
    @pytest.fixture
    def scorer(self):
        return LLMSelfConsistencyScorer(samples=5, temperature=0.7)
    
    @pytest.mark.asyncio
    async def test_score_returns_confidence_score(self, scorer):
        """Test score returns ConfidenceScore."""
        result = await scorer.score("test input", {})
        
        assert isinstance(result, ConfidenceScore)
        assert 0 <= result.value <= 1
        assert result.level in ConfidenceLevel
        assert "self_consistency_variance" in result.factors
        assert result.metadata["method"] == "self_consistency"
    
    @pytest.mark.asyncio
    async def test_score_level_high(self, scorer):
        """Test high confidence level classification."""
        # Patch random to return high confidence
        with patch("random.uniform", return_value=0.95):
            result = await scorer.score("test", {})
        
        assert result.level == ConfidenceLevel.HIGH
    
    @pytest.mark.asyncio
    async def test_score_level_medium(self, scorer):
        """Test medium confidence level classification."""
        with patch("random.uniform", return_value=0.7):
            result = await scorer.score("test", {})
        
        assert result.level == ConfidenceLevel.MEDIUM
    
    @pytest.mark.asyncio
    async def test_score_level_low(self, scorer):
        """Test low confidence level classification."""
        with patch("random.uniform", return_value=0.5):
            result = await scorer.score("test", {})
        
        assert result.level == ConfidenceLevel.LOW


class TestProbabilisticScorer:
    """Test ProbabilisticScorer."""
    
    @pytest.fixture
    def scorer(self):
        return ProbabilisticScorer()
    
    @pytest.mark.asyncio
    async def test_score_with_probabilities(self, scorer):
        """Test score uses provided probabilities."""
        probs = [0.9, 0.05, 0.03, 0.01, 0.01]
        result = await scorer.score("test", {"probabilities": probs})
        
        assert isinstance(result, ConfidenceScore)
        assert result.value > 0.8  # High max prob, low entropy
        assert result.factors["max_probability"] == 0.9
        assert result.metadata["method"] == "probabilistic"
    
    @pytest.mark.asyncio
    async def test_score_uniform_probabilities(self, scorer):
        """Test score with uniform probabilities."""
        probs = [0.2, 0.2, 0.2, 0.2, 0.2]
        result = await scorer.score("test", {"probabilities": probs})
        
        # Uniform has max entropy, should lower confidence
        assert result.value < 0.5
    
    @pytest.mark.asyncio
    async def test_score_default_random(self, scorer):
        """Test score uses random when no probabilities provided."""
        result = await scorer.score("test", {})
        
        assert isinstance(result, ConfidenceScore)
        assert 0 <= result.value <= 1


class TestConfidenceGate:
    """Test ConfidenceGate main functionality."""
    
@pytest.fixture
def gate(self):
    # Use explicit demo config to avoid singleton contamination
    demo_config = ConfidenceGateConfig(
        min_confidence=0.7,
        fallback="human_review",
        thresholds={"low": 0.5, "medium": 0.7, "high": 0.9},
        calibration_enabled=False,
        adaptive_thresholds=False,
        audit_trail=False,
    )
    return ConfidenceGate(config=demo_config)
    
    @pytest.mark.asyncio
    async def test_evaluate_allowed_high_confidence(self, gate):
        """Test evaluation allows high confidence."""
        decision = await gate.evaluate(
            {"query": "test"},
            context={"probabilities": [0.99, 0.005, 0.003, 0.001, 0.001]},
            scorer_name="probabilistic",
        )
        
        assert decision.allowed is True
        assert decision.confidence.value > 0.9
        assert decision.fallback is None
    
    @pytest.mark.asyncio
    async def test_evaluate_blocked_low_confidence(self, gate):
        """Test evaluation blocks low confidence."""
        decision = await gate.evaluate(
            {"query": "test"},
            context={"probabilities": [0.3, 0.25, 0.2, 0.15, 0.1]},
            scorer_name="probabilistic",
        )
        
        assert decision.allowed is False
        assert decision.fallback == FallbackAction.HUMAN_REVIEW
    
    @pytest.mark.asyncio
    async def test_evaluate_custom_scorer(self, gate):
        """Test evaluation with custom scorer name."""
        decision = await gate.evaluate(
            {"query": "test"},
            context={"probabilities": [0.99, 0.005, 0.003, 0.001, 0.001]},
            scorer_name="llm_self_consistency",
        )
        
        assert decision.confidence.metadata["method"] == "self_consistency"
    
    @pytest.mark.asyncio
    async def test_evaluate_unknown_scorer(self, gate):
        """Test evaluation fails with unknown scorer."""
        with pytest.raises(ValueError, match="Unknown scorer"):
            await gate.evaluate(
                {"query": "test"},
                scorer_name="nonexistent",
            )
    
    @pytest.mark.asyncio
    async def test_calibration_enabled(self):
        """Test calibration is applied when enabled."""
        gate = ConfidenceGate()
        gate._config.calibration_enabled = True
        
        # Add calibration samples
        for _ in range(100):
            gate.add_calibration_sample(0.8, True)
        
        await gate.evaluate(
            {"query": "test"},
            context={"probabilities": [0.9, 0.05, 0.03, 0.01, 0.01]},
        )
        
        # Should be calibrated
        cal_stats = gate.get_calibration_stats()
        assert cal_stats["calibrated"] is True
    
    @pytest.mark.asyncio
    async def test_audit_trail(self):
        """Test audit trail records decisions."""
        gate = ConfidenceGate()
        gate._config.audit_trail = True
        
        await gate.evaluate(
            {"query": "test"},
            context={"probabilities": [0.99, 0.005, 0.003, 0.001, 0.001]},
        )
        
        audit = gate.get_audit_log()
        assert len(audit) == 1
        assert "confidence" in audit[0]
        assert "allowed" in audit[0]
    
    @pytest.mark.asyncio
    async def test_threshold_recommendations(self, gate):
        """Test threshold recommendations from history."""
        # Add history
        for _ in range(50):
            gate._threshold_history.append({"confidence": 0.9, "allowed": True})
        for _ in range(50):
            gate._threshold_history.append({"confidence": 0.4, "allowed": False})
        
        recs = gate.get_threshold_recommendations()
        
        assert "low" in recs
        assert "medium" in recs
        assert "high" in recs
        assert recs["medium"] > recs["low"]
        assert recs["high"] > recs["medium"]


class TestConfidenceGateGlobal:
    """Test global ConfidenceGate instance."""
    
    def test_get_confidence_gate_singleton(self):
        """Test get_confidence_gate returns singleton."""
        gate1 = get_confidence_gate()
        gate2 = get_confidence_gate()
        assert gate1 is gate2
    
    def test_set_confidence_gate(self):
        """Test set_confidence_gate replaces global."""
        original = get_confidence_gate()
        new_gate = ConfidenceGate()
        set_confidence_gate(new_gate)
        assert get_confidence_gate() is new_gate
        set_confidence_gate(original)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])