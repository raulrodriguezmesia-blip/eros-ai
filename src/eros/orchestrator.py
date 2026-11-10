import time

from eros.agents.architecture_agent import ArchitectureAgent
from eros.agents.base import BaseAgent
from eros.agents.compliance_agent import ComplianceAgent
from eros.agents.remediation_agent import RemediationAgent
from eros.agents.security_agent import SecurityAgent
from eros.config.feature_flags import FeatureFlag, FeatureFlags
from eros.models.schemas import AnalysisRequest, AnalysisResult, Finding, RiskLevel


class AnalysisOrchestrator:
    def __init__(self):
        self.agents: list[BaseAgent] = [
            SecurityAgent(),
            ArchitectureAgent(),
            ComplianceAgent(),
            RemediationAgent(),
        ]

    async def run(self, request: AnalysisRequest) -> AnalysisResult:
        start = time.monotonic()
        all_findings: list[Finding] = []
        agents_executed: list[str] = []

        # Run all agents in parallel
        import asyncio

        tasks = [agent.run(request.code, request.language) for agent in self.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for agent, result in zip(self.agents, results):
            if isinstance(result, Exception):
                continue
            findings = result if isinstance(result, list) else []
            # Attach patches if auto_patch enabled
            if FeatureFlags.is_enabled(FeatureFlag.AUTO_PATCH_GENERATION):
                remediation = RemediationAgent()
                for f in findings:
                    if f.cwe:
                        validation = await remediation.generate_patch(f, request.code)
                        f.patch = validation.get("patch", "")
                        f.validated = validation.get("validated", False)
                        f.validation_status = "tests_passed" if validation.get("tests_passed", 0) > 0 else "pending"
                        # Store validation evidence in metadata
                        f.metadata = getattr(f, 'metadata', {})
                        f.metadata["validation_evidence"] = {
                            "tests_run": validation.get("tests_run", 0),
                            "tests_passed": validation.get("tests_passed", 0),
                            "patch_generated": validation.get("patch_generated", False),
                            "note": validation.get("validation_note", "")
                        }
            all_findings.extend(findings)
            agents_executed.append(agent.name)

        # Determine risk level
        risk_level = RiskLevel.LOW
        severities = [f.severity for f in all_findings]
        if "CRITICAL" in severities:
            risk_level = RiskLevel.CRITICAL
        elif "HIGH" in severities:
            risk_level = RiskLevel.HIGH
        elif "MEDIUM" in severities:
            risk_level = RiskLevel.MEDIUM

        patches_count = sum(1 for f in all_findings if f.patch)

        duration_ms = int((time.monotonic() - start) * 1000)

        return AnalysisResult(
            status="completed",
            findings=all_findings,
            risk_level=risk_level,
            patches_generated=patches_count,
            agents_executed=agents_executed,
            flags_active=FeatureFlags.all_flags(),
            duration_ms=duration_ms,
        )


orchestrator = AnalysisOrchestrator()
