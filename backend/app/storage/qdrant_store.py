from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchAny, PointStruct, VectorParams

from app.core.config import get_settings


class QdrantStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.collection = settings.qdrant_collection
        self.default_vector_size = settings.vector_size
        self.client = QdrantClient(url=settings.qdrant_url)

    def ensure_collection(self, vector_size: int | None = None) -> None:
        size = vector_size or self.default_vector_size
        collections = self.client.get_collections().collections
        if any(c.name == self.collection for c in collections):
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=size, distance=Distance.COSINE),
        )

    def upsert(self, records: list[dict[str, Any]], vectors: list[list[float]]) -> None:
        if not records:
            return
        self.ensure_collection(vector_size=len(vectors[0]))
        points = []
        for rec, vec in zip(records, vectors):
            payload = {
                "chunk_id": rec["chunk_id"],
                "document_id": rec["document_id"],
                "user_id": rec.get("user_id"),
                "company_ids": rec.get("company_ids", []),
                "source_type": rec.get("source_type"),
                "published_at": rec.get("published_at"),
            }
            # Qdrant supports numeric or UUID point IDs. We derive stable UUIDs from chunk IDs.
            point_id = str(uuid5(NAMESPACE_URL, f"chunk:{rec['chunk_id']}"))
            points.append(PointStruct(id=point_id, vector=vec, payload=payload))
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, query_vector: list[float], filters: dict[str, Any], limit: int = 40) -> list[dict[str, Any]]:
        must = []
        if user_id := filters.get("user_id"):
            must.append(FieldCondition(key="user_id", match=MatchAny(any=[user_id])))
        if company_ids := filters.get("company_ids"):
            must.append(FieldCondition(key="company_ids", match=MatchAny(any=company_ids)))
        if source_types := filters.get("source_types"):
            must.append(FieldCondition(key="source_type", match=MatchAny(any=source_types)))

        query_filter = Filter(must=must) if must else None
        try:
            hits = self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception:
            return []

        out: list[dict[str, Any]] = []
        for h in hits:
            payload = h.payload or {}
            chunk_id = payload.get("chunk_id")
            if not chunk_id:
                continue
            out.append({"chunk_id": chunk_id, "score": float(h.score)})
        return out
