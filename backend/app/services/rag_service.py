from __future__ import annotations

from typing import Any

from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievedChunk


class RAGService:
    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    def answer_question(self, question: str, contexts: list[RetrievedChunk]) -> dict[str, Any]:
        if not contexts:
            return {
                "answer": "I could not find enough indexed evidence to answer this question yet.",
                "confidence": 0.0,
                "citation_ids": [],
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
            "You are a market intelligence analyst speaking directly to the user in a natural, conversational tone. "
            "Use only the provided evidence. Keep the answer concise and helpful. "
            "If useful, include short sections like 'What I found' and 'Why it matters'. "
            "Do not invent facts. If evidence is weak, say that clearly and suggest the next best question. "
            "Return JSON with keys: answer, confidence, citation_ids, key_points."
        )
        user_prompt = f"Question: {question}\n\nEvidence:\n" + "\n\n".join(evidence)

        fallback = {
            "answer": self._fallback_answer(question, contexts),
            "confidence": 0.45,
            "citation_ids": [c.chunk_id for c in contexts[:3]],
            "key_points": [],
        }
        payload = self.llm.generate_json(system_prompt, user_prompt, fallback=fallback)

        citation_ids = payload.get("citation_ids") or []
        if not citation_ids:
            citation_ids = [c.chunk_id for c in contexts[:3]]

        return {
            "answer": str(payload.get("answer", fallback["answer"])),
            "confidence": float(payload.get("confidence", 0.45)),
            "citation_ids": citation_ids,
            "key_points": payload.get("key_points", []),
        }

    @staticmethod
    def _fallback_answer(question: str, contexts: list[RetrievedChunk]) -> str:
        top = contexts[0]
        return (
            f"Here’s what I can confirm right now: I found one strong signal related to '{question}' "
            f"from {top.source_url}. I can dig deeper if you want a fuller cross-source comparison."
        )
