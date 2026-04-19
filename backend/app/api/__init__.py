from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.api.intel import router as intel_router
from app.api.query import router as query_router
from app.api.watchlist import router as watchlist_router

__all__ = [
    "health_router",
    "ingest_router",
    "intel_router",
    "query_router",
    "watchlist_router",
]
