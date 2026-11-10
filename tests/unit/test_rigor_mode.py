"""
Unit tests for RigorMode configuration loader.
"""

import os
import pytest
import tempfile
from pathlib import Path

from eros import (
    RigorMode,
    get_rigor_mode,
    reset_rigor_mode,
    AgentRegistryConfig,
    ConfidenceGateConfig,
    ReasoningTraceConfig,
    StressTestConfig,
    CLISkillsConfig,
    SafetyGuardrailsConfig,
)


class TestRigorMode:
    """Test RigorMode configuration loading."""

    def setup_method(self):
        """Reset global state before each test."""
        reset_rigor_mode()
        # Clear env var
        if "AEGIS_RIGOR_MODE" in os.environ:
            del os.environ["AEGIS_RIGOR_MODE"]
        if "AEGIS_RIGOR_CONFIG" in os.environ:
            del os.environ["AEGIS_RIGOR_CONFIG"]

    def teardown_method(self):
        """Clean up after each test."""
        reset_rigor_mode()

    def test_default_mode_is_demo(self):
        """Default mode should be demo when no config/env."""
        # Create minimal config with only demo mode
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
rigor:
  mode: "demo"
  demo:
    agent_registry:
      max_agents: 3
    confidence_gate:
      min_confidence: 0.7
    reasoning_trace:
      enabled: true
    stress_test:
      enabled: true
    cli_skills:
      enabled: true
    safety_guardrails:
      enabled: true
""")
            config_path = f.name
        
        try:
            rigor = RigorMode(config_path=config_path)
            assert rigor.mode == "demo"
            assert isinstance(rigor.get_agent_registry_config(), AgentRegistryConfig)
            assert rigor.get_agent_registry_config().max_agents == 3
        finally:
            Path(config_path).unlink()

    def test_env_override_mode(self):
        """AEGIS_RIGOR_MODE env var should override config default."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
rigor:
  mode: "demo"
  demo:
    agent_registry:
      max_agents: 3
    confidence_gate:
      min_confidence: 0.7
    reasoning_trace:
      enabled: true
    stress_test:
      enabled: true
    cli_skills:
      enabled: true
    safety_guardrails:
      enabled: true
  standard:
    agent_registry:
      max_agents: 10
    confidence_gate:
      min_confidence: 0.75
    reasoning_trace:
      enabled: true
    stress_test:
      enabled: true
    cli_skills:
      enabled: true
    safety_guardrails:
      enabled: true
""")
            config_path = f.name
        
        try:
            os.environ["AEGIS_RIGOR_MODE"] = "standard"
            rigor = RigorMode(config_path=config_path)
            assert rigor.mode == "standard"
            assert rigor.get_agent_registry_config().max_agents == 10
        finally:
            Path(config_path).unlink()
            if "AEGIS_RIGOR_MODE" in os.environ:
                del os.environ["AEGIS_RIGOR_MODE"]

    def test_mode_override_parameter(self):
        """Constructor mode_override should take precedence."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
rigor:
  mode: "demo"
  demo:
    agent_registry:
      max_agents: 3
    confidence_gate:
      min_confidence: 0.7
    reasoning_trace:
      enabled: true
    stress_test:
      enabled: true
    cli_skills:
      enabled: true
    safety_guardrails:
      enabled: true
  enterprise:
    agent_registry:
      max_agents: 100
    confidence_gate:
      min_confidence: 0.8
    reasoning_trace:
      enabled: true
    stress_test:
      enabled: true
    cli_skills:
      enabled: true
    safety_guardrails:
      enabled: true
""")
            config_path = f.name
        
        try:
            rigor = RigorMode(config_path=config_path, mode_override="enterprise")
            assert rigor.mode == "enterprise"
            assert rigor.get_agent_registry_config().max_agents == 100
        finally:
            Path(config_path).unlink()

    def test_all_config_sections_loaded(self):
        """All 6 component configs should be loaded for each mode."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
rigor:
  mode: "standard"
  standard:
    agent_registry:
      max_agents: 10
      persistence: "sqlite"
    confidence_gate:
      min_confidence: 0.75
      fallback: "escalate"
      calibration_enabled: true
    reasoning_trace:
      enabled: true
      max_depth: 10
      storage: "sqlite"
      export_formats: ["json", "mermaid"]
    stress_test:
      enabled: true
      max_concurrent: 100
      scenarios: ["load", "latency"]
    cli_skills:
      enabled: true
      commands: ["register", "invoke", "benchmark"]
    safety_guardrails:
      enabled: true
      rules: ["pii_detection", "prompt_injection"]
      action: "block"
""")
            config_path = f.name
        
        try:
            rigor = RigorMode(config_path=config_path)
            
            # AgentRegistry
            reg_cfg = rigor.get_agent_registry_config()
            assert reg_cfg.max_agents == 10
            assert reg_cfg.persistence == "sqlite"
            
            # ConfidenceGate
            gate_cfg = rigor.get_confidence_gate_config()
            assert gate_cfg.min_confidence == 0.75
            assert gate_cfg.fallback == "escalate"
            assert gate_cfg.calibration_enabled is True
            
            # ReasoningTrace
            trace_cfg = rigor.get_reasoning_trace_config()
            assert trace_cfg.enabled is True
            assert trace_cfg.max_depth == 10
            assert trace_cfg.storage == "sqlite"
            assert "json" in trace_cfg.export_formats
            assert "mermaid" in trace_cfg.export_formats
            
            # StressTest
            stress_cfg = rigor.get_stress_test_config()
            assert stress_cfg.enabled is True
            assert stress_cfg.max_concurrent == 100
            assert "load" in stress_cfg.scenarios
            
            # CLISkills
            cli_cfg = rigor.get_cli_skills_config()
            assert cli_cfg.enabled is True
            assert "register" in cli_cfg.commands
            assert "benchmark" in cli_cfg.commands
            
            # SafetyGuardrails
            guard_cfg = rigor.get_safety_guardrails_config()
            assert guard_cfg.enabled is True
            assert "pii_detection" in guard_cfg.rules
            assert guard_cfg.action == "block"
            
        finally:
            Path(config_path).unlink()

    def test_invalid_mode_raises_error(self):
        """Invalid mode should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
rigor:
  mode: "invalid_mode"
  demo:
    agent_registry:
      max_agents: 3
    confidence_gate:
      min_confidence: 0.7
    reasoning_trace:
      enabled: true
    stress_test:
      enabled: true
    cli_skills:
      enabled: true
    safety_guardrails:
      enabled: true
""")
            config_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid rigor mode"):
                RigorMode(config_path=config_path)
        finally:
            Path(config_path).unlink()

    def test_missing_config_raises_error(self):
        """Missing config file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            RigorMode(config_path="/nonexistent/path/rigor.yaml")

    def test_singleton_behavior(self):
        """get_rigor_mode should return singleton instance."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
rigor:
  mode: "demo"
  demo:
    agent_registry:
      max_agents: 3
    confidence_gate:
      min_confidence: 0.7
    reasoning_trace:
      enabled: true
    stress_test:
      enabled: true
    cli_skills:
      enabled: true
    safety_guardrails:
      enabled: true
""")
            config_path = f.name
        
        try:
            rigor1 = get_rigor_mode(config_path)
            rigor2 = get_rigor_mode(config_path)
            assert rigor1 is rigor2
        finally:
            Path(config_path).unlink()
            reset_rigor_mode()

    def test_is_demo_standard_enterprise_helpers(self):
        """Helper methods should correctly identify mode."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
rigor:
  mode: "standard"
  demo:
    agent_registry:
      max_agents: 3
    confidence_gate:
      min_confidence: 0.7
    reasoning_trace:
      enabled: true
    stress_test:
      enabled: true
    cli_skills:
      enabled: true
    safety_guardrails:
      enabled: true
  standard:
    agent_registry:
      max_agents: 10
    confidence_gate:
      min_confidence: 0.75
    reasoning_trace:
      enabled: true
    stress_test:
      enabled: true
    cli_skills:
      enabled: true
    safety_guardrails:
      enabled: true
""")
            config_path = f.name
        
        try:
            rigor = RigorMode(config_path=config_path)
            assert rigor.is_demo() is False
            assert rigor.is_standard() is True
            assert rigor.is_enterprise() is False
        finally:
            Path(config_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])