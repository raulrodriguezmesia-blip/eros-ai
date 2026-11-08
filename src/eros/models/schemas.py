from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class RiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Finding(BaseModel):
    agent: str
    phase: str
    severity: Severity
    cwe: str | None = None
    description: str
    line: int | None = None
    fix: str | None = None
    patch: str | None = None
    # Contextual Risk Intelligence
    reachability: str = "Unknown"
    business_impact: str = "Unknown"
    # Validated Remediation
    validated: bool = False
    validation_status: str = "pending"
    confidence: float = 0.0


class AnalysisRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50_000)
    language: str = Field(default="python")
    repo_url: str | None = None


class AnalysisResult(BaseModel):
    status: str = "completed"
    findings: list[Finding] = []
    risk_level: RiskLevel = RiskLevel.LOW
    patches_generated: int = 0
    agents_executed: list[str] = []
    flags_active: dict[str, bool] = {}
    duration_ms: int = 0


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str
    flags: dict[str, bool]
