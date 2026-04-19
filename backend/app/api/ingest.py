from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.container import get_services
from app.core.database import get_db
from app.models.entities import User
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
async def ingest_url(
    req: IngestURLRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IngestResponse:
    try:
        services = get_services()
        llm_cfg = services.llm_config.get_default_runtime_config(db, current_user.id)
        trace_id = f"ing_{uuid4().hex[:12]}"
        return await _service().ingest_url(
            db,
            req,
            user_id=current_user.id,
            llm_config=llm_cfg,
            trace_id=trace_id,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rss")
async def ingest_rss(
    req: IngestRSSRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        services = get_services()
        llm_cfg = services.llm_config.get_default_runtime_config(db, current_user.id)
        return await _service().ingest_rss(
            db,
            str(req.feed_url),
            req.source_type,
            req.limit,
            user_id=current_user.id,
            llm_config=llm_cfg,
        )
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
    current_user: User = Depends(get_current_user),
) -> IngestResponse:
    try:
        data = await file.read()
        services = get_services()
        llm_cfg = services.llm_config.get_default_runtime_config(db, current_user.id)
        trace_id = f"ing_{uuid4().hex[:12]}"
        return await _service().ingest_report_bytes(
            db,
            user_id=current_user.id,
            file_name=file.filename or "report.txt",
            data=data,
            source_type=source_type,
            company_name=company_name,
            company_domain=company_domain,
            llm_config=llm_cfg,
            trace_id=trace_id,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
