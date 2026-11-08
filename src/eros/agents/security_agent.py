import json
import re

from eros.agents.base import BaseAgent
from eros.foundry.client import foundry_client
from eros.models.schemas import Finding, Severity

SECURITY_PROMPT = """You are a security code analyzer. Analyze the following code for vulnerabilities.
Return a JSON array of findings. Each finding must have:
- "severity": "CRITICAL", "HIGH", "MEDIUM", "LOW", or "INFO"
- "cwe": CWE identifier (e.g., "CWE-89")
- "description": brief description
- "line": line number (1-based)
- "fix": suggested fix

Only return the JSON array, no other text. If no issues found, return []."""


class SecurityAgent(BaseAgent):
    name = "security_agent"
    description = "Detects OWASP vulnerabilities, secrets, and insecure dependencies"

    async def analyze(self, code: str, language: str) -> list[Finding]:
        findings: list[Finding] = []

        # Try Foundry IQ first if configured
        foundry_result = await foundry_client.analyze_code(code, SECURITY_PROMPT)
        if foundry_result["status"] == "success" and foundry_result["result"]:
            try:
                parsed = json.loads(foundry_result["result"])
                for item in parsed:
                    findings.append(
                        Finding(
                            agent=self.name,
                            phase="security_audit",
                            severity=Severity(item.get("severity", "MEDIUM")),
                            cwe=item.get("cwe"),
                            description=item.get("description", "Unknown issue"),
                            line=item.get("line"),
                            fix=item.get("fix"),
                            reachability=item.get("reachability", "Unknown"),
                            business_impact=item.get("business_impact", "Unknown"),
                            confidence=item.get("confidence", 0.90),
                        )
                    )
                return findings
            except (json.JSONDecodeError, ValueError, KeyError):
                pass  # Fall through to local analysis

        # Local fallback (regex-based)
        lines = code.splitlines()

        sql_patterns = [
            (r'f["\'].*SELECT.*\{.*\}', "SQL Injection via f-string"),
            (r'execute\(.*%.*\)', "SQL Injection via string formatting"),
            (r'execute\(.*\+.*\)', "SQL Injection via concatenation"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, desc in sql_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            agent=self.name,
                            phase="security_audit",
                            severity=Severity.CRITICAL,
                            cwe="CWE-89",
                            description=desc,
                            line=i,
                            fix="Use parameterized queries with placeholders",
                            reachability="Internet Facing",
                            business_impact="Customer Data Exposure",
                            confidence=0.98,
                        )
                    )

        secret_patterns = [
            (r'(password|passwd|pwd)\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'(api_key|apikey|secret_key)\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
            (r'(token|auth_token)\s*=\s*["\'][^"\']+["\']', "Hardcoded token"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, desc in secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            agent=self.name,
                            phase="security_audit",
                            severity=Severity.CRITICAL,
                            cwe="CWE-798",
                            description=desc,
                            line=i,
                            fix="Use environment variables or a secrets manager (Azure Key Vault)",
                            reachability="Internal Only",
                            business_impact="Privilege Escalation",
                            confidence=0.99,
                        )
                    )

        cmd_patterns = [
            (r'os\.system\(', "Command injection via os.system"),
            (r'subprocess\.(call|run|Popen)\(.*shell\s*=\s*True', "Command injection via shell=True"),
            (r'eval\(', "Dangerous eval() usage"),
            (r'exec\(', "Dangerous exec() usage"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, desc in cmd_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            agent=self.name,
                            phase="security_audit",
                            severity=Severity.HIGH,
                            cwe="CWE-78",
                            description=desc,
                            line=i,
                            fix="Use subprocess with shell=False and input validation",
                            reachability="Internet Facing",
                            business_impact="Service Disruption",
                            confidence=0.95,
                        )
                    )

        return findings
