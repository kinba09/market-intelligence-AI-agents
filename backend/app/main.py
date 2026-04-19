from __future__ import annotations

from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    auth_router,
    automation_router,
    health_router,
    ingest_router,
    intel_router,
    query_router,
    watchlist_router,
)
from app.core.config import get_settings
from app.core.container import get_services
from app.core.database import Base, SessionLocal, engine
from app.services.ingestion_service import IngestionService
from app.services.scheduler_service import SchedulerService


settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    services = get_services()
    try:
        services.opensearch.ensure_index()
    except Exception:
        pass
    try:
        services.qdrant.ensure_collection(vector_size=services.embedding.vector_size)
    except Exception:
        pass

    ingestion = IngestionService(
        object_store=services.object_store,
        embedding=services.embedding,
        opensearch=services.opensearch,
        qdrant=services.qdrant,
        enrichment=services.enrichment,
        alerts=services.alerts,
    )
    scheduler = SchedulerService(
        scheduler=AsyncIOScheduler(),
        session_factory=SessionLocal,
        ingestion_service=ingestion,
        llm_config_service=services.llm_config,
        llmops_service=services.llmops,
        interval_minutes=settings.scheduler_interval_minutes,
    )
    scheduler.start()
    app.state.scheduler = scheduler


@app.on_event("shutdown")
def shutdown_event() -> None:
    scheduler: SchedulerService | None = getattr(app.state, "scheduler", None)
    if scheduler:
        scheduler.shutdown()


app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(ingest_router, prefix=settings.api_prefix)
app.include_router(query_router, prefix=settings.api_prefix)
app.include_router(watchlist_router, prefix=settings.api_prefix)
app.include_router(intel_router, prefix=settings.api_prefix)
app.include_router(automation_router, prefix=settings.api_prefix)


frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
def landing() -> FileResponse:
    path = frontend_dir / "landing.html"
    if path.exists():
        return FileResponse(path)
    return FileResponse(frontend_dir / "index.html")


@app.get("/login")
def login_page() -> FileResponse:
    path = frontend_dir / "login.html"
    if path.exists():
        return FileResponse(path)
    return FileResponse(frontend_dir / "index.html")


@app.get("/app")
def app_page() -> FileResponse:
    path = frontend_dir / "dashboard.html"
    if path.exists():
        return FileResponse(path)
    return FileResponse(frontend_dir / "index.html")
