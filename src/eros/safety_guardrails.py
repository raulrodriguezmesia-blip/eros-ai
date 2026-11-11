"""
aegis-lite SafetyGuardrails
Deterministic safety guardrails for agent outputs.
Implements PII detection, toxicity, prompt injection, hallucination, bias, and copyright detection.
"""

from __future__ import annotations
import re
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Set
import hashlib

from .rigor import get_rigor_mode, SafetyGuardrailsConfig

logger = logging.getLogger(__name__)


# Thread pool for running async code from sync contexts
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="safety-guardrails")


class GuardrailAction(Enum):
    LOG = "log"
    BLOCK = "block"
    BLOCK_AND_ALERT = "block_and_alert"


class GuardrailCategory(Enum):
    PII = "pii"
    TOXICITY = "toxicity"
    PROMPT_INJECTION = "prompt_injection"
    HALLUCINATION = "hallucination"
    BIAS = "bias"
    COPYRIGHT = "copyright"


@dataclass
class GuardrailRule:
    name: str
    category: GuardrailCategory
    pattern: Optional[Pattern] = None
    keywords: List[str] = field(default_factory=list)
    threshold: float = 0.8
    action: GuardrailAction = GuardrailAction.LOG
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def match(self, text: str) -> bool:
        if not self.enabled:
            return False
        
        if self.pattern and self.pattern.search(text):
            return True
        
        if self.keywords:
            text_lower = text.lower()
            return any(kw.lower() in text_lower for kw in self.keywords)
        
        return False


@dataclass
class GuardrailResult:
    rule_name: str
    category: GuardrailCategory
    triggered: bool
    confidence: float
    action: GuardrailAction
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class GuardrailDetector(ABC):
    """Abstract base for guardrail detectors."""
    
    @abstractmethod
    async def detect(self, text: str, context: Dict[str, Any]) -> List[GuardrailResult]:
        pass


class PIIDetector(GuardrailDetector):
    """Detects personally identifiable information."""
    
    # Common PII patterns
    PATTERNS = {
        "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "phone_us": re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
        "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "credit_card": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        "ip_address": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
        "api_key": re.compile(r'\b(?:api[_-]?key|secret)[\s:=]+[A-Za-z0-9_-]{20,}\b', re.IGNORECASE),
        "aws_key": re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
        "jwt": re.compile(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b'),
    }
    
    def __init__(self, custom_patterns: Optional[Dict[str, Pattern]] = None):
        self._patterns = {**self.PATTERNS}
        if custom_patterns:
            self._patterns.update(custom_patterns)
    
    async def detect(self, text: str, context: Dict[str, Any]) -> List[GuardrailResult]:
        results = []
        for name, pattern in self._patterns.items():
            matches = pattern.findall(text)
            if matches:
                results.append(GuardrailResult(
                    rule_name=f"pii_{name}",
                    category=GuardrailCategory.PII,
                    triggered=True,
                    confidence=0.95,
                    action=GuardrailAction.BLOCK,
                    details={
                        "pii_type": name,
                        "match_count": len(matches),
                        "matches": matches[:5],  # Limit exposure
                    },
                ))
        return results


class ToxicityDetector(GuardrailDetector):
    """Detects toxic content."""
    
    TOXIC_KEYWORDS = {
        "hate_speech": [
            "hate", "racist", "sexist", "bigot", "supremacist",
            "nazi", "kkk", "terrorist", "extremist",
        ],
        "harassment": [
            "harass", "bully", "threaten", "intimidate", "stalk",
            "abuse", "victim", "target",
        ],
        "violence": [
            "kill", "murder", "assault", "bomb", "weapon",
            "violence", "harm", "injure",
        ],
        "self_harm": [
            "suicide", "self-harm", "cutting", "overdose",
            "kill myself", "end my life",
        ],
    }
    
    def __init__(self, custom_keywords: Optional[Dict[str, List[str]]] = None):
        self._categories = {**self.TOXIC_KEYWORDS}
        if custom_keywords:
            self._categories.update(custom_keywords)
    
    async def detect(self, text: str, context: Dict[str, Any]) -> List[GuardrailResult]:
        results = []
        text_lower = text.lower()
        
        for category, keywords in self._categories.items():
            matches = [kw for kw in keywords if kw.lower() in text_lower]
            if matches:
                # Simple scoring based on match count
                confidence = min(0.5 + len(matches) * 0.1, 0.95)
                results.append(GuardrailResult(
                    rule_name=f"toxicity_{category}",
                    category=GuardrailCategory.TOXICITY,
                    triggered=True,
                    confidence=confidence,
                    action=GuardrailAction.BLOCK,
                    details={
                        "toxicity_category": category,
                        "match_count": len(matches),
                        "matched_keywords": matches[:10],
                    },
                ))
        return results


class PromptInjectionDetector(GuardrailDetector):
    """Detects prompt injection attempts."""
    
    # Comprehensive pattern list for prompt injection detection
    INJECTION_PATTERNS = [
        # Direct instructions - ordered by specificity
        (r'ignore\s+all\s+previous\s+instructions', "ignore_all_previous_instructions"),
        (r'ignore\s+previous\s+instructions', "ignore_previous_instructions"),
        (r'ignore\s+above\s+instructions', "ignore_above_instructions"),
        (r'ignore\s+all\s+instructions', "ignore_all_instructions"),
        (r'disregard\s+all\s+previous\s+instructions', "disregard_all_previous_instructions"),
        (r'disregard\s+previous\s+instructions', "disregard_previous_instructions"),
        (r'forget\s+(?:everything|all|previous)', "forget_context"),
        (r'override\s+(?:instructions|prompts?)', "override_instructions"),
        
        # Role manipulation
        (r'you\s+are\s+(?:now|an?)\s+(?:a|the)\s+\w+', "role_manipulation"),
        (r'act\s+as\s+(?:a|an|the)\s+\w+', "act_as"),
        (r'pretend\s+(?:to\s+be|you\s+are)\s+\w+', "pretend"),
        
        # Output manipulation
        (r'output\s+(?:only|just)\s+(?:the|in)\s+\w+', "output_constraint"),
        (r'respond\s+(?:only|just)\s+(?:with|in)\s+\w+', "respond_constraint"),
        (r'(?:print|show|display)\s+(?:the\s+)?(?:flag|password|secret|key)', "extract_secret"),
        
        # System prompt extraction
        (r'(?:what\s+is|show\s+me|tell\s+me)\s+(?:your\s+)?(?:system\s+)?prompt', "extract_prompt"),
        (r'repeat\s+(?:your\s+)?(?:system\s+)?prompt', "repeat_prompt"),
        (r'show\s+me\s+(?:your|the)\s+instructions', "show_instructions"),
        (r'reveal\s+(?:your|the)\s+(?:system\s+)?prompt', "reveal_prompt"),
        
        # Jailbreak attempts
        (r'developer\s+mode', "developer_mode"),
        (r'do\s+anything\s+now', "dan_mode"),
        (r'unrestricted\s+mode', "unrestricted_mode"),
        (r'bypass\s+(?:guardrails|safety|controls)', "bypass_guardrails"),
        (r'jailbreak', "jailbreak"),
    ]
    
    def __init__(self, custom_patterns: Optional[List[tuple]] = None):
        self._patterns = [(re.compile(p, re.IGNORECASE), n) for p, n in self.INJECTION_PATTERNS]
        if custom_patterns:
            self._patterns.extend([(re.compile(p, re.IGNORECASE), n) for p, n in custom_patterns])
    
    async def detect(self, text: str, context: Dict[str, Any]) -> List[GuardrailResult]:
        results = []
        normalized = text.lower().strip()
        for pattern, name in self._patterns:
            if pattern.search(normalized):
                results.append(GuardrailResult(
                    rule_name=f"prompt_injection_{name}",
                    category=GuardrailCategory.PROMPT_INJECTION,
                    triggered=True,
                    confidence=0.9,
                    action=GuardrailAction.BLOCK_AND_ALERT,
                    details={
                        "injection_type": name,
                        "matched_pattern": pattern.pattern,
                    },
                ))
        return results


class HallucinationDetector(GuardrailDetector):
    """Detects potential hallucinations in model outputs."""
    
    def __init__(self):
        # Patterns that suggest made-up facts
        self._uncertainty_markers = [
            r'\b(?:i think|i believe|probably|maybe|possibly|likely)\b',
            r'\b(?:as far as i know|to my knowledge|if i recall)\b',
        ]
        self._fabrication_markers = [
            r'\b(?:according to|studies show|research indicates|experts say)\b',
            r'\b(?:in \d{4}|as of \d{4}|recently)\b',
        ]
    
    async def detect(self, text: str, context: Dict[str, Any]) -> List[GuardrailResult]:
        results = []
        text_lower = text.lower()
        
        # Check for fabricated citations
        citation_pattern = re.compile(r'\[\d+\]|\(\w+,\s*\d{4}\)|doi:\s*\S+')
        citations = citation_pattern.findall(text)
        
        if citations:
            # Heuristic: many citations in short text might be hallucinated
            citation_density = len(citations) / max(len(text.split()), 1)
            if citation_density > 0.1:
                results.append(GuardrailResult(
                    rule_name="hallucination_excessive_citations",
                    category=GuardrailCategory.HALLUCINATION,
                    triggered=True,
                    confidence=0.7,
                    action=GuardrailAction.LOG,
                    details={
                        "citation_count": len(citations),
                        "citation_density": citation_density,
                        "citations": citations[:5],
                    },
                ))
        
        # Check for specific false claims patterns
        false_claim_patterns = [
            (r'\b(?:the capital of|the president of|the population of)\s+\w+', "factual_claim"),
            (r'\b(?:won the|received the)\s+(?:nobel|pulitzer|oscar|grammy)', "award_claim"),
        ]
        
        for pattern, name in false_claim_patterns:
            if re.search(pattern, text_lower):
                results.append(GuardrailResult(
                    rule_name=f"hallucination_{name}",
                    category=GuardrailCategory.HALLUCINATION,
                    triggered=True,
                    confidence=0.6,
                    action=GuardrailAction.LOG,
                    details={"claim_type": name},
                ))
        
        return results


class BiasDetector(GuardrailDetector):
    """Detects potential bias in outputs."""
    
    BIAS_PATTERNS = {
        "gender": [
            r'\b(?:all\s+)?(?:men|women)\s+(?:are|tend to|always|never)',
            r'\b(?:typical|normal)\s+(?:man|woman|male|female)',
        ],
        "racial": [
            r'\b(?:all\s+)?(?:black|white|asian|hispanic|latino)\s+people',
            r'\b(?:typical|stereotypical)\s+(?:black|white|asian)',
        ],
        "age": [
            r'\b(?:old|young|elderly|senior)\s+people\s+(?:are|tend to|always|never)',
        ],
        "disability": [
            r'\b(?:disabled|handicapped|impaired)\s+people\s+(?:are|tend to|always|never)',
        ],
    }
    
    def __init__(self, custom_patterns: Optional[Dict[str, List[str]]] = None):
        self._patterns = {k: [re.compile(p, re.IGNORECASE) for p in v] 
                          for k, v in self.BIAS_PATTERNS.items()}
        if custom_patterns:
            for cat, pats in custom_patterns.items():
                self._patterns.setdefault(cat, []).extend([re.compile(p, re.IGNORECASE) for p in pats])
    
    async def detect(self, text: str, context: Dict[str, Any]) -> List[GuardrailResult]:
        results = []
        for category, patterns in self._patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    results.append(GuardrailResult(
                        rule_name=f"bias_{category}",
                        category=GuardrailCategory.BIAS,
                        triggered=True,
                        confidence=0.75,
                        action=GuardrailAction.LOG,
                        details={"bias_category": category},
                    ))
                    break  # One match per category
        return results


class CopyrightDetector(GuardrailDetector):
    """Detects potential copyright violations."""
    
    def __init__(self):
        # Known text signatures (simplified)
        self._known_signatures: Set[str] = set()
        # In production, would load from database
    
    def add_signature(self, text: str) -> None:
        """Add known copyrighted text signature."""
        # Use hash of first 100 chars
        sig = hashlib.sha256(text[:100].encode()).hexdigest()[:16]
        self._known_signatures.add(sig)
    
    async def detect(self, text: str, context: Dict[str, Any]) -> List[GuardrailResult]:
        results = []
        
        # Check for verbatim reproduction (simplified)
        if len(text) > 200:
            # Check chunks
            for i in range(0, len(text) - 100, 50):
                chunk = text[i:i+100]
                sig = hashlib.sha256(chunk.encode()).hexdigest()[:16]
                if sig in self._known_signatures:
                    results.append(GuardrailResult(
                        rule_name="copyright_verbatim_match",
                        category=GuardrailCategory.COPYRIGHT,
                        triggered=True,
                        confidence=0.95,
                        action=GuardrailAction.BLOCK,
                        details={"chunk_position": i},
                    ))
                    break
        
        # Check for likely copyrighted patterns
        copyright_indicators = [
            r'©\s*\d{4}',
            r'copyright\s+\d{4}',
            r'all\s+rights\s+reserved',
            r'published\s+by\s+\w+',
        ]
        
        for pattern in copyright_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                results.append(GuardrailResult(
                    rule_name="copyright_notice_detected",
                    category=GuardrailCategory.COPYRIGHT,
                    triggered=True,
                    confidence=0.6,
                    action=GuardrailAction.LOG,
                    details={"notice_type": pattern},
                ))
        
        return results


class SafetyGuardrails:
    """
    Main safety guardrails orchestrator.
    Runs all detectors and applies configured actions.
    Configuration driven by RigorMode.
    """
    
    def __init__(self, config: Optional[SafetyGuardrailsConfig] = None):
        self._config = config or get_rigor_mode().get_safety_guardrails_config()
        self._detectors: List[GuardrailDetector] = []
        self._custom_rules: List[GuardrailRule] = []
        self._audit_log: Optional[List[Dict[str, Any]]] = None
        
        self._init_detectors()
    
    def _ensure_audit_log(self) -> None:
        """Lazily initialize audit log if enabled."""
        if self._config.audit_log and self._audit_log is None:
            self._audit_log = []
    
    def _refresh_detectors(self) -> None:
        """Re-initialize detectors from current config (useful if config changed)."""
        self._detectors.clear()
        self._init_detectors()
    
    def _init_detectors(self) -> None:
        """Initialize detectors based on configured rules."""
        rule_to_detector = {
            "pii_detection": PIIDetector(),
            "toxicity": ToxicityDetector(),
            "prompt_injection": PromptInjectionDetector(),
            "hallucination": HallucinationDetector(),
            "bias": BiasDetector(),
            "copyright": CopyrightDetector(),
        }
        
        for rule_name in self._config.rules:
            detector = rule_to_detector.get(rule_name)
            if detector:
                self._detectors.append(detector)
                logger.info(f"Enabled guardrail detector: {rule_name}")
        
        # Add custom rules as detectors
        for rule in self._custom_rules:
            # Custom rules would be converted to detectors
            pass
    
    def add_custom_rule(self, rule: GuardrailRule) -> None:
        """Add a custom guardrail rule."""
        self._custom_rules.append(rule)
        if not self._config.custom_rules:
            logger.warning("Custom rules not enabled in current rigor mode")
    
    async def check(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[GuardrailResult]:
        """Run all guardrail checks on text."""
        context = context or {}
        all_results: List[GuardrailResult] = []
        
        for detector in self._detectors:
            try:
                results = await detector.detect(text, context)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Detector {detector.__class__.__name__} failed: {e}")
        
        # Apply custom rules
        for rule in self._custom_rules:
            if rule.match(text):
                all_results.append(GuardrailResult(
                    rule_name=rule.name,
                    category=rule.category,
                    triggered=True,
                    confidence=rule.threshold,
                    action=rule.action,
                    details=rule.metadata,
                ))
        
        # Audit log
        self._ensure_audit_log()
        if self._audit_log is not None:
            for result in all_results:
                if result.triggered:
                    self._audit_log.append({
                        "timestamp": result.timestamp.isoformat(),
                        "rule": result.rule_name,
                        "category": result.category.value,
                        "action": result.action.value,
                        "confidence": result.confidence,
                        "text_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
                        "details": result.details,
                    })
        
        return all_results
    
    def get_action(self, results: List[GuardrailResult]) -> GuardrailAction:
        """Determine overall action from results."""
        if not results:
            return GuardrailAction.LOG
        
        # Highest severity action wins
        actions = [r.action for r in results if r.triggered]
        if GuardrailAction.BLOCK_AND_ALERT in actions:
            return GuardrailAction.BLOCK_AND_ALERT
        if GuardrailAction.BLOCK in actions:
            return GuardrailAction.BLOCK
        return GuardrailAction.LOG
    
    def is_allowed(self, text: str, context: Optional[Dict[str, Any]] = None) -> tuple[bool, List[GuardrailResult]]:
        """Synchronous check for simple cases. Works in both sync and async contexts."""
        
        async def _run_check():
            return await self.check_async(text, context)
        
        try:
            # Try to get running loop (async context)
            asyncio.get_running_loop()
            # We're in an async context - run in thread pool to avoid deadlock
            future = _executor.submit(asyncio.run, _run_check())
            allowed, results = future.result(timeout=30)
            return allowed, results
        except RuntimeError:
            # No running loop - we're in a sync context
            return asyncio.run(_run_check())
    
    async def check_async(self, text: str, context: Optional[Dict[str, Any]] = None) -> tuple[bool, List[GuardrailResult]]:
        """Async check returning allow/deny decision."""
        results = await self.check(text, context)
        action = self.get_action(results)
        allowed = action not in (GuardrailAction.BLOCK, GuardrailAction.BLOCK_AND_ALERT)
        return allowed, results
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        self._ensure_audit_log()
        if not self._audit_log:
            return []
        return self._audit_log[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "enabled": self._config.enabled,
            "rules": self._config.rules,
            "custom_rules": len(self._custom_rules),
            "action": self._config.action,
            "real_time": self._config.real_time,
            "compliance_frameworks": self._config.compliance_frameworks,
            "audit_log_enabled": self._audit_log is not None,
            "detectors": [d.__class__.__name__ for d in self._detectors],
        }


# Global guardrails instance
_guardrails: Optional[SafetyGuardrails] = None


def get_safety_guardrails(config: Optional[SafetyGuardrailsConfig] = None) -> SafetyGuardrails:
    """Get or create the global SafetyGuardrails instance."""
    global _guardrails
    if _guardrails is None:
        _guardrails = SafetyGuardrails(config)
    return _guardrails


def set_safety_guardrails(guardrails: SafetyGuardrails) -> None:
    """Set the global SafetyGuardrails instance (for testing)."""
    global _guardrails
    _guardrails = guardrails