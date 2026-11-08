import asyncio

import structlog

from eros.config.settings import settings

logger = structlog.get_logger()


class FoundryClient:
    """Microsoft Foundry IQ client with retry and circuit breaker."""

    def __init__(self):
        self.endpoint = settings.foundry_endpoint
        self.api_key = settings.foundry_api_key
        self.model = settings.foundry_model
        self._client = None
        self._circuit_open = False
        self._failure_count = 0
        self._max_failures = 3

    def _get_client(self):
        if self._client is not None:
            return self._client

        if not self.endpoint:
            logger.info("foundry_not_configured", msg="Using local analysis only")
            return None

        # Try Azure AD auth first, fall back to API key
        if self.api_key:
            from openai import OpenAI

            self._client = OpenAI(
                base_url=f"{self.endpoint}/openai/v1",
                api_key=self.api_key,
            )
        else:
            try:
                from azure.ai.projects import AIProjectClient
                from azure.identity import DefaultAzureCredential

                project = AIProjectClient(
                    endpoint=self.endpoint,
                    credential=DefaultAzureCredential(),
                )
                self._client = project.get_openai_client()
            except Exception as e:  # noqa: BLE001
                logger.error("foundry_auth_failed", error=str(e))
                return None

        return self._client

    async def analyze_code(self, code: str, prompt: str) -> dict:
        """Send code to Foundry IQ for analysis."""
        if self._circuit_open:
            logger.warning("circuit_breaker_open", msg="Foundry unavailable, using local analysis")
            return {"status": "degraded", "result": None}

        client = self._get_client()
        if client is None:
            return {"status": "local", "result": None}

        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": code},
                ],
                max_tokens=settings.max_tokens_per_analysis,
                temperature=0.1,
            )
            self._failure_count = 0
            content = response.choices[0].message.content
            return {"status": "success", "result": content}
        except Exception as e:  # noqa: BLE001
            if self._failure_count >= self._max_failures:
                self._circuit_open = True
                logger.error("circuit_breaker_tripped", failures=self._failure_count)
            logger.error("foundry_call_failed", error=str(e))
            return {"status": "error", "result": None}

    def reset_circuit(self):
        self._circuit_open = False
        self._failure_count = 0


foundry_client = FoundryClient()
