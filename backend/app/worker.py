from __future__ import annotations

import asyncio

from celery import Celery
from sqlalchemy import select

from app.core.config import get_settings
from app.core.container import get_services
from app.core.database import SessionLocal
from app.models.entities import Event
from app.schemas.api import IngestURLRequest
from app.services.ingestion_service import IngestionService


settings = get_settings()
celery_app = Celery("market_intel", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task
def ingest_url_task(url: str, source_type: str = "news") -> dict:
    services = get_services()
    ingestion = IngestionService(
        object_store=services.object_store,
        embedding=services.embedding,
        opensearch=services.opensearch,
        qdrant=services.qdrant,
        enrichment=services.enrichment,
        alerts=services.alerts,
    )

    req = IngestURLRequest(url=url, source_type=source_type)
    db = SessionLocal()
    try:
        resp = asyncio.run(ingestion.ingest_url(db, req))
        return resp.model_dump()
    finally:
        db.close()


@celery_app.task
def evaluate_alerts_task() -> dict:
    services = get_services()
    db = SessionLocal()
    try:
        events = db.execute(select(Event).order_by(Event.created_at.desc()).limit(200)).scalars().all()
        alerts = services.alerts.evaluate_and_create_alerts(db, events)
        db.commit()
        return {"alerts_created": len(alerts)}
    finally:
        db.close()
