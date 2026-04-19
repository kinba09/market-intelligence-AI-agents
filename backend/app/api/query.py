from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.workflow import MarketIntelAgentWorkflow
from app.core.auth import get_current_user
from app.core.container import get_services
from app.core.database import get_db
from app.models.entities import User
from app.schemas.api import AskRequest, AskResponse, Citation


router = APIRouter(prefix="/query", tags=["query"])


@router.post("/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AskResponse:
    services = get_services()
    workflow = MarketIntelAgentWorkflow(services.llm, services.retrieval, services.rag)
    llm_cfg = services.llm_config.get_default_runtime_config(db, current_user.id)
    trace_id = f"qry_{uuid4().hex[:12]}"

    state = workflow.run(
        db,
        req,
        user_id=current_user.id,
        llm_config=llm_cfg,
        trace_id=trace_id,
    )

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

    db.commit()

    return AskResponse(
        answer=state.answer_payload.get("answer", "No answer generated."),
        confidence=float(state.answer_payload.get("confidence", 0.0)),
        citations=citations,
        trace=state.trace,
        trace_id=trace_id,
    )
