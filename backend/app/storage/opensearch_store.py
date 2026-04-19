from __future__ import annotations

from typing import Any

from opensearchpy import OpenSearch

from app.core.config import get_settings


class OpenSearchStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.index = settings.opensearch_index
        client_kwargs = {
            "hosts": [settings.opensearch_url],
            "use_ssl": settings.opensearch_url.startswith("https://"),
            "verify_certs": False,
            "timeout": 30,
        }
        if settings.opensearch_user and settings.opensearch_password:
            client_kwargs["http_auth"] = (settings.opensearch_user, settings.opensearch_password)
        self.client = OpenSearch(**client_kwargs)

    def ensure_index(self) -> None:
        if self.client.indices.exists(index=self.index):
            return
        mapping = {
            "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},
                    "text": {"type": "text"},
                    "title": {"type": "text"},
                    "source_url": {"type": "keyword"},
                    "source_type": {"type": "keyword"},
                    "company_ids": {"type": "keyword"},
                    "published_at": {"type": "date"},
                }
            },
        }
        self.client.indices.create(index=self.index, body=mapping)

    def index_chunks(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        self.ensure_index()
        for rec in records:
            self.client.index(index=self.index, id=rec["chunk_id"], body=rec, refresh=False)

    def search(self, query: str, filters: dict[str, Any], limit: int = 40) -> list[dict[str, Any]]:
        must: list[dict[str, Any]] = [{"multi_match": {"query": query, "fields": ["text^2", "title"]}}]
        flt: list[dict[str, Any]] = []

        if company_ids := filters.get("company_ids"):
            flt.append({"terms": {"company_ids": company_ids}})
        if source_types := filters.get("source_types"):
            flt.append({"terms": {"source_type": source_types}})
        if date_from := filters.get("date_from"):
            flt.append({"range": {"published_at": {"gte": date_from.isoformat()}}})
        if date_to := filters.get("date_to"):
            flt.append({"range": {"published_at": {"lte": date_to.isoformat()}}})

        body = {
            "size": limit,
            "query": {
                "bool": {
                    "must": must,
                    "filter": flt,
                }
            },
        }
        try:
            response = self.client.search(index=self.index, body=body)
        except Exception:
            return []

        hits = []
        for hit in response.get("hits", {}).get("hits", []):
            hits.append(
                {
                    "chunk_id": hit.get("_id"),
                    "score": float(hit.get("_score", 0.0)),
                }
            )
        return hits
