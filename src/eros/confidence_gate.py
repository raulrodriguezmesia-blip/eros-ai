"""
aegis-lite ConfidenceGate
Routes decisions based on confidence scores with configurable thresholds.
Implements fallback strategies and calibration per RigorMode.
"""

from __future__ import annotations
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import statistics

from .rigor import get_rigor_mode, ConfidenceGateConfig

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FallbackAction(Enum):
    HUMAN_REVIEW = "human_review"
    ESCALATE = "escalate"
    DETERMINISTIC_GUARDRAIL = "deterministic_guardrail"
    REJECT = "reject"
    DEFAULT = "default"


@dataclass
class ConfidenceScore:
    value: float  # 0.0 - 1.0
    level: ConfidenceLevel
    factors: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GateDecision:
    allowed: bool
    confidence: ConfidenceScore
    fallback: Optional[FallbackAction] = None
    reason: str = ""
    guardrail_triggered: bool = False
    escalation_path: List[str] = field(default_factory=list)


class ConfidenceScorer(ABC):
    """Abstract confidence scorer for different model types."""
    
    @abstractmethod
    async def score(self, input_data: Any, context: Dict[str, Any]) -> ConfidenceScore:
        """Calculate confidence score for the given input."""
        pass


class LLMSelfConsistencyScorer(ConfidenceScorer):
    """Confidence via self-consistency (multiple samples)."""
    
    def __init__(self, samples: int = 5, temperature: float = 0.7):
        self.samples = samples
        self.temperature = temperature
    
    async def score(self, input_data: Any, context: Dict[str, Any]) -> ConfidenceScore:
        # Placeholder - would integrate with actual LLM
        # Returns variance-based confidence
        import random
        base_confidence = random.uniform(0.6, 0.95)
        variance = random.uniform(0.02, 0.15)
        confidence = max(0.0, min(1.0, base_confidence - variance))
        
        level = ConfidenceLevel.HIGH if confidence >= 0.8 else (
            ConfidenceLevel.MEDIUM if confidence >= 0.6 else ConfidenceLevel.LOW
        )
        
        return ConfidenceScore(
            value=confidence,
            level=level,
            factors={"self_consistency_variance": variance, "samples": self.samples},
            metadata={"method": "self_consistency"},
        )


class ProbabilisticScorer(ConfidenceScorer):
    """Confidence from model probability outputs."""
    
    async def score(self, input_data: Any, context: Dict[str, Any]) -> ConfidenceScore:
        # Placeholder - would use actual model logits/probabilities
        import random
        import math
        probs = context.get("probabilities", [random.random() for _ in range(5)])
        max_prob = max(probs)
        # Shannon entropy: -sum(p * log2(p))
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        
        # Normalize entropy to 0-1 confidence (max entropy for 5 classes = log2(5) ≈ 2.32)
        max_entropy = math.log2(len(probs))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        confidence = max_prob * (1 - min(normalized_entropy, 0.5))
        
        level = ConfidenceLevel.HIGH if confidence >= 0.8 else (
            ConfidenceLevel.MEDIUM if confidence >= 0.6 else ConfidenceLevel.LOW
        )
        
        return ConfidenceScore(
            value=confidence,
            level=level,
            factors={"max_probability": max_prob, "entropy": entropy},
            metadata={"method": "probabilistic"},
        )


class CalibrationModel:
    """Platt scaling / isotonic regression for confidence calibration."""
    
    def __init__(self):
        self._calibrated = False
        self._slope = 1.0
        self._intercept = 0.0
        self._history: List[Tuple[float, bool]] = []  # (confidence, correct)
    
    def add_sample(self, confidence: float, correct: bool) -> None:
        self._history.append((confidence, correct))
        if len(self._history) >= 100:
            self._recalibrate()
    
    def _recalibrate(self) -> None:
        # Simple Platt scaling approximation
        if len(self._history) < 10:
            return
        
        confidences = [c for c, _ in self._history]
        outcomes = [1 if o else 0 for _, o in self._history]
        
        # Linear regression for Platt scaling
        n = len(confidences)
        sum_x = sum(confidences)
        sum_y = sum(outcomes)
        sum_xy = sum(c * o for c, o in zip(confidences, outcomes))
        sum_x2 = sum(c * c for c in confidences)
        
        denom = n * sum_x2 - sum_x * sum_x
        if denom != 0:
            self._slope = (n * sum_xy - sum_x * sum_y) / denom
            self._intercept = (sum_y - self._slope * sum_x) / n
            self._calibrated = True
    
    def calibrate(self, confidence: float) -> float:
        if not self._calibrated:
            return confidence
        calibrated = self._slope * confidence + self._intercept
        return max(0.0, min(1.0, calibrated))


class ConfidenceGate:
    """
    Routes decisions based on confidence with configurable fallbacks.
    Respects RigorMode for threshold and behavior configuration.
    """
    
    def __init__(self, config: Optional[ConfidenceGateConfig] = None):
        self._config = config or get_rigor_mode().get_confidence_gate_config()
        self._scorers: Dict[str, ConfidenceScorer] = {}
        self._calibration = CalibrationModel() if self._config.calibration_enabled else None
        self._adaptive_thresholds = self._config.adaptive_thresholds
        self._threshold_history: List[Dict[str, float]] = []
        self._audit_log: List[Dict[str, Any]] = [] if self._config.audit_trail else None
        self._lock = asyncio.Lock()
        
        # Register default scorers
        self.register_scorer("llm_self_consistency", LLMSelfConsistencyScorer())
        self.register_scorer("probabilistic", ProbabilisticScorer())
    
    def register_scorer(self, name: str, scorer: ConfidenceScorer) -> None:
        self._scorers[name] = scorer
        logger.info(f"Registered confidence scorer: {name}")
    
    async def evaluate(
        self,
        input_data: Any,
        context: Optional[Dict[str, Any]] = None,
        scorer_name: str = "llm_self_consistency",
    ) -> GateDecision:
        """Evaluate confidence and make routing decision."""
        context = context or {}
        scorer = self._scorers.get(scorer_name)
        
        if not scorer:
            raise ValueError(f"Unknown scorer: {scorer_name}")
        
        # Get confidence score
        score = await scorer.score(input_data, context)
        
        # Apply calibration if enabled
        if self._calibration:
            score.value = self._calibration.calibrate(score.value)
            score.level = self._get_level(score.value)
        
        # Determine decision
        decision = self._make_decision(score, context)
        
        # Audit trail
        if self._audit_log is not None:
            self._audit_log.append({
                "timestamp": datetime.now(UTC).isoformat(),
                "input_hash": hash(str(input_data)) % 1000000,
                "scorer": scorer_name,
                "confidence": score.value,
                "level": score.level.value,
                "allowed": decision.allowed,
                "fallback": decision.fallback.value if decision.fallback else None,
                "reason": decision.reason,
            })
        
        # Update adaptive thresholds
        if self._adaptive_thresholds:
            self._update_thresholds(score, decision)
        
        return decision
    
    def _get_level(self, confidence: float) -> ConfidenceLevel:
        thresholds = self._config.thresholds
        if confidence >= thresholds.get("high", 0.9):
            return ConfidenceLevel.HIGH
        elif confidence >= thresholds.get("medium", 0.7):
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
    
    def _make_decision(self, score: ConfidenceScore, context: Dict[str, Any]) -> GateDecision:
        min_conf = self._config.min_confidence
        fallback_str = self._config.fallback
        fallback = FallbackAction(fallback_str) if fallback_str in [f.value for f in FallbackAction] else FallbackAction.HUMAN_REVIEW
        
        if score.value >= min_conf:
            return GateDecision(
                allowed=True,
                confidence=score,
                reason=f"Confidence {score.value:.2f} >= threshold {min_conf}",
            )
        
        # Below threshold - apply fallback
        reason = f"Confidence {score.value:.2f} < threshold {min_conf}"
        
        if fallback == FallbackAction.DETERMINISTIC_GUARDRAIL:
            return GateDecision(
                allowed=False,
                confidence=score,
                fallback=fallback,
                reason=reason,
                guardrail_triggered=True,
                escalation_path=["deterministic_guardrail", "human_review"],
            )
        elif fallback == FallbackAction.ESCALATE:
            return GateDecision(
                allowed=False,
                confidence=score,
                fallback=fallback,
                reason=reason,
                escalation_path=["escalate_to_specialist", "human_review"],
            )
        else:  # HUMAN_REVIEW or REJECT or DEFAULT
            return GateDecision(
                allowed=False,
                confidence=score,
                fallback=fallback,
                reason=reason,
                escalation_path=["human_review"],
            )
    
    def _update_thresholds(self, score: ConfidenceScore, decision: GateDecision) -> None:
        """Update adaptive thresholds based on outcomes."""
        self._threshold_history.append({
            "timestamp": time.time(),
            "confidence": score.value,
            "allowed": decision.allowed,
            "fallback": decision.fallback.value if decision.fallback else None,
        })
        
        # Keep last 1000 entries
        if len(self._threshold_history) > 1000:
            self._threshold_history = self._threshold_history[-1000:]
    
    def get_calibration_stats(self) -> Dict[str, Any]:
        """Get calibration model statistics."""
        if not self._calibration:
            return {"calibrated": False}
        
        return {
            "calibrated": self._calibration._calibrated,
            "slope": self._calibration._slope,
            "intercept": self._calibration._intercept,
            "samples": len(self._calibration._history),
        }
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        if not self._audit_log:
            return []
        return self._audit_log[-limit:]
    
    def add_calibration_sample(self, confidence: float, correct: bool) -> None:
        """Add sample for calibration model."""
        if self._calibration:
            self._calibration.add_sample(confidence, correct)
    
    def get_threshold_recommendations(self) -> Dict[str, float]:
        """Get recommended thresholds based on history."""
        if not self._threshold_history:
            return self._config.thresholds.copy()
        
        # Analyze history to recommend thresholds
        [h["confidence"] for h in self._threshold_history]
        allowed_conf = [h["confidence"] for h in self._threshold_history if h["allowed"]]
        rejected_conf = [h["confidence"] for h in self._threshold_history if not h["allowed"]]
        
        if not allowed_conf or not rejected_conf:
            return self._config.thresholds.copy()
        
        # Find separation point
        mean_allowed = statistics.mean(allowed_conf)
        mean_rejected = statistics.mean(rejected_conf)
        optimal = (mean_allowed + mean_rejected) / 2
        
        return {
            "low": max(0.0, optimal - 0.15),
            "medium": optimal,
            "high": min(1.0, optimal + 0.15),
        }


# Global gate instance
_gate: Optional[ConfidenceGate] = None


def get_confidence_gate(config: Optional[ConfidenceGateConfig] = None) -> ConfidenceGate:
    """Get or create the global ConfidenceGate instance."""
    global _gate
    if _gate is None:
        _gate = ConfidenceGate(config)
    return _gate


def set_confidence_gate(gate: ConfidenceGate) -> None:
    """Set the global ConfidenceGate instance (for testing)."""
    global _gate
    _gate = gate