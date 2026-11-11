"""
aegis-lite Rigor Mode Configuration Loader
Provides config-driven scope control for demo | standard | enterprise modes.
"""

from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class AgentRegistryConfig:
    max_agents: int
    persistence: str
    health_check_interval_sec: int
    replication: bool = False
    audit_log: bool = False


@dataclass
class ConfidenceGateConfig:
    min_confidence: float
    fallback: str
    thresholds: Dict[str, float]
    calibration_enabled: bool = False
    adaptive_thresholds: bool = False
    audit_trail: bool = False


@dataclass
class ReasoningTraceConfig:
    enabled: bool
    max_depth: int
    storage: str
    export_formats: List[str]
    sampling_rate: float = 1.0
    compression: bool = False
    retention_days: int = 7
    pii_redaction: bool = False


@dataclass
class StressTestConfig:
    enabled: bool = True
    max_concurrent: int = 100
    duration_sec: int = 60
    scenarios: List[str] = field(default_factory=lambda: ["load"])
    ramp_up_sec: int = 10
    distributed: bool = False
    sla_thresholds: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CLISkillsConfig:
    enabled: bool
    commands: List[str]
    autocomplete: bool = False
    plugin_support: bool = False
    rbac: bool = False
    telemetry: bool = False


@dataclass
class SafetyGuardrailsConfig:
    enabled: bool
    rules: List[str]
    action: str
    custom_rules: bool = False
    real_time: bool = False
    compliance_frameworks: List[str] = field(default_factory=list)
    audit_log: bool = False


@dataclass
class RigorConfig:
    mode: str
    agent_registry: AgentRegistryConfig
    confidence_gate: ConfidenceGateConfig
    reasoning_trace: ReasoningTraceConfig
    stress_test: StressTestConfig
    cli_skills: CLISkillsConfig
    safety_guardrails: SafetyGuardrailsConfig


class RigorMode:
    """Manages rigor mode configuration with environment override support."""
    
    DEMO = "demo"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"
    VALID_MODES = [DEMO, STANDARD, ENTERPRISE]
    
    def __init__(self, config_path: Optional[str] = None, mode_override: Optional[str] = None):
        self.config_path = config_path or os.getenv(
            "AEGIS_RIGOR_CONFIG", 
            str(Path(__file__).parent.parent / "config" / "rigor.yaml")
        )
        self._mode_override = mode_override
        self._config: Optional[RigorConfig] = None
        self._load()
    
    def _load(self) -> None:
        """Load configuration from YAML file."""
        path = Path(self.config_path)
        if not path.exists():
            raise FileNotFoundError(f"Rigor config not found: {path}")
        
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        
        # Allow environment variable override, or programmatic override
        env_mode = os.getenv("AEGIS_RIGOR_MODE")
        mode = self._mode_override or env_mode or raw.get("rigor", {}).get("mode", self.DEMO)
        
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid rigor mode: {mode}. Must be one of {self.VALID_MODES}")
        
        rigor_data = raw.get("rigor", {})
        mode_data = rigor_data.get(mode, {})
        
        self._config = RigorConfig(
            mode=mode,
            agent_registry=self._parse_agent_registry(mode_data.get("agent_registry", {})),
            confidence_gate=self._parse_confidence_gate(mode_data.get("confidence_gate", {})),
            reasoning_trace=self._parse_reasoning_trace(mode_data.get("reasoning_trace", {})),
            stress_test=self._parse_stress_test(mode_data.get("stress_test", {})),
            cli_skills=self._parse_cli_skills(mode_data.get("cli_skills", {})),
            safety_guardrails=self._parse_safety_guardrails(mode_data.get("safety_guardrails", {})),
        )
    
    def _parse_agent_registry(self, data: Dict) -> AgentRegistryConfig:
        return AgentRegistryConfig(
            max_agents=data.get("max_agents", 3),
            persistence=data.get("persistence", "memory"),
            health_check_interval_sec=data.get("health_check_interval_sec", 30),
            replication=data.get("replication", False),
            audit_log=data.get("audit_log", False),
        )
    
    def _parse_confidence_gate(self, data: Dict) -> ConfidenceGateConfig:
        return ConfidenceGateConfig(
            min_confidence=data.get("min_confidence", 0.7),
            fallback=data.get("fallback", "human_review"),
            thresholds=data.get("thresholds", {"low": 0.5, "medium": 0.7, "high": 0.9}),
            calibration_enabled=data.get("calibration_enabled", False),
            adaptive_thresholds=data.get("adaptive_thresholds", False),
            audit_trail=data.get("audit_trail", False),
        )
    
    def _parse_reasoning_trace(self, data: Dict) -> ReasoningTraceConfig:
        return ReasoningTraceConfig(
            enabled=data.get("enabled", True),
            max_depth=data.get("max_depth", 3),
            storage=data.get("storage", "memory"),
            export_formats=data.get("export_formats", ["json"]),
            sampling_rate=data.get("sampling_rate", 1.0),
            compression=data.get("compression", False),
            retention_days=data.get("retention_days", 7),
            pii_redaction=data.get("pii_redaction", False),
        )
    
    def _parse_stress_test(self, data: Dict) -> StressTestConfig:
        return StressTestConfig(
            enabled=data.get("enabled", True),
            max_concurrent=data.get("max_concurrent", 10),
            duration_sec=data.get("duration_sec", 30),
            scenarios=data.get("scenarios", ["load", "latency"]),
            ramp_up_sec=data.get("ramp_up_sec", 0),
            distributed=data.get("distributed", False),
            sla_thresholds=data.get("sla_thresholds", {}),
        )
    
    def _parse_cli_skills(self, data: Dict) -> CLISkillsConfig:
        return CLISkillsConfig(
            enabled=data.get("enabled", True),
            commands=data.get("commands", ["register", "invoke", "trace", "health"]),
            autocomplete=data.get("autocomplete", False),
            plugin_support=data.get("plugin_support", False),
            rbac=data.get("rbac", False),
            telemetry=data.get("telemetry", False),
        )
    
    def _parse_safety_guardrails(self, data: Dict) -> SafetyGuardrailsConfig:
        return SafetyGuardrailsConfig(
            enabled=data.get("enabled", True),
            rules=data.get("rules", ["pii_detection", "toxicity"]),
            action=data.get("action", "log"),
            custom_rules=data.get("custom_rules", False),
            real_time=data.get("real_time", False),
            compliance_frameworks=data.get("compliance_frameworks", []),
            audit_log=data.get("audit_log", False),
        )
    
    @property
    def config(self) -> RigorConfig:
        return self._config
    
    @property
    def mode(self) -> str:
        return self._config.mode
    
    def get_agent_registry_config(self) -> AgentRegistryConfig:
        return self._config.agent_registry
    
    def get_confidence_gate_config(self) -> ConfidenceGateConfig:
        return self._config.confidence_gate
    
    def get_reasoning_trace_config(self) -> ReasoningTraceConfig:
        return self._config.reasoning_trace
    
    def get_stress_test_config(self) -> StressTestConfig:
        return self._config.stress_test
    
    def get_cli_skills_config(self) -> CLISkillsConfig:
        return self._config.cli_skills
    
    def get_safety_guardrails_config(self) -> SafetyGuardrailsConfig:
        return self._config.safety_guardrails
    
    def is_demo(self) -> bool:
        return self._config.mode == self.DEMO
    
    def is_standard(self) -> bool:
        return self._config.mode == self.STANDARD
    
    def is_enterprise(self) -> bool:
        return self._config.mode == self.ENTERPRISE
    
    def __repr__(self) -> str:
        return f"RigorMode(mode={self._config.mode})"


# Singleton instance
_rigor_mode: Optional[RigorMode] = None


def get_rigor_mode(config_path: Optional[str] = None) -> RigorMode:
    """Get or create the global RigorMode instance."""
    global _rigor_mode
    if _rigor_mode is None:
        _rigor_mode = RigorMode(config_path)
    return _rigor_mode


def set_rigor_mode(mode: RigorMode) -> None:
    """Set the global RigorMode instance (for testing)."""
    global _rigor_mode
    _rigor_mode = mode


def reset_rigor_mode() -> None:
    """Reset the global RigorMode instance."""
    global _rigor_mode
    _rigor_mode = None