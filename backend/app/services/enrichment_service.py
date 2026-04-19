from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.services.llm_config_service import RuntimeLLMConfig
from app.services.llm_service import LLMRunContext, LLMService
from app.services.text_utils import keyword_hits, parse_possible_date


EVENT_KEYWORDS: dict[str, list[str]] = {
    "funding": ["raised", "series a", "series b", "investment", "funding round"],
    "pricing_change": ["pricing", "price", "discount", "plan", "subscription"],
    "hiring_spike": ["hiring", "open roles", "job openings", "we are hiring"],
    "product_launch": ["launch", "released", "new product", "feature rollout"],
    "partnership": ["partnership", "collaboration", "alliance", "integrated with"],
}

SOURCE_CREDIBILITY = {
    "news": 0.75,
    "company_site": 0.80,
    "jobs": 0.70,
    "social": 0.55,
    "report": 0.85,
}

EVENT_SEVERITY = {
    "funding": 0.90,
    "pricing_change": 0.85,
    "hiring_spike": 0.70,
    "product_launch": 0.80,
    "partnership": 0.72,
    "trend": 0.65,
}


@dataclass
class ExtractedEvent:
    event_type: str
    summary: str
    sentiment: str
    confidence: float
    event_time: datetime


class EnrichmentService:
    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    def extract(
        self,
        text: str,
        source_type: str,
        *,
        title: str | None = None,
        llm_config: RuntimeLLMConfig | None = None,
        run_ctx: LLMRunContext | None = None,
    ) -> dict[str, Any]:
        excerpt = text[:8000]
        system_prompt = (
            "You are an information extraction engine for market intelligence. "
            "Extract companies, events, and sentiment from evidence-only text. "
            "Return valid JSON with keys: entities, events, sentiment. "
            "events[] must include event_type, summary, confidence, sentiment, event_time."
        )
        user_prompt = f"Title: {title or 'N/A'}\nSource type: {source_type}\nText:\n{excerpt}"

        fallback = {
            "entities": {"companies": []},
            "events": [],
            "sentiment": "neutral",
        }
        llm_payload = self.llm.generate_json(
            system_prompt,
            user_prompt,
            fallback=fallback,
            llm_config=llm_config,
            run_ctx=run_ctx,
        )

        events = self._coerce_events(llm_payload.get("events", []), source_type)
        if not events:
            events = self._fallback_events(text, source_type)

        entities = llm_payload.get("entities", {"companies": []})
        sentiment = llm_payload.get("sentiment", "neutral")

        return {
            "entities": entities,
            "events": [
                {
                    "event_type": e.event_type,
                    "summary": e.summary,
                    "sentiment": e.sentiment,
                    "confidence": e.confidence,
                    "event_time": e.event_time,
                    "importance": self.score_event(
                        event_type=e.event_type,
                        source_type=source_type,
                        watchlist_match=0.8,
                        social_velocity=0.4 if source_type != "social" else 0.7,
                        novelty=0.6,
                    ),
                }
                for e in events
            ],
            "sentiment": sentiment,
        }

    def score_event(
        self,
        *,
        event_type: str,
        source_type: str,
        watchlist_match: float,
        social_velocity: float,
        novelty: float,
    ) -> float:
        source_credibility = SOURCE_CREDIBILITY.get(source_type, 0.6)
        event_severity = EVENT_SEVERITY.get(event_type, 0.6)

        score = (
            0.35 * source_credibility
            + 0.25 * event_severity
            + 0.20 * watchlist_match
            + 0.10 * social_velocity
            + 0.10 * novelty
        )
        return max(0.0, min(1.0, round(score, 4)))

    def _coerce_events(self, raw_events: list[dict[str, Any]], source_type: str) -> list[ExtractedEvent]:
        parsed: list[ExtractedEvent] = []
        for raw in raw_events[:8]:
            event_type = str(raw.get("event_type", "trend")).strip() or "trend"
            summary = str(raw.get("summary", "Market update detected.")).strip()
            sentiment = str(raw.get("sentiment", "neutral")).strip().lower()
            confidence = float(raw.get("confidence", 0.6))
            confidence = max(0.0, min(1.0, confidence))
            event_time = parse_possible_date(raw.get("event_time")) or datetime.utcnow()
            parsed.append(
                ExtractedEvent(
                    event_type=event_type,
                    summary=summary,
                    sentiment=sentiment,
                    confidence=confidence,
                    event_time=event_time,
                )
            )
        return parsed

    def _fallback_events(self, text: str, source_type: str) -> list[ExtractedEvent]:
        lower = text.lower()
        detected: list[ExtractedEvent] = []
        for event_type, words in EVENT_KEYWORDS.items():
            if keyword_hits(lower, words) > 0:
                detected.append(
                    ExtractedEvent(
                        event_type=event_type,
                        summary=f"Detected {event_type.replace('_', ' ')} signal from keyword evidence.",
                        sentiment="neutral",
                        confidence=0.55,
                        event_time=datetime.utcnow(),
                    )
                )

        if not detected:
            detected.append(
                ExtractedEvent(
                    event_type="trend",
                    summary="General market trend update detected.",
                    sentiment="neutral",
                    confidence=0.40,
                    event_time=datetime.utcnow(),
                )
            )
        return detected
