from __future__ import annotations

from functools import lru_cache

from app.services.alert_service import AlertService
from app.services.embedding_service import EmbeddingService
from app.services.enrichment_service import EnrichmentService
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.report_service import ReportService
from app.services.retrieval_service import RetrievalService
from app.storage.object_store import ObjectStore
from app.storage.opensearch_store import OpenSearchStore
from app.storage.qdrant_store import QdrantStore


class ServiceContainer:
    def __init__(self) -> None:
        self.embedding = EmbeddingService()
        self.llm = LLMService()
        self.object_store = ObjectStore()
        self.opensearch = OpenSearchStore()
        self.qdrant = QdrantStore()
        self.alerts = AlertService()
        self.enrichment = EnrichmentService(self.llm)
        self.retrieval = RetrievalService(self.embedding, self.opensearch, self.qdrant)
        self.rag = RAGService(self.llm)
        self.reports = ReportService(self.llm)


@lru_cache(maxsize=1)
def get_services() -> ServiceContainer:
    return ServiceContainer()
