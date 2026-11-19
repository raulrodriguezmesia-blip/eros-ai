# 🛡️ EROS AI
**Sistema de razonamiento y observabilidad empresarial — Capa de confianza para código generado por IA**

*Analizar · Gobernar · Remediar · Validar*

[![Demo Video](https://img.shields.io/badge/Demo%20Video-YouTube-red)](https://youtu.be/Y5Fm0csCYQg)
[![Release](https://img.shields.io/badge/Release-v1.0--hackathon--submission-blue)](https://github.com/raulrodriguezmesia-blip/eros-ai)

> **Video de demostración (1:54):** https://youtu.be/Y5Fm0csCYQg

---

## 📌 Resumen ejecutivo (BLUF)

**EROS AI** es una plataforma autónoma de análisis y gobernanza de código diseñada como **Trust Layer** para código generado por IA y agentes autónomos. Coordina cuatro agentes especializados para detectar vulnerabilidades, auditar calidad y cumplimiento, y generar parches validados, todo bajo control en tiempo real mediante **feature flags** y orquestación con **Microsoft Foundry IQ**.

| Aspecto | Escáner / Herramienta tradicional | EROS AI |
| :--- | :--- | :--- |
| **Detección** | Reglas estáticas o hallazgos aislados | Análisis contextual (accesibilidad, impacto en negocio y confianza) |
| **Remediación** | Sugerencias o reportes sin validar | Propuesta de parche y validación en entorno aislado |
| **Gobernanza** | Cambios estáticos o redeploy de pipeline | *Feature flags* en tiempo real sin reiniciar el servicio |
| **Evidencia** | Opinión o alertas dispersas | Telemetría, trazas y pruebas verificables (*from opinion to evidence*) |

---

## 🎯 Por qué importa

1. **Contexto de riesgo:** Evalúa no solo qué falla, sino dónde expone el sistema y cuál es el impacto real.
2. **Gobernanza en tiempo real:** Permite activar o desactivar políticas y capacidades mediante *feature flags* sin redesplegar.
3. **Remediación validada:** Prioriza soluciones verificadas frente a simples sugerencias de texto.
4. **Observabilidad y trazabilidad:** Registra el flujo de ejecución y razonamiento para auditar decisiones con evidencia.

---

## 🤖 Agentes y gobernanza

* **Security Guardian:** Identifica vulnerabilidades críticas (inyección SQL, secretos expuestos, ejecución insegura, *path traversal*).
* **Quality Inspector:** Evalúa mantenibilidad, complejidad, acoplamiento y deuda técnica.
* **Compliance Officer:** Verifica políticas de seguridad y cumplimiento normativo.
* **Remediation Generator:** Sintetiza parches de código y dispara su validación.

### Indicadores de características (*Feature Flags*)

* `deep_ast_analysis`: Alterna entre análisis rápido y análisis profundo basado en AST.
* `auto_patch_generation`: Activa la generación de parches y su validación.
* `strict_compliance_mode`: Endurece el bloqueo ante hallazgos críticos.

---

## 🛠️ Stack tecnológico

* **Backend & API:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2.
* **Orquestación de IA:** Microsoft Foundry IQ (`azure-ai-projects`), con mecanismos de resiliencia (*circuit breaker*, control de presupuesto de tokens y *fallback* local).
* **Frontend / Panel:** HTML, Tailwind CSS y Alpine.js.
* **Contenedores y pruebas:** Docker, Docker Compose, `pytest` y `pytest-asyncio`.

---

## 🚀 Inicio rápido

### 1. Instalación

```bash
git clone https://github.com/raulrodriguezmesia-blip/eros-ai.git
cd eros-ai
pip install -e ".[dev]"
cp .env.example .env
```

### 2. Ejecutar el servidor y el panel

```bash
PYTHONPATH=src uvicorn eros.main:app --reload --port 8080
```

* Panel: http://localhost:8080
* Documentación interactiva (Swagger/OpenAPI): http://localhost:8080/docs

(También puedes ejecutarlo con Docker o Docker Compose según tu configuración de `.env` y puertos).

### 3. Ejecutar pruebas

```bash
python -m pytest tests/ -v
```

Estado de validación de la entrega (`v1.0-hackathon-submission`): **151/151 pruebas superadas, 69.24% de cobertura y 0 errores de linter.**

---

## 🗺️ Próximos pasos

* Exportación de métricas a Prometheus / Grafana (`/metrics`).
* Integración directa en flujos de PR (GitHub / GitLab) y extensión para VS Code.
* Políticas declarativas como código y trazabilidad criptográfica de ejecuciones.

---

## 📄 Licencia y autor

**Licencia:** MIT (ver [LICENSE](LICENSE)).

**Autor:** Raúl Rodríguez Mesia — Repositorio: https://github.com/raulrodriguezmesia-blip/eros-ai