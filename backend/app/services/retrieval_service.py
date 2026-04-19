from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Chunk, Document
from app.services.embedding_service import EmbeddingService
from app.services.text_utils import keyword_hits
from app.storage.opensearch_store import OpenSearchStore
from app.storage.qdrant_store import QdrantStore


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    text: str
    source_url: str
    title: str | None
    published_at: datetime | None
    score: float


class RetrievalService:
    def __init__(self, embedding: EmbeddingService, opensearch: OpenSearchStore, qdrant: QdrantStore) -> None:
        self.embedding = embedding
        self.opensearch = opensearch
        self.qdrant = qdrant

    def hybrid_search(
        self,
        db: Session,
        *,
        question: str,
        filters: dict[str, Any],
        top_k: int,
    ) -> list[RetrievedChunk]:
        bm25_hits = self.opensearch.search(question, filters=filters, limit=max(40, top_k * 4))
        query_vec = self.embedding.embed_query(question)
        vector_hits = self.qdrant.search(query_vec, filters=filters, limit=max(40, top_k * 4))

        fused = self._fuse(bm25_hits, vector_hits)
        if not fused:
            return []

        top_ids = [chunk_id for chunk_id, _ in sorted(fused.items(), key=lambda x: x[1], reverse=True)[:120]]
        rows = db.execute(
            select(Chunk, Document).join(Document, Chunk.document_id == Document.id).where(Chunk.id.in_(top_ids))
        ).all()

        row_map: dict[str, tuple[Chunk, Document]] = {chunk.id: (chunk, doc) for chunk, doc in rows}
        question_terms = [t for t in question.lower().split() if len(t) > 2]

        reranked: list[RetrievedChunk] = []
        for chunk_id, base_score in sorted(fused.items(), key=lambda x: x[1], reverse=True):
            pair = row_map.get(chunk_id)
            if not pair:
                continue
            chunk, doc = pair
            overlap = keyword_hits(chunk.text, question_terms)
            freshness = self._freshness_boost(doc.published_at)
            score = 0.7 * base_score + 0.2 * min(overlap / 6.0, 1.0) + 0.1 * freshness

            reranked.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    text=chunk.text,
                    source_url=doc.source_url,
                    title=doc.title,
                    published_at=doc.published_at,
                    score=round(score, 6),
                )
            )

        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked[:top_k]

    @staticmethod
    def _fuse(bm25_hits: list[dict[str, Any]], vector_hits: list[dict[str, Any]]) -> dict[str, float]:
        fused: dict[str, float] = {}
        for rank, hit in enumerate(bm25_hits, start=1):
            fused[hit["chunk_id"]] = fused.get(hit["chunk_id"], 0.0) + 0.45 * (1.0 / (rank + 20))
        for rank, hit in enumerate(vector_hits, start=1):
            fused[hit["chunk_id"]] = fused.get(hit["chunk_id"], 0.0) + 0.45 * (1.0 / (rank + 20))
        return fused

    @staticmethod
    def _freshness_boost(published_at: datetime | None) -> float:
        if not published_at:
            return 0.2
        age_days = (datetime.utcnow() - published_at).days
        if age_days <= 7:
            return 1.0
        if age_days <= 30:
            return 0.7
        if age_days <= 90:
            return 0.45
        return 0.2
