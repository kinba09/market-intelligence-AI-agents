from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.container import get_services
from app.core.database import get_db
from app.models.entities import LLMRunLog, SourceMonitor, User, WorkflowRunLog
from app.schemas.api import LLMRunOut, SourceMonitorCreateRequest, SourceMonitorOut, WorkflowRunOut
from app.schemas.api import IngestURLRequest
from app.services.ingestion_service import IngestionService


router = APIRouter(tags=["automation"])


def _ingest_service() -> IngestionService:
    services = get_services()
    return IngestionService(
        object_store=services.object_store,
        embedding=services.embedding,
        opensearch=services.opensearch,
        qdrant=services.qdrant,
        enrichment=services.enrichment,
        alerts=services.alerts,
    )


@router.post("/automation/monitors", response_model=SourceMonitorOut)
def create_monitor(
    req: SourceMonitorCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SourceMonitorOut:
    row = SourceMonitor(
        user_id=current_user.id,
        label=req.label,
        source_type=req.source_type,
        source_url=str(req.source_url),
        ingest_source_type=req.ingest_source_type,
        enabled=req.enabled,
        frequency_hours=req.frequency_hours,
        next_run_at=datetime.utcnow() + timedelta(minutes=5),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return SourceMonitorOut(
        monitor_id=row.id,
        label=row.label,
        source_type=row.source_type,
        source_url=row.source_url,
        ingest_source_type=row.ingest_source_type,
        enabled=row.enabled,
        frequency_hours=row.frequency_hours,
        last_run_at=row.last_run_at,
        next_run_at=row.next_run_at,
        last_status=row.last_status,
        last_error=row.last_error,
    )


@router.get("/automation/monitors", response_model=list[SourceMonitorOut])
def list_monitors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SourceMonitorOut]:
    rows = db.execute(
        select(SourceMonitor)
        .where(SourceMonitor.user_id == current_user.id)
        .order_by(SourceMonitor.created_at.desc())
    ).scalars().all()

    return [
        SourceMonitorOut(
            monitor_id=r.id,
            label=r.label,
            source_type=r.source_type,
            source_url=r.source_url,
            ingest_source_type=r.ingest_source_type,
            enabled=r.enabled,
            frequency_hours=r.frequency_hours,
            last_run_at=r.last_run_at,
            next_run_at=r.next_run_at,
            last_status=r.last_status,
            last_error=r.last_error,
        )
        for r in rows
    ]


@router.post("/automation/monitors/{monitor_id}/toggle")
def toggle_monitor(
    monitor_id: str,
    enabled: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    row = db.execute(
        select(SourceMonitor).where(SourceMonitor.id == monitor_id, SourceMonitor.user_id == current_user.id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Monitor not found")

    row.enabled = enabled
    row.next_run_at = datetime.utcnow() + timedelta(minutes=5)
    db.commit()
    return {"monitor_id": row.id, "enabled": row.enabled}


@router.post("/automation/monitors/{monitor_id}/run")
async def run_monitor_now(
    monitor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    row = db.execute(
        select(SourceMonitor).where(SourceMonitor.id == monitor_id, SourceMonitor.user_id == current_user.id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Monitor not found")

    services = get_services()
    llm_cfg = services.llm_config.get_default_runtime_config(db, current_user.id)
    ingestion = _ingest_service()
    trace_id = f"manual_{monitor_id}_{int(datetime.utcnow().timestamp())}"

    if row.source_type == "url":
        req = IngestURLRequest(url=row.source_url, source_type=row.ingest_source_type)
        result = await ingestion.ingest_url(
            db,
            req,
            user_id=current_user.id,
            llm_config=llm_cfg,
            trace_id=trace_id,
        )
        row.last_status = result.status
        result_payload = result.model_dump()
    else:
        rss_result = await ingestion.ingest_rss(
            db,
            row.source_url,
            row.ingest_source_type,
            limit=5,
            user_id=current_user.id,
            llm_config=llm_cfg,
        )
        row.last_status = "indexed"
        result_payload = {"rss": rss_result}

    row.last_run_at = datetime.utcnow()
    row.next_run_at = datetime.utcnow() + timedelta(hours=row.frequency_hours)
    db.commit()
    return {"status": "ok", "trace_id": trace_id, "result": result_payload}


@router.get("/ops/llm-runs", response_model=list[LLMRunOut])
def list_llm_runs(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LLMRunOut]:
    rows = db.execute(
        select(LLMRunLog)
        .where(LLMRunLog.user_id == current_user.id)
        .order_by(LLMRunLog.created_at.desc())
        .limit(max(1, min(limit, 500)))
    ).scalars().all()

    return [
        LLMRunOut(
            run_id=r.id,
            trace_id=r.trace_id,
            endpoint=r.endpoint,
            provider=r.provider,
            model_name=r.model_name,
            latency_ms=r.latency_ms,
            success=r.success,
            error=r.error,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/ops/workflow-runs", response_model=list[WorkflowRunOut])
def list_workflow_runs(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkflowRunOut]:
    rows = db.execute(
        select(WorkflowRunLog)
        .where(WorkflowRunLog.user_id == current_user.id)
        .order_by(WorkflowRunLog.started_at.desc())
        .limit(max(1, min(limit, 500)))
    ).scalars().all()

    return [
        WorkflowRunOut(
            run_id=r.id,
            workflow_name=r.workflow_name,
            status=r.status,
            started_at=r.started_at,
            ended_at=r.ended_at,
            details=r.details_json,
        )
        for r in rows
    ]
