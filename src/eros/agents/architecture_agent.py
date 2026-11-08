import re

from eros.agents.base import BaseAgent
from eros.models.schemas import Finding, Severity


class ArchitectureAgent(BaseAgent):
    name = "architecture_agent"
    description = "Detects coupling, technical debt, and complexity issues"

    async def analyze(self, code: str, language: str) -> list[Finding]:
        findings: list[Finding] = []
        lines = code.splitlines()

        # Long functions (more than 50 lines)
        func_lines = 0
        func_start = 0
        in_func = False

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.match(r"^(def |async def |function |public |private |protected )", stripped):
                if in_func and func_lines > 50:
                    findings.append(
                        Finding(
                            agent=self.name,
                            phase="quality_review",
                            severity=Severity.MEDIUM,
                            description=f"Function starting at line {func_start} exceeds 50 lines ({func_lines} lines)",
                            line=func_start,
                            fix="Refactor into smaller, single-responsibility functions",
                            reachability="Internal Only",
                            business_impact="Service Disruption",
                            confidence=0.85,
                        )
                    )
                in_func = True
                func_start = i
                func_lines = 0
            elif in_func:
                func_lines += 1

        # God class / too many imports
        import_count = sum(1 for l in lines if re.match(r"^(import |from )", l.strip()))
        if import_count > 15:
            findings.append(
                Finding(
                    agent=self.name,
                    phase="quality_review",
                    severity=Severity.LOW,
                    description=f"High coupling: {import_count} imports detected",
                    fix="Consider splitting into smaller modules",
                    reachability="Internal Only",
                    business_impact="Service Disruption",
                    confidence=0.80,
                )
            )

        # Deep nesting
        for i, line in enumerate(lines, 1):
            indent = len(line) - len(line.lstrip())
            if indent > 24:
                findings.append(
                    Finding(
                        agent=self.name,
                        phase="quality_review",
                        severity=Severity.MEDIUM,
                        description="Deep nesting detected (>3 levels)",
                        line=i,
                        fix="Extract nested logic into separate functions",
                    )
                )
                break

        return findings
