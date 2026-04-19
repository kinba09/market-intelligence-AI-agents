from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.container import get_services
from app.core.database import get_db
from app.schemas.api import IngestResponse, IngestRSSRequest, IngestURLRequest
from app.services.ingestion_service import IngestionService


router = APIRouter(prefix="/ingest", tags=["ingestion"])


def _service() -> IngestionService:
    services = get_services()
    return IngestionService(
        object_store=services.object_store,
        embedding=services.embedding,
        opensearch=services.opensearch,
        qdrant=services.qdrant,
        enrichment=services.enrichment,
        alerts=services.alerts,
    )


@router.post("/url", response_model=IngestResponse)
async def ingest_url(req: IngestURLRequest, db: Session = Depends(get_db)) -> IngestResponse:
    try:
        return await _service().ingest_url(db, req)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rss")
async def ingest_rss(req: IngestRSSRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return await _service().ingest_rss(db, str(req.feed_url), req.source_type, req.limit)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/report", response_model=IngestResponse)
async def ingest_report(
    file: UploadFile = File(...),
    source_type: str = Form(default="report"),
    company_name: str | None = Form(default=None),
    company_domain: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> IngestResponse:
    try:
        data = await file.read()
        return await _service().ingest_report_bytes(
            db,
            file_name=file.filename or "report.txt",
            data=data,
            source_type=source_type,
            company_name=company_name,
            company_domain=company_domain,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
