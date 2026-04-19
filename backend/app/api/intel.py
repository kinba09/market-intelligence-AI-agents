from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.container import get_services
from app.core.database import get_db
from app.models.entities import Alert, Event
from app.schemas.api import (
    AlertOut,
    CompetitorReportRequest,
    CompetitorReportResponse,
    EventOut,
)


router = APIRouter(tags=["intel"])


@router.get("/events", response_model=list[EventOut])
def list_events(
    company_id: str | None = None,
    days: int = 14,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[EventOut]:
    cutoff = datetime.utcnow() - timedelta(days=max(1, min(days, 120)))
    stmt = select(Event).where(Event.event_time >= cutoff).order_by(Event.event_time.desc()).limit(max(1, min(limit, 500)))
    if company_id:
        stmt = stmt.where(Event.company_id == company_id)
    rows = db.execute(stmt).scalars().all()
    return [
        EventOut(
            event_id=e.id,
            company_id=e.company_id,
            event_type=e.event_type,
            event_time=e.event_time,
            sentiment=e.sentiment,
            importance=e.importance,
            confidence=e.confidence,
            summary=e.summary,
        )
        for e in rows
    ]


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    company_id: str | None = None,
    days: int = 7,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    cutoff = datetime.utcnow() - timedelta(days=max(1, min(days, 120)))
    stmt = select(Alert).where(Alert.created_at >= cutoff).order_by(Alert.created_at.desc()).limit(max(1, min(limit, 500)))
    if company_id:
        stmt = stmt.where(Alert.company_id == company_id)
    rows = db.execute(stmt).scalars().all()

    return [
        AlertOut(
            alert_id=a.id,
            company_id=a.company_id,
            event_id=a.event_id,
            alert_type=a.alert_type,
            priority=a.priority,
            confidence=a.confidence,
            importance=a.importance,
            message=a.message,
            created_at=a.created_at,
        )
        for a in rows
    ]


@router.post("/alerts/evaluate")
def evaluate_recent_alerts(db: Session = Depends(get_db)) -> dict:
    services = get_services()
    events = db.execute(
        select(Event).where(Event.created_at >= datetime.utcnow() - timedelta(hours=2))
    ).scalars().all()
    alerts = services.alerts.evaluate_and_create_alerts(db, events)
    db.commit()
    return {"alerts_created": len(alerts)}


@router.post("/reports/competitor-summary", response_model=CompetitorReportResponse)
def competitor_summary(req: CompetitorReportRequest, db: Session = Depends(get_db)) -> CompetitorReportResponse:
    services = get_services()
    report = services.reports.competitor_summary(db, req.company_ids, req.days)
    return CompetitorReportResponse(report_markdown=report, generated_at=datetime.utcnow())
