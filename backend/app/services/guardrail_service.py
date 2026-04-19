from __future__ import annotations

import re


class GuardrailService:
    INJECTION_PATTERNS = [
        r"ignore\s+previous\s+instructions",
        r"reveal\s+system\s+prompt",
        r"bypass\s+guardrails",
        r"act\s+as\s+developer",
        r"jailbreak",
    ]

    def validate_question(self, question: str) -> tuple[bool, str | None]:
        text = question.strip()
        if len(text) < 3:
            return False, "Question is too short."
        if len(text) > 2500:
            return False, "Question is too long. Keep it under 2500 characters."

        lower = text.lower()
        for pat in self.INJECTION_PATTERNS:
            if re.search(pat, lower):
                return False, "Question appears to contain prompt-injection text."
        return True, None

    def validate_grounded_output(self, answer: str, citation_ids: list[str]) -> tuple[bool, str | None]:
        if not answer.strip():
            return False, "Empty answer generated."
        if len(answer) > 6000:
            return False, "Answer too long; possible ungrounded output."
        if not citation_ids:
            return False, "Missing citations for grounded response."
        return True, None

    def safe_fallback_answer(self) -> str:
        return (
            "I can help with that, but I do not yet have enough reliable indexed evidence to answer confidently. "
            "Try ingesting more relevant sources or narrowing the question."
        )
