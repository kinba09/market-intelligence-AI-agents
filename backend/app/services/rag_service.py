from __future__ import annotations

from typing import Any

from app.services.guardrail_service import GuardrailService
from app.services.llm_config_service import RuntimeLLMConfig
from app.services.llm_service import LLMRunContext, LLMService
from app.services.retrieval_service import RetrievedChunk


class RAGService:
    def __init__(self, llm: LLMService, guardrails: GuardrailService) -> None:
        self.llm = llm
        self.guardrails = guardrails

    def answer_question(
        self,
        question: str,
        contexts: list[RetrievedChunk],
        *,
        llm_config: RuntimeLLMConfig | None = None,
        run_ctx: LLMRunContext | None = None,
    ) -> dict[str, Any]:
        valid, error = self.guardrails.validate_question(question)
        if not valid:
            return {
                "answer": error,
                "confidence": 0.0,
                "citation_ids": [],
                "key_points": [],
            }

        if not contexts:
            return {
                "answer": self.guardrails.safe_fallback_answer(),
                "confidence": 0.0,
                "citation_ids": [],
                "key_points": [],
            }

        evidence = []
        for c in contexts:
            evidence.append(
                (
                    f"[CID:{c.chunk_id}] title={c.title or 'Untitled'} "
                    f"url={c.source_url} published_at={c.published_at}\n{c.text[:1200]}"
                )
            )

        system_prompt = (
            "You are a market intelligence analyst speaking naturally to the user. "
            "Use only evidence chunks provided. Do not use outside knowledge. "
            "Answer in a conversational style with max 5 short paragraphs. "
            "If evidence is conflicting or weak, explicitly say uncertainty. "
            "Return JSON with keys: answer, confidence, citation_ids, key_points."
        )
        user_prompt = f"Question: {question}\n\nEvidence:\n" + "\n\n".join(evidence)

        fallback = {
            "answer": self._fallback_answer(question, contexts),
            "confidence": 0.45,
            "citation_ids": [c.chunk_id for c in contexts[:3]],
            "key_points": [],
        }
        payload = self.llm.generate_json(
            system_prompt,
            user_prompt,
            fallback=fallback,
            llm_config=llm_config,
            run_ctx=run_ctx,
        )

        citation_ids = payload.get("citation_ids") or [c.chunk_id for c in contexts[:3]]
        answer_text = str(payload.get("answer", fallback["answer"])).strip()
        confidence = self._coerce_confidence(payload.get("confidence", 0.45))

        grounded_ok, grounded_error = self.guardrails.validate_grounded_output(answer_text, citation_ids)
        if not grounded_ok:
            return {
                "answer": self.guardrails.safe_fallback_answer(),
                "confidence": min(confidence, 0.35),
                "citation_ids": [c.chunk_id for c in contexts[:2]],
                "key_points": [grounded_error],
            }

        return {
            "answer": answer_text,
            "confidence": max(0.0, min(1.0, confidence)),
            "citation_ids": citation_ids,
            "key_points": payload.get("key_points", []),
        }

    @staticmethod
    def _coerce_confidence(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            v = value.strip().lower()
            mapping = {
                "low": 0.3,
                "medium": 0.6,
                "high": 0.85,
            }
            if v in mapping:
                return mapping[v]
            try:
                return float(v)
            except ValueError:
                return 0.45
        return 0.45

    @staticmethod
    def _fallback_answer(question: str, contexts: list[RetrievedChunk]) -> str:
        top = contexts[0]
        return (
            f"Here’s what I can confirm now: I found a strong signal related to '{question}' from {top.source_url}. "
            "If you want, I can compare this against other recent sources for higher confidence."
        )
