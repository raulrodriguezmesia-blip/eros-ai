# 🛡️ Eros AI: Autonomous Engineering Governance Platform

[![Hackathon](https://img.shields.io/badge/Microsoft_Agents_League-Hackathon-0078D4?style=for-the-badge&logo=microsoft&logoColor=white)](https://devpost.com)
[![Track](https://img.shields.io/badge/Track-Agentic_Engineering-5C2D91?style=for-the-badge)](https://devpost.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-23%20Passing-brightgreen?style=for-the-badge)](https://github.com/raulrodriguezmesia-blip/eros-ai/actions)
[![Security](https://img.shields.io/badge/Security-Policy-success?style=for-the-badge)](SECURITY.md)
[![Code of Conduct](https://img.shields.io/badge/Code_of_Conduct-Contributor_Covenant-blue?style=for-the-badge)](CODE_OF_CONDUCT.md)

> **Analyze. Govern. Remediate. Validate.**

![Eros AI Dashboard](docs/dashboard.png)

Eros AI is a multi-agent engineering governance platform that continuously audits repositories, enforces security and compliance policies, and generates AI-assisted remediations — with behavior dynamically controlled through enterprise-grade Feature Flags, without redeployments.

---

## 📌 Executive Summary (BLUF)

**Eros AI** is an autonomous code analysis and governance platform powered by 4 specialized AI agents that collaborate to detect vulnerabilities, enforce compliance, and generate validated fixes — all orchestrated through **Microsoft Foundry IQ** and governed by **Feature Flags** that change agent behavior in real time.

Unlike traditional static analysis tools (SonarQube, Snyk, CodeQL), Eros AI doesn't just find problems — it **contextualizes risk** (reachability, business impact), **generates remediations**, and **validates them in a sandbox** before recommending them. The same agent produces different behavior based on governance flags, without redeployment.

### Why this matters

| Traditional Scanner | Eros AI |
|---|---|
| Finds vulnerabilities | Finds + contextualizes (reachability, business impact) |
| Reports issues | Reports + generates validated patches |
| Static rules | Dynamic governance via Feature Flags |
| Requires redeploy to change behavior | Real-time behavior switching |
| "AI-generated fix" | "AI-generated AND sandbox-validated fix" |

---

## Why Eros AI

Traditional tools focus on **detection**.

Modern engineering teams need:
- **Risk context** — not just "what" but "where" and "how bad"
- **Governance** — control agent behavior without redeploying
- **Validated remediation** — fixes that are tested, not just suggested
- **Runtime controllability** — change behavior in real time via Feature Flags

Eros AI combines all four.

---

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Azure Agent Server                            │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    Eros AI (FastAPI)                          │  │
│  │                                                                │  │
│  │  ┌──────────────┐    ┌──────────────────────────────────────┐  │  │
│  │  │  API Layer   │    │     Feature Flag Provider            │  │  │
│  │  │  /analyze    │    │  (Env vars / Azure App Config)       │  │  │
│  │  │  /health     │    └──────────────┬───────────────────────┘  │  │
│  │  │  /flags      │                   │                          │  │
│  │  └──────┬───────┘                   │                          │  │
│  │         │                           │                          │  │
│  │  ┌──────▼───────────────────────────▼──────────────────────┐   │  │
│  │  │            Analysis Orchestrator (async)               │   │  │
│  │  │  - Consulta flags → selecciona agentes                 │   │  │
│  │  │  - Ejecuta agentes en paralelo                        │   │  │
│  │  │  - Agrega resultados parciales                        │   │  │
│  │  └──────┬──────────────┬──────────────┬──────────────────┘   │  │
│  │         │              │              │                      │  │
│  │  ┌──────▼──────┐ ┌────▼──────┐ ┌────▼──────────┐          │  │
│  │  │  Security   │ │ Quality   │ │ Compliance    │          │  │
│  │  │  Guardian   │ │ Inspector │ │ Enforcer      │          │  │
│  │  └──────┬──────┘ └────┬──────┘ └────┬──────────┘          │  │
│  │         │              │              │                      │  │
│  │  ┌──────▼──────────────▼──────────────▼──────────────────┐   │  │
│  │  │           Microsoft Foundry IQ Client                  │   │  │
│  │  │  (retry + circuit breaker + token budget)              │   │  │
│  │  └──────────────────────┬────────────────────────────────┘   │  │
│  │                         │                                    │  │
│  └─────────────────────────┼────────────────────────────────────┘  │
│                            │                                       │
└────────────────────────────┼───────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Microsoft      │
                    │  Foundry IQ     │
                    │  (LLM + Tools)  │
                    └─────────────────┘
```

---

## 🤖 The 4 Agents

| Agent | Icon | Role | Detects |
|-------|------|------|---------|
| **Security Guardian** | 🛡️ | OWASP Top 10, secrets, command injection | SQL injection, hardcoded credentials, `os.system`, `eval` |
| **Quality Inspector** | 🔍 | Coupling, technical debt, complexity | Long functions, deep nesting, excessive imports |
| **Compliance Enforcer** | ✅ | Enterprise policies, OWASP compliance | Unsafe deserialization, debug mode, SSL disabled |
| **Fix Generator** | 🛠️ | AI-assisted remediation | Generates validated code patches |

---

## 🎛️ Feature Flag Governance

The core differentiator. Agents change behavior in real time without redeployment:

| Flag | OFF (default) | ON |
|------|---------------|-----|
| `deep_ast_analysis` | Regex scan (fast, ~200ms) | Deep AST + regex (~1.2s, exhaustive) |
| `auto_patch_generation` | Report only | Generate code patches + sandbox validation |
| `strict_compliance_mode` | Warnings | Block execution on critical findings |

**Toggle via API or dashboard switches — instant effect, no restart.**

---

## 📊 Contextual Risk Intelligence

Every finding includes enterprise-grade context:

| Field | Values | Purpose |
|-------|--------|---------|
| `reachability` | Internet Facing, Internal Only, Authenticated, Unknown | Where is the vulnerability exploitable? |
| `business_impact` | Customer Data Exposure, Privilege Escalation, Service Disruption, Compliance Risk | What's the real business cost? |
| `confidence` | 0.0–1.0 | How certain is the detection? |
| `validated` | true/false | Was the remediation sandbox-tested? |
| `validation_status` | pending, tests_passed, tests_failed | Validation result |

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ (strict typing, async/await) |
| API Framework | FastAPI + Uvicorn |
| Validation | Pydantic v2 |
| AI / Orchestration | Microsoft Foundry IQ (azure-ai-projects) |
| Feature Flags | Environment variables + runtime overrides |
| Frontend | HTML + Tailwind CSS (CDN) + Alpine.js |
| Container | Docker multi-stage (non-root, healthcheck) |
| Testing | pytest + pytest-asyncio |
| Observability | Structured logging (structlog) |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- (Optional) Microsoft Foundry IQ endpoint + API key

### 1. Clone & Install

```bash
git clone https://github.com/raulrodriguezmesia-blip/eros-ai.git
cd eros-ai
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Foundry credentials (optional for local analysis)
```

### 3. Run

```bash
PYTHONPATH=src uvicorn eros.main:app --reload --port 5000
```

Open `http://localhost:5000` — the dashboard loads instantly.

### 4. Test

```bash
python -m pytest tests/ -v
# 23 tests, all passing
```

### 5. Docker

```bash
docker build -t eros-ai:latest .
docker run -p 5000:8080 eros-ai:latest
```

---

## 📋 API Reference

### `GET /health`
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "flags": {
    "deep_ast_analysis": false,
    "auto_patch_generation": false,
    "strict_compliance_mode": false
  }
}
```

### `POST /analyze`
```json
{
  "code": "password = \"admin123\"\ndef get_user(uid): return db.execute(f\"SELECT * FROM users WHERE id={uid}\")",
  "language": "python"
}
```

**Response:**
```json
{
  "status": "completed",
  "findings": [
    {
      "agent": "security_agent",
      "phase": "security_audit",
      "severity": "CRITICAL",
      "cwe": "CWE-798",
      "description": "Hardcoded password",
      "line": 1,
      "fix": "Use environment variables or Azure Key Vault",
      "reachability": "Internal Only",
      "business_impact": "Privilege Escalation",
      "confidence": 0.99,
      "validated": false,
      "validation_status": "pending",
      "patch": null
    }
  ],
  "risk_level": "CRITICAL",
  "patches_generated": 0,
  "agents_executed": ["security_agent", "architecture_agent", "compliance_agent", "remediation_agent"],
  "flags_active": { "deep_ast_analysis": false, "auto_patch_generation": false, "strict_compliance_mode": false },
  "duration_ms": 12
}
```

### `GET /flags`
Returns current flag state and source.

### `POST /flags/{flag_name}?value=true`
Toggle a flag at runtime. Instant effect, no restart.

---

## 🎮 Demo Flow (60 seconds)

```
1. Open dashboard → KPIs in initial state
2. Click "Load Vulnerable Sample" → code with SQL injection, secrets, command injection
3. Click "Analyze Code" → agents detect 4+ findings
4. KPIs update: Health drops, Risk → CRITICAL, Compliance → FAIL
5. Findings show: reachability, business impact, confidence badges
6. Toggle "Strict Compliance" → ON → re-analyze → more findings, higher severity
7. Toggle "Auto Remediation" → ON → re-analyze → patches generated with "Sandbox Verified ✅"
8. Click "View Patch" → see validated code fix
```

---

## 🧪 Test Suite

23 tests across 3 layers:

| Layer | Files | Tests |
|-------|-------|-------|
| Unit | `test_security_agent.py`, `test_compliance_agent.py`, `test_feature_flags.py` | 11 |
| Integration | `test_analyze_api.py`, `test_foundry_client.py` | 6 |
| E2E | `test_vulnerable_sample_flow.py` | 2 |
| Legacy | `test_agents.py` | 4 |

```bash
python -m pytest tests/ -v
# 23 passed in 0.15s
```

---

## 📂 Project Structure

```
eros-ai/
├── src/eros/
│   ├── main.py                    # FastAPI app + dashboard route
│   ├── config/
│   │   ├── settings.py            # Pydantic settings
│   │   └── feature_flags.py       # Feature Flag provider
│   ├── agents/
│   │   ├── base.py                # BaseAgent interface
│   │   ├── security_agent.py      # Security Guardian
│   │   ├── architecture_agent.py  # Quality Inspector
│   │   ├── compliance_agent.py    # Compliance Enforcer
│   │   └── remediation_agent.py   # Fix Generator
│   ├── foundry/
│   │   └── client.py              # Microsoft Foundry IQ client
│   ├── models/
│   │   └── schemas.py             # Pydantic models
│   ├── orchestrator.py            # Async multi-agent orchestrator
│   └── templates/
│       └── dashboard.html         # Executive dashboard
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── conftest.py
├── Dockerfile                     # Multi-stage build
├── pyproject.toml                 # Project config
├── .env.example                   # Environment template
└── README.md
```

---

## 🏆 Microsoft Agents League Hackathon

**Track:** Coding and Agentic Engineering

**What we built:**
- Multi-agent code governance platform (4 specialized agents)
- Feature Flag governance — change agent behavior in real time, no redeploy
- Contextual Risk Intelligence — reachability, business impact, confidence
- Validated Remediation — AI-generated patches sandbox-tested before recommendation
- Executive dashboard — KPIs, agent status, findings, patches

**How we use Microsoft Foundry IQ:**
- All agent analysis is orchestrated through Microsoft Foundry IQ
- Circuit breaker with graceful degradation to local analysis
- Token budget management for cost control

**Judging criteria alignment:**

| Criterion | How Eros AI delivers |
|-----------|---------------------|
| Technological Implementation | FastAPI + Foundry IQ + Feature Flags + Circuit Breaker + 23 tests |
| Design | Complete dashboard with KPIs, agents, findings, patches, flags |
| Potential Impact | Addresses real problem: AI-generated code needs governance, not just scanning |
| Quality of the Idea | Feature Flag governance for agents is novel — no competitor has this as core feature |

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

Built for the **Microsoft Agents League Hackathon** by **Raul Rodriguez Mesia**.