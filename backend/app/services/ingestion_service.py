from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Chunk, Company, Document, Event
from app.schemas.api import IngestResponse, IngestURLRequest
from app.services.alert_service import AlertService
from app.services.embedding_service import EmbeddingService
from app.services.enrichment_service import EnrichmentService
from app.services.text_utils import estimate_tokens, extract_html_content, fingerprint_text, semantic_chunk
from app.storage.object_store import ObjectStore
from app.storage.opensearch_store import OpenSearchStore
from app.storage.qdrant_store import QdrantStore


class IngestionService:
    def __init__(
        self,
        *,
        object_store: ObjectStore,
        embedding: EmbeddingService,
        opensearch: OpenSearchStore,
        qdrant: QdrantStore,
        enrichment: EnrichmentService,
        alerts: AlertService,
    ) -> None:
        self.object_store = object_store
        self.embedding = embedding
        self.opensearch = opensearch
        self.qdrant = qdrant
        self.enrichment = enrichment
        self.alerts = alerts

    async def ingest_url(self, db: Session, req: IngestURLRequest) -> IngestResponse:
        url = str(req.url)
        html = await self._fetch_html(url)
        title, text = extract_html_content(html)
        if not text or len(text) < 120:
            raise ValueError("Unable to extract meaningful text from source")

        text_hash = fingerprint_text(text)
        existing = db.execute(
            select(Document).where(Document.source_url == url, Document.hash == text_hash)
        ).scalar_one_or_none()
        if existing:
            return IngestResponse(
                document_id=existing.id,
                status="duplicate",
                chunks_indexed=0,
                events_created=0,
            )

        company = self._resolve_company(db, req.company_name, req.company_domain, url)
        raw_key = self.object_store.put_raw_html(url, html)

        document = Document(
            source_url=url,
            source_type=req.source_type,
            title=title,
            raw_object_key=raw_key,
            language="en",
            hash=text_hash,
            published_at=datetime.utcnow(),
            company_id=company.id if company else None,
        )
        db.add(document)
        db.flush()

        chunks = semantic_chunk(text, max_tokens=700, overlap_tokens=80)
        chunk_rows: list[Chunk] = []
        for idx, chunk_text in enumerate(chunks):
            row = Chunk(
                document_id=document.id,
                chunk_index=idx,
                text=chunk_text,
                token_count=estimate_tokens(chunk_text),
                company_ids=[company.id] if company else [],
                event_tags=[],
                metadata_json={
                    "source_type": req.source_type,
                    "source_url": url,
                    "published_at": document.published_at.isoformat() if document.published_at else None,
                },
            )
            db.add(row)
            chunk_rows.append(row)

        db.flush()

        vectors = self.embedding.embed_documents([c.text for c in chunk_rows])
        index_records = []
        for c in chunk_rows:
            index_records.append(
                {
                    "chunk_id": c.id,
                    "document_id": c.document_id,
                    "text": c.text,
                    "title": title,
                    "source_url": url,
                    "source_type": req.source_type,
                    "company_ids": c.company_ids,
                    "published_at": document.published_at.isoformat() if document.published_at else None,
                }
            )

        try:
            self.qdrant.upsert(index_records, vectors)
        except Exception:
            pass

        try:
            self.opensearch.index_chunks(index_records)
        except Exception:
            pass

        enrich = self.enrichment.extract(text, req.source_type, title=title)
        event_rows: list[Event] = []
        for ev in enrich.get("events", []):
            event = Event(
                company_id=company.id if company else None,
                document_id=document.id,
                event_type=ev["event_type"],
                event_time=ev["event_time"],
                sentiment=ev.get("sentiment"),
                importance=float(ev.get("importance", 0.5)),
                confidence=float(ev.get("confidence", 0.5)),
                summary=ev.get("summary", "Market signal detected."),
                evidence_chunk_ids=[c.id for c in chunk_rows[:2]],
                metadata_json={
                    "source_type": req.source_type,
                    "source_url": url,
                },
            )
            db.add(event)
            event_rows.append(event)

        db.flush()
        self.alerts.evaluate_and_create_alerts(db, event_rows)
        db.commit()

        return IngestResponse(
            document_id=document.id,
            status="indexed",
            chunks_indexed=len(chunk_rows),
            events_created=len(event_rows),
        )

    async def ingest_rss(self, db: Session, feed_url: str, source_type: str, limit: int) -> dict:
        parsed = feedparser.parse(feed_url)
        results = []
        for entry in parsed.entries[:limit]:
            link = entry.get("link")
            if not link:
                continue
            req = IngestURLRequest(url=link, source_type=source_type)
            try:
                result = await self.ingest_url(db, req)
                results.append({"url": link, "status": result.status, "document_id": result.document_id})
            except Exception as exc:
                results.append({"url": link, "status": f"failed: {exc}"})
        return {"feed_url": feed_url, "results": results, "processed": len(results)}

    async def ingest_report_bytes(
        self,
        db: Session,
        *,
        file_name: str,
        data: bytes,
        source_type: str,
        company_name: str | None = None,
        company_domain: str | None = None,
    ) -> IngestResponse:
        text = data.decode("utf-8", errors="ignore")
        if len(text.strip()) < 120:
            raise ValueError("Uploaded report has insufficient text content")

        raw_key = self.object_store.put_raw_bytes(file_name, data, content_type="application/octet-stream")
        company = self._resolve_company(db, company_name, company_domain, source_url=f"upload://{file_name}")

        text_hash = fingerprint_text(text)
        document = Document(
            source_url=f"upload://{file_name}",
            source_type=source_type,
            title=file_name,
            raw_object_key=raw_key,
            language="en",
            hash=text_hash,
            published_at=datetime.utcnow(),
            company_id=company.id if company else None,
        )
        db.add(document)
        db.flush()

        chunks = semantic_chunk(text, max_tokens=700, overlap_tokens=80)
        chunk_rows: list[Chunk] = []
        for idx, chunk_text in enumerate(chunks):
            row = Chunk(
                document_id=document.id,
                chunk_index=idx,
                text=chunk_text,
                token_count=estimate_tokens(chunk_text),
                company_ids=[company.id] if company else [],
                event_tags=[],
                metadata_json={
                    "source_type": source_type,
                    "source_url": document.source_url,
                    "published_at": document.published_at.isoformat(),
                },
            )
            db.add(row)
            chunk_rows.append(row)

        db.flush()

        vectors = self.embedding.embed_documents([c.text for c in chunk_rows])
        index_records = []
        for c in chunk_rows:
            index_records.append(
                {
                    "chunk_id": c.id,
                    "document_id": c.document_id,
                    "text": c.text,
                    "title": document.title,
                    "source_url": document.source_url,
                    "source_type": source_type,
                    "company_ids": c.company_ids,
                    "published_at": document.published_at.isoformat(),
                }
            )

        try:
            self.qdrant.upsert(index_records, vectors)
            self.opensearch.index_chunks(index_records)
        except Exception:
            pass

        enrich = self.enrichment.extract(text, source_type, title=file_name)
        event_rows: list[Event] = []
        for ev in enrich.get("events", []):
            event = Event(
                company_id=company.id if company else None,
                document_id=document.id,
                event_type=ev["event_type"],
                event_time=ev["event_time"],
                sentiment=ev.get("sentiment"),
                importance=float(ev.get("importance", 0.5)),
                confidence=float(ev.get("confidence", 0.5)),
                summary=ev.get("summary", "Market signal detected from report."),
                evidence_chunk_ids=[c.id for c in chunk_rows[:2]],
                metadata_json={"source_type": source_type, "source_url": document.source_url},
            )
            db.add(event)
            event_rows.append(event)

        db.flush()
        self.alerts.evaluate_and_create_alerts(db, event_rows)
        db.commit()

        return IngestResponse(
            document_id=document.id,
            status="indexed",
            chunks_indexed=len(chunk_rows),
            events_created=len(event_rows),
        )

    async def _fetch_html(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _resolve_company(
        self,
        db: Session,
        company_name: str | None,
        company_domain: str | None,
        source_url: str,
    ) -> Company | None:
        domain = company_domain or self._domain_from_url(source_url)

        if domain:
            existing = db.execute(select(Company).where(Company.domain == domain)).scalar_one_or_none()
            if existing:
                return existing

        if company_name:
            existing_by_name = db.execute(select(Company).where(Company.name == company_name)).scalar_one_or_none()
            if existing_by_name:
                if domain and not existing_by_name.domain:
                    existing_by_name.domain = domain
                return existing_by_name

            company = Company(name=company_name, domain=domain, watchlist_tier=1)
            db.add(company)
            db.flush()
            return company

        return None

    @staticmethod
    def _domain_from_url(url: str) -> str | None:
        parsed = urlparse(url)
        host = parsed.netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or None
