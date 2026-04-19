from __future__ import annotations

import hashlib
from typing import Literal

import numpy as np

from app.core.config import get_settings

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover - optional runtime dependency behavior
    genai = None


class EmbeddingService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.vector_size = self.settings.vector_size
        self._gemini_enabled = bool(self.settings.gemini_api_key and genai is not None)
        if self._gemini_enabled:
            genai.configure(api_key=self.settings.gemini_api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_many(texts, task_type="retrieval_document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed_many([text], task_type="retrieval_query")[0]

    def _embed_many(
        self,
        texts: list[str],
        *,
        task_type: Literal["retrieval_document", "retrieval_query"] = "retrieval_document",
    ) -> list[list[float]]:
        if self._gemini_enabled:
            vectors: list[list[float]] = []
            for text in texts:
                clipped = text[:11000]
                try:
                    resp = genai.embed_content(
                        model=self.settings.gemini_embedding_model,
                        content=clipped,
                        task_type=task_type,
                    )
                    vec = resp["embedding"] if isinstance(resp, dict) else getattr(resp, "embedding", None)
                    if vec:
                        vectors.append([float(x) for x in vec])
                except Exception:
                    vectors = []
                    break
            if vectors:
                self.vector_size = len(vectors[0])
                return vectors

        # deterministic local fallback to keep the system operational
        return [self._hash_embedding(t) for t in texts]

    def _hash_embedding(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        seed = int(digest[:16], 16)
        rng = np.random.default_rng(seed)
        vec = rng.normal(size=self.vector_size)
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec.tolist()
        return (vec / norm).astype(float).tolist()
