from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


JSONType = JSON().with_variant(JSONB, "postgresql")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("usr"))
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    llm_keys: Mapped[list[UserLLMKey]] = relationship("UserLLMKey", back_populates="user", cascade="all, delete-orphan")


class UserLLMKey(Base):
    __tablename__ = "user_llm_keys"
    __table_args__ = (
        Index("ix_user_llm_keys_user_provider", "user_id", "provider"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("key"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="gemini")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship("User", back_populates="llm_keys")


class SourceMonitor(Base):
    __tablename__ = "source_monitors"
    __table_args__ = (
        Index("ix_source_monitors_user_next", "user_id", "next_run_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("mon"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)  # url | rss
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    ingest_source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="news")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    frequency_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowRunLog(Base):
    __tablename__ = "workflow_run_logs"
    __table_args__ = (
        Index("ix_workflow_run_logs_user_started", "user_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("wrk"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    details_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)


class LLMRunLog(Base):
    __tablename__ = "llm_run_logs"
    __table_args__ = (
        Index("ix_llm_run_logs_user_created", "user_id", "created_at"),
        Index("ix_llm_run_logs_trace", "trace_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("llm"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index("ix_companies_user_name", "user_id", "name"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("cmp"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    headquarters: Mapped[str | None] = mapped_column(String(120), nullable=True)
    watchlist_tier: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents: Mapped[list[Document]] = relationship("Document", back_populates="company")
    events: Mapped[list[Event]] = relationship("Event", back_populates="company")


class WatchlistCompany(Base):
    __tablename__ = "watchlist_companies"
    __table_args__ = (
        Index("ix_watchlist_companies_user_company", "user_id", "company_id"),
        UniqueConstraint("user_id", "company_id", name="uq_watchlist_user_company"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("wlc"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source_url", "hash", "user_id", name="uq_source_hash_user"),
        Index("ix_documents_user_pub", "user_id", "published_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("doc"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_object_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ingestion_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)

    company: Mapped[Company | None] = relationship("Company", back_populates="documents")
    chunks: Mapped[list[Chunk]] = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_user_doc_idx", "user_id", "document_id", "chunk_index"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("chk"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    company_ids: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    event_tags: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    document: Mapped[Document] = relationship("Document", back_populates="chunks")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_user_company_time", "user_id", "company_id", "event_time"),
        Index("ix_events_user_type_importance", "user_id", "event_type", "importance"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("evt"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_chunk_ids: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    company: Mapped[Company | None] = relationship("Company", back_populates="events")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_user_company_created", "user_id", "company_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("alt"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    importance: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="dashboard")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
