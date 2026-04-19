from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models.entities import SourceMonitor
from app.schemas.api import IngestURLRequest
from app.services.ingestion_service import IngestionService


class SchedulerService:
    def __init__(
        self,
        *,
        scheduler: AsyncIOScheduler,
        session_factory: sessionmaker,
        ingestion_service: IngestionService,
        llm_config_service,
        llmops_service,
        interval_minutes: int,
    ) -> None:
        self.scheduler = scheduler
        self.session_factory = session_factory
        self.ingestion_service = ingestion_service
        self.llm_config_service = llm_config_service
        self.llmops_service = llmops_service
        self.interval_minutes = max(5, interval_minutes)

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.add_job(self.run_due_monitors, "interval", minutes=self.interval_minutes, id="run_due_monitors")
            self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def run_due_monitors(self) -> None:
        db = self.session_factory()
        try:
            now = datetime.utcnow()
            due_monitors = db.execute(
                select(SourceMonitor).where(
                    SourceMonitor.enabled.is_(True),
                    SourceMonitor.next_run_at <= now,
                )
            ).scalars().all()

            for monitor in due_monitors:
                started = datetime.utcnow()
                trace_id = f"sched_{monitor.id}_{int(started.timestamp())}"
                llm_cfg = self.llm_config_service.get_default_runtime_config(db, monitor.user_id)
                status = "success"
                details: dict = {
                    "monitor_id": monitor.id,
                    "source_type": monitor.source_type,
                    "source_url": monitor.source_url,
                }

                try:
                    if monitor.source_type == "url":
                        req = IngestURLRequest(url=monitor.source_url, source_type=monitor.ingest_source_type)
                        await self.ingestion_service.ingest_url(
                            db,
                            req,
                            user_id=monitor.user_id,
                            llm_config=llm_cfg,
                            trace_id=trace_id,
                        )
                    else:
                        await self.ingestion_service.ingest_rss(
                            db,
                            monitor.source_url,
                            monitor.ingest_source_type,
                            limit=5,
                            user_id=monitor.user_id,
                            llm_config=llm_cfg,
                        )
                except Exception as exc:
                    status = "failed"
                    details["error"] = str(exc)

                monitor.last_run_at = datetime.utcnow()
                monitor.next_run_at = datetime.utcnow() + timedelta(hours=monitor.frequency_hours)
                monitor.last_status = status
                monitor.last_error = details.get("error")

                self.llmops_service.log_workflow_run(
                    db=db,
                    user_id=monitor.user_id,
                    workflow_name="daily_source_monitor",
                    status=status,
                    started_at=started,
                    ended_at=datetime.utcnow(),
                    details=details,
                )

            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
