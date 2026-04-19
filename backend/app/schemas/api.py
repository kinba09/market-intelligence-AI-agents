from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    user_id: str
    email: EmailStr


class LLMKeyUpsertRequest(BaseModel):
    label: str = Field(default="default", max_length=64)
    provider: str = Field(default="gemini", max_length=32)
    model_name: str = Field(default="gemini-2.0-flash", max_length=128)
    api_key: str = Field(min_length=8)
    base_url: str | None = None
    is_default: bool = True


class LLMKeyOut(BaseModel):
    key_id: str
    label: str
    provider: str
    model_name: str
    base_url: str | None
    is_default: bool
    masked_api_key: str


class SourceMonitorCreateRequest(BaseModel):
    label: str = Field(max_length=120)
    source_type: str = Field(pattern="^(url|rss)$")
    source_url: HttpUrl
    ingest_source_type: str = Field(default="news", max_length=50)
    enabled: bool = True
    frequency_hours: int = Field(default=24, ge=1, le=168)


class SourceMonitorOut(BaseModel):
    monitor_id: str
    label: str
    source_type: str
    source_url: str
    ingest_source_type: str
    enabled: bool
    frequency_hours: int
    last_run_at: datetime | None
    next_run_at: datetime
    last_status: str | None
    last_error: str | None


class WorkflowRunOut(BaseModel):
    run_id: str
    workflow_name: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    details: dict[str, Any]


class LLMRunOut(BaseModel):
    run_id: str
    trace_id: str | None
    endpoint: str | None
    provider: str
    model_name: str
    latency_ms: int
    success: bool
    error: str | None
    created_at: datetime


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
    trace_id: str


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
    trace_id: str
