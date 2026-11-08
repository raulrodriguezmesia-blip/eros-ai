import re

from typing import ClassVar

from eros.agents.base import BaseAgent
from eros.config.feature_flags import FeatureFlag, FeatureFlags
from eros.models.schemas import Finding, Severity


class ComplianceAgent(BaseAgent):
    name = "compliance_agent"
    description = "Enforces enterprise policies and OWASP Top 10 compliance"

    OWASP_RULES: ClassVar[list] = [
        (r"eval\(", "A03:2021 - Injection (eval usage)", "CWE-94"),
        (r"pickle\.loads", "A08:2021 - Software and Data Integrity Failures", "CWE-502"),
        (r"yaml\.load\([^)]*\)(?!.*Loader)", "A08:2021 - Unsafe YAML deserialization", "CWE-502"),
        (r"debug\s*=\s*True", "A05:2021 - Security Misconfiguration", "CWE-489"),
        (r"verify\s*=\s*False", "A02:2021 - Cryptographic Failures (SSL disabled)", "CWE-295"),
    ]

    async def analyze(self, code: str, language: str) -> list[Finding]:
        findings: list[Finding] = []
        lines = code.splitlines()
        strict = FeatureFlags.is_enabled(FeatureFlag.STRICT_COMPLIANCE_MODE)

        for i, line in enumerate(lines, 1):
            for pattern, desc, cwe in self.OWASP_RULES:
                if re.search(pattern, line, re.IGNORECASE):
                    severity = Severity.CRITICAL if strict else Severity.HIGH
                    findings.append(
                        Finding(
                            agent=self.name,
                            phase="compliance_audit",
                            severity=severity,
                            cwe=cwe,
                            description=desc,
                            line=i,
                            fix="Review and remediate per OWASP guidelines",
                            reachability="Authenticated",
                            business_impact="Compliance Risk",
                            confidence=0.90,
                        )
                    )

        # Hardcoded credentials in strict mode
        if strict:
            for i, line in enumerate(lines, 1):
                if re.search(r"(password|secret|token)\s*=\s*['\"]", line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            agent=self.name,
                            phase="compliance_audit",
                            severity=Severity.CRITICAL,
                            cwe="CWE-798",
                            description="Hardcoded credential in strict compliance mode",
                            line=i,
                            fix="Move to Azure Key Vault or environment variables",
                            reachability="Internal Only",
                            business_impact="Compliance Risk",
                            confidence=0.99,
                        )
                    )

        return findings
