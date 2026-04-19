from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class IngestURLRequest(BaseModel):
    url: HttpUrl
    source_type: str = Field(default="company_site")
    company_name: str | None = None
    company_domain: str | None = None


class IngestRSSRequest(BaseModel):
    feed_url: HttpUrl
    source_type: str = Field(default="news")
    limit: int = Field(default=10, ge=1, le=50)


class IngestResponse(BaseModel):
    document_id: str
    status: str
    chunks_indexed: int
    events_created: int


class AskRequest(BaseModel):
    question: str
    company_ids: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None
    top_k: int = Field(default=10, ge=3, le=20)


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    source_url: str
    title: str | None = None
    published_at: datetime | None = None


class AskResponse(BaseModel):
    answer: str
    confidence: float
    citations: list[Citation]
    trace: dict[str, Any]


class CompanyUpsertRequest(BaseModel):
    name: str
    domain: str | None = None
    industry: str | None = None
    headquarters: str | None = None
    watchlist_tier: int = Field(default=1, ge=0, le=5)


class WatchlistResponse(BaseModel):
    company_id: str
    name: str
    watchlist_tier: int


class EventOut(BaseModel):
    event_id: str
    company_id: str | None
    event_type: str
    event_time: datetime
    sentiment: str | None
    importance: float
    confidence: float
    summary: str


class AlertOut(BaseModel):
    alert_id: str
    company_id: str | None
    event_id: str | None
    alert_type: str
    priority: str
    confidence: float
    importance: float
    message: str
    created_at: datetime


class CompetitorReportRequest(BaseModel):
    company_ids: list[str] = Field(default_factory=list)
    days: int = Field(default=14, ge=1, le=120)


class CompetitorReportResponse(BaseModel):
    report_markdown: str
    generated_at: datetime
