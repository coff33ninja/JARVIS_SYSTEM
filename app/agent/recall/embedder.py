"""Optional semantic embedder backed by a local OpenAI-compatible endpoint.

Defaults to Ollama's ``/v1`` embeddings API (ADR-003) with zero new
dependencies — the project already ships the ``openai`` client. The
embedder is strictly optional: the hybrid retriever degrades to keyword
recall when it is unreachable or disabled.
"""

from __future__ import annotations

import logging

from .config import EmbedderConfig

logger = logging.getLogger(__name__)


class Embedder:
    """Lazy, cached client for dense text embeddings."""

    def __init__(self, config: EmbedderConfig | None = None):
        self.config = config or EmbedderConfig()
        self._client = None
        self._pinged = False
        self._ping_ok = False

    def _build_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError:
            logger.warning("openai not installed; semantic recall disabled")
            return None
        try:
            self._client = OpenAI(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                timeout=self.config.timeout_s,
            )
        except Exception as exc:  # pragma: no cover - config error path
            logger.warning("failed to build embedder client: %s", exc)
            return None
        return self._client

    @property
    def available(self) -> bool:
        """True if the endpoint responds. The probe result is cached."""
        if self._pinged:
            return self._ping_ok
        self._pinged = True
        client = self._build_client()
        if client is None:
            return False
        try:
            client.models.list()
            self._ping_ok = True
        except Exception as exc:
            logger.warning("embedding endpoint unreachable (%s): %s",
                           self.config.base_url, exc)
        return self._ping_ok

    def embed(self, texts: str | list[str]) -> list[list[float]]:
        """Embed one text or a batch. Returns row-aligned vectors."""
        single = isinstance(texts, str)
        inputs = [texts] if single else list(texts)
        client = self._build_client()
        if client is None:
            raise RuntimeError("embedder unavailable (client could not be built)")
        resp = client.embeddings.create(model=self.config.model, input=inputs)
        ordered = sorted(resp.data, key=lambda item: item.index)
        vectors = [list(item.embedding) for item in ordered]
        return vectors[0] if single else vectors
