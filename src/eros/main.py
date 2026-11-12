from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from eros.config.feature_flags import FeatureFlags
from eros.config.settings import settings
from eros.models.schemas import AnalysisRequest, AnalysisResult, HealthResponse
from eros.orchestrator import orchestrator

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

print(f"[DEBUG] BASE_DIR: {BASE_DIR}")
print(f"[DEBUG] STATIC_DIR: {STATIC_DIR}")
print(f"[DEBUG] STATIC_DIR.exists(): {STATIC_DIR.exists()}")
print(f"[DEBUG] STATIC_DIR contents: {list(STATIC_DIR.iterdir()) if STATIC_DIR.exists() else 'N/A'}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    dashboard_path = TEMPLATES_DIR / "dashboard.html"
    if dashboard_path.exists():
        return HTMLResponse(content=dashboard_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        flags=FeatureFlags.all_flags(),
    )


@app.get("/flags")
async def get_flags():
    return FeatureFlags.snapshot()


@app.post("/flags/{flag_name}")
async def set_flag(flag_name: str, value: bool):
    from eros.config.feature_flags import FeatureFlag

    try:
        flag = FeatureFlag(flag_name)
        FeatureFlags.set_override(flag, value)
        return {"flag": flag_name, "value": value, "status": "updated"}
    except ValueError:
        return JSONResponse(status_code=400, content={"error": f"Unknown flag: {flag_name}"})


@app.post("/analyze", response_model=AnalysisResult)
async def analyze(request: AnalysisRequest) -> AnalysisResult:
    return await orchestrator.run(request)
