from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import LLMRunLog, WorkflowRunLog


class LLMOpsService:
    def __init__(self) -> None:
        self.log_dir = Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.llm_log_file = self.log_dir / "llm_runs.jsonl"
        self.workflow_log_file = self.log_dir / "workflow_runs.jsonl"

    def log_llm_run(
        self,
        *,
        db: Session | None,
        user_id: str | None,
        trace_id: str | None,
        endpoint: str | None,
        provider: str,
        model_name: str,
        prompt_chars: int,
        response_chars: int,
        latency_ms: int,
        success: bool,
        error: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        metadata = metadata or {}
        now = datetime.utcnow()

        if db is not None:
            db.add(
                LLMRunLog(
                    user_id=user_id,
                    trace_id=trace_id,
                    endpoint=endpoint,
                    provider=provider,
                    model_name=model_name,
                    prompt_chars=prompt_chars,
                    response_chars=response_chars,
                    latency_ms=latency_ms,
                    success=success,
                    error=error,
                    metadata_json=metadata,
                    created_at=now,
                )
            )

        payload = {
            "ts": now.isoformat(),
            "user_id": user_id,
            "trace_id": trace_id,
            "endpoint": endpoint,
            "provider": provider,
            "model_name": model_name,
            "prompt_chars": prompt_chars,
            "response_chars": response_chars,
            "latency_ms": latency_ms,
            "success": success,
            "error": error,
            "metadata": metadata,
        }
        with self.llm_log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def log_workflow_run(
        self,
        *,
        db: Session | None,
        user_id: str | None,
        workflow_name: str,
        status: str,
        started_at: datetime,
        ended_at: datetime,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}

        if db is not None:
            db.add(
                WorkflowRunLog(
                    user_id=user_id,
                    workflow_name=workflow_name,
                    status=status,
                    started_at=started_at,
                    ended_at=ended_at,
                    details_json=details,
                )
            )

        payload = {
            "user_id": user_id,
            "workflow_name": workflow_name,
            "status": status,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "details": details,
        }
        with self.workflow_log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
