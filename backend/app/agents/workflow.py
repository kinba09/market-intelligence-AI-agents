from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.api import AskRequest
from app.services.llm_config_service import RuntimeLLMConfig
from app.services.llm_service import LLMRunContext, LLMService
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievedChunk, RetrievalService


@dataclass
class AgentState:
    question: str
    intent: dict[str, Any] = field(default_factory=dict)
    retrieval_filters: dict[str, Any] = field(default_factory=dict)
    candidates: list[RetrievedChunk] = field(default_factory=list)
    validated: list[RetrievedChunk] = field(default_factory=list)
    answer_payload: dict[str, Any] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)


class MarketIntelAgentWorkflow:
    def __init__(self, llm: LLMService, retrieval: RetrievalService, rag: RAGService) -> None:
        self.llm = llm
        self.retrieval = retrieval
        self.rag = rag

    def run(
        self,
        db: Session,
        req: AskRequest,
        *,
        user_id: str,
        llm_config: RuntimeLLMConfig | None = None,
        trace_id: str | None = None,
    ) -> AgentState:
        state = AgentState(question=req.question)
        self._query_understanding(state, req, db=db, user_id=user_id, llm_config=llm_config, trace_id=trace_id)
        self._retrieve(db, state, req, user_id=user_id, llm_config=llm_config)
        self._validate(state)
        self._synthesize(state, db=db, user_id=user_id, llm_config=llm_config, trace_id=trace_id)
        return state

    def _query_understanding(
        self,
        state: AgentState,
        req: AskRequest,
        *,
        db: Session,
        user_id: str,
        llm_config: RuntimeLLMConfig | None,
        trace_id: str | None,
    ) -> None:
        system_prompt = (
            "You are a query understanding agent for market intelligence. "
            "Return JSON with keys: intent_type, entities, required_time_window_days, confidence."
        )
        payload = self.llm.generate_json(
            system_prompt,
            req.question,
            fallback={
                "intent_type": "analysis",
                "entities": [],
                "required_time_window_days": 90,
                "confidence": 0.6,
            },
            llm_config=llm_config,
            run_ctx=LLMRunContext(db=db, user_id=user_id, trace_id=trace_id, endpoint="query_understanding"),
        )

        state.intent = payload
        state.retrieval_filters = {
            "company_ids": req.company_ids,
            "source_types": req.source_types,
            "date_from": req.date_from,
            "date_to": req.date_to,
        }
        state.trace["query_understanding"] = payload

    def _retrieve(
        self,
        db: Session,
        state: AgentState,
        req: AskRequest,
        *,
        user_id: str,
        llm_config: RuntimeLLMConfig | None,
    ) -> None:
        candidates = self.retrieval.hybrid_search(
            db,
            user_id=user_id,
            question=state.question,
            filters=state.retrieval_filters,
            top_k=max(req.top_k * 2, 12),
            llm_config=llm_config,
        )
        state.candidates = candidates
        state.trace["retrieval"] = {
            "candidate_count": len(candidates),
            "top_chunk_ids": [c.chunk_id for c in candidates[:10]],
        }

    def _validate(self, state: AgentState) -> None:
        validated = state.candidates[:10]
        unique_docs = len({c.document_id for c in validated})
        sufficiency = len(validated) >= 3 and unique_docs >= 2

        state.validated = validated
        state.trace["validation"] = {
            "sufficient_evidence": sufficiency,
            "validated_count": len(validated),
            "unique_documents": unique_docs,
        }

    def _synthesize(
        self,
        state: AgentState,
        *,
        db: Session,
        user_id: str,
        llm_config: RuntimeLLMConfig | None,
        trace_id: str | None,
    ) -> None:
        state.answer_payload = self.rag.answer_question(
            state.question,
            state.validated,
            llm_config=llm_config,
            run_ctx=LLMRunContext(db=db, user_id=user_id, trace_id=trace_id, endpoint="query_synthesis"),
        )
        state.trace["synthesis"] = {
            "citation_ids": state.answer_payload.get("citation_ids", []),
            "confidence": state.answer_payload.get("confidence", 0.0),
        }
