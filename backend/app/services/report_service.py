from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Company, Event
from app.services.llm_config_service import RuntimeLLMConfig
from app.services.llm_service import LLMRunContext, LLMService


class ReportService:
    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    def competitor_summary(
        self,
        db: Session,
        user_id: str,
        company_ids: list[str],
        *,
        days: int = 14,
        llm_config: RuntimeLLMConfig | None = None,
        trace_id: str | None = None,
    ) -> str:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(Event)
            .where(Event.user_id == user_id, Event.event_time >= cutoff)
            .order_by(Event.event_time.desc())
        )
        if company_ids:
            stmt = stmt.where(Event.company_id.in_(company_ids))

        events = db.execute(stmt).scalars().all()
        if not events:
            return "No events found for the selected window."

        company_map = {
            c.id: c.name
            for c in db.execute(
                select(Company).where(Company.user_id == user_id, Company.id.in_([e.company_id for e in events if e.company_id]))
            ).scalars().all()
        }

        lines = []
        for e in events[:80]:
            cname = company_map.get(e.company_id or "", "Unknown")
            lines.append(
                f"- {e.event_time.date()} | {cname} | {e.event_type} | importance={e.importance:.2f} | {e.summary}"
            )

        system_prompt = (
            "You are a market intelligence strategist. Write in a conversational but concise style. "
            "Create sections: What changed, Why it matters, Recommended next actions. "
            "Use only the provided event evidence."
        )
        user_prompt = "Events:\n" + "\n".join(lines)
        try:
            text = self.llm.generate_text(
                system_prompt,
                user_prompt,
                temperature=0.2,
                llm_config=llm_config,
                run_ctx=LLMRunContext(db=db, user_id=user_id, trace_id=trace_id, endpoint="report_summary"),
            )
        except Exception:
            text = "No LLM response available"

        if "No LLM key configured" in text or "No LLM response available" in text:
            return "# Competitor Summary\n\n" + "\n".join(lines[:25])
        return text
