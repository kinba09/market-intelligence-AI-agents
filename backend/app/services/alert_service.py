from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Alert, Event


class AlertService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def evaluate_and_create_alerts(self, db: Session, events: list[Event]) -> list[Alert]:
        created: list[Alert] = []
        cutoff = datetime.utcnow() - timedelta(hours=6)

        for event in events:
            priority = self._classify_priority(event.importance, event.confidence)
            if priority is None:
                continue

            # cooldown to prevent duplicate alert storms
            existing = db.execute(
                select(Alert).where(
                    Alert.user_id == event.user_id,
                    Alert.company_id == event.company_id,
                    Alert.alert_type == event.event_type,
                    Alert.created_at >= cutoff,
                )
            ).scalar_one_or_none()
            if existing:
                continue

            alert = Alert(
                user_id=event.user_id,
                company_id=event.company_id,
                event_id=event.id,
                alert_type=event.event_type,
                priority=priority,
                confidence=event.confidence,
                importance=event.importance,
                status="queued",
                channel="dashboard",
                message=event.summary,
                metadata_json={"event_time": event.event_time.isoformat()},
            )
            db.add(alert)
            created.append(alert)

        if created:
            db.flush()
        return created

    def _classify_priority(self, importance: float, confidence: float) -> str | None:
        if importance >= self.settings.alert_importance_high and confidence >= self.settings.alert_confidence_high:
            return "high"
        if importance >= self.settings.alert_importance_medium and confidence >= self.settings.alert_confidence_medium:
            return "medium"
        return None
