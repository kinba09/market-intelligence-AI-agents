from __future__ import annotations

import json
import re
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None


class LLMService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._enabled = bool(self.settings.gemini_api_key and genai is not None)
        self._model = None
        if self._enabled:
            genai.configure(api_key=self.settings.gemini_api_key)
            self._model = genai.GenerativeModel(self.settings.gemini_chat_model)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        if not self._enabled or self._model is None:
            return "Gemini API key missing. Configure GEMINI_API_KEY in .env."

        prompt = f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nUSER INPUT:\n{user_prompt}"
        response = self._model.generate_content(
            prompt,
            generation_config={"temperature": temperature},
        )
        return (response.text or "").strip()

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback: dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        if fallback is None:
            fallback = {}

        if not self._enabled or self._model is None:
            return fallback

        prompt = f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nUSER INPUT:\n{user_prompt}"
        try:
            response = self._model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                },
            )
            return self._parse_json(response.text) or fallback
        except Exception:
            return fallback

    @staticmethod
    def _parse_json(text: str | None) -> dict[str, Any] | list[Any] | None:
        if not text:
            return None
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # recover JSON from fenced or mixed output
        match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", stripped)
        if not match:
            return None
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None
