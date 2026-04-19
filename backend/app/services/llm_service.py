from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from litellm import completion

from app.core.config import get_settings
from app.services.llm_config_service import RuntimeLLMConfig
from app.services.llmops_service import LLMOpsService


@dataclass
class LLMRunContext:
    db: Any | None = None
    user_id: str | None = None
    trace_id: str | None = None
    endpoint: str | None = None


class LLMService:
    def __init__(self, llmops: LLMOpsService) -> None:
        self.settings = get_settings()
        self.llmops = llmops

    def _default_config(self) -> RuntimeLLMConfig | None:
        if not self.settings.gemini_api_key:
            return None
        return RuntimeLLMConfig(
            provider="gemini",
            model_name=self.settings.gemini_chat_model,
            api_key=self.settings.gemini_api_key,
        )

    @staticmethod
    def _resolve_model(provider: str, model_name: str) -> str:
        if "/" in model_name:
            return model_name
        return f"{provider}/{model_name}"

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        llm_config: RuntimeLLMConfig | None = None,
        run_ctx: LLMRunContext | None = None,
    ) -> str:
        config = llm_config or self._default_config()
        if not config:
            return "No LLM key configured. Add a key in Settings."

        model = self._resolve_model(config.provider, config.model_name)
        started = time.perf_counter()
        prompt_chars = len(system_prompt) + len(user_prompt)

        try:
            response = completion(
                model=model,
                api_key=config.api_key,
                base_url=config.base_url,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            text = response["choices"][0]["message"]["content"] or ""
            latency_ms = int((time.perf_counter() - started) * 1000)
            self.llmops.log_llm_run(
                db=run_ctx.db if run_ctx else None,
                user_id=run_ctx.user_id if run_ctx else None,
                trace_id=run_ctx.trace_id if run_ctx else None,
                endpoint=run_ctx.endpoint if run_ctx else None,
                provider=config.provider,
                model_name=config.model_name,
                prompt_chars=prompt_chars,
                response_chars=len(text),
                latency_ms=latency_ms,
                success=True,
                error=None,
            )
            return text.strip()
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            self.llmops.log_llm_run(
                db=run_ctx.db if run_ctx else None,
                user_id=run_ctx.user_id if run_ctx else None,
                trace_id=run_ctx.trace_id if run_ctx else None,
                endpoint=run_ctx.endpoint if run_ctx else None,
                provider=config.provider,
                model_name=config.model_name,
                prompt_chars=prompt_chars,
                response_chars=0,
                latency_ms=latency_ms,
                success=False,
                error=str(exc),
            )
            raise

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        fallback: dict[str, Any] | list[Any] | None = None,
        llm_config: RuntimeLLMConfig | None = None,
        run_ctx: LLMRunContext | None = None,
    ) -> dict[str, Any] | list[Any]:
        if fallback is None:
            fallback = {}

        json_prompt = (
            system_prompt
            + "\n\nReturn ONLY valid JSON. No markdown, no prose outside JSON."
        )

        try:
            output = self.generate_text(
                json_prompt,
                user_prompt,
                temperature=0.1,
                llm_config=llm_config,
                run_ctx=run_ctx,
            )
        except Exception:
            return fallback

        return self._parse_json(output) or fallback

    @staticmethod
    def _parse_json(text: str | None) -> dict[str, Any] | list[Any] | None:
        if not text:
            return None

        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", stripped)
        if not match:
            return None

        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None
