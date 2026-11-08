from abc import ABC, abstractmethod

from eros.models.schemas import Finding


class BaseAgent(ABC):
    name: str = "base"
    description: str = "Base agent"

    @abstractmethod
    async def analyze(self, code: str, language: str) -> list[Finding]:
        ...

    async def run(self, code: str, language: str) -> list[Finding]:
        try:
            return await self.analyze(code, language)
        except Exception as e:
            return [
                Finding(
                    agent=self.name,
                    phase="error",
                    severity="INFO",
                    description=f"Agent {self.name} failed: {str(e)}",
                )
            ]
