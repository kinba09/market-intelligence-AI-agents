from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.workflow import MarketIntelAgentWorkflow
from app.core.container import get_services
from app.core.database import get_db
from app.schemas.api import AskRequest, AskResponse, Citation


router = APIRouter(prefix="/query", tags=["query"])


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    services = get_services()
    workflow = MarketIntelAgentWorkflow(services.llm, services.retrieval, services.rag)
    state = workflow.run(db, req)

    citation_ids = state.answer_payload.get("citation_ids", [])
    context_map = {c.chunk_id: c for c in state.validated}

    citations = []
    for cid in citation_ids:
        chunk = context_map.get(cid)
        if not chunk:
            continue
        citations.append(
            Citation(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source_url=chunk.source_url,
                title=chunk.title,
                published_at=chunk.published_at,
            )
        )

    return AskResponse(
        answer=state.answer_payload.get("answer", "No answer generated."),
        confidence=float(state.answer_payload.get("confidence", 0.0)),
        citations=citations,
        trace=state.trace,
    )
