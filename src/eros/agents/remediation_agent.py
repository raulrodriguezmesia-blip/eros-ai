from eros.agents.base import BaseAgent
from eros.config.feature_flags import FeatureFlag, FeatureFlags
from eros.models.schemas import Finding, Severity


class RemediationAgent(BaseAgent):
    name = "remediation_agent"
    description = "Generates code patches and PRs for detected vulnerabilities"

    PATCH_TEMPLATES = {
        "CWE-89": '''# Fix: Use parameterized query
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))''',
        "CWE-798": '''# Fix: Use environment variable
import os
password = os.environ.get("APP_SECRET")''',
        "CWE-78": '''# Fix: Use subprocess without shell
import subprocess
subprocess.run(["ls", "-la"], shell=False)''',
    }

    async def analyze(self, code: str, language: str) -> list[Finding]:
        if not FeatureFlags.is_enabled(FeatureFlag.AUTO_PATCH_GENERATION):
            return []

        # This agent is triggered post-analysis with findings context
        # For standalone, return empty (patches attached to findings by orchestrator)
        return []

    async def generate_patch(self, finding: Finding, original_code: str) -> str:
        """Generate a code patch for a given finding."""
        template = self.PATCH_TEMPLATES.get(finding.cwe or "", "")
        if template:
            return template
        return f"# TODO: Manual review required for {finding.cwe}\n# Original: {finding.description}"
