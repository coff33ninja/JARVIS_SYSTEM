"""OpenAI-compatible LLM client (Ollama / LM Studio / cloud).

All agent code talks to the model through this client (ADR-003) so swapping
backends is a config change, not a code change. Responses are normalised to
plain dicts:

* no tool calls:  ``{"role", "content", "tool_calls": []}``
* tool calls:     ``{"role", "content", "tool_calls": [{"id", "name", "arguments"}]}``
  where ``arguments`` is a parsed JSON dict.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:11434/v1"
    model: str = "llama3.2"
    api_key: str = "ollama"
    temperature: float = 0.2
    timeout_s: float = 30.0
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        cfg = cls()
        cfg.base_url = os.getenv("JARVIS_LLM_BASE_URL", cfg.base_url)
        cfg.model = os.getenv("JARVIS_LLM_MODEL", cfg.model)
        return cfg


class LLMClient:
    """Lazy, cached OpenAI-compatible chat client."""

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self._client = None
        self._pinged = False
        self._ping_ok = False

    def _build_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError:
            logger.warning("openai not installed; LLM unavailable")
            return None
        try:
            self._client = OpenAI(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                timeout=self.config.timeout_s,
            )
        except Exception as exc:  # pragma: no cover - config error path
            logger.warning("failed to build LLM client: %s", exc)
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
            logger.warning("LLM endpoint unreachable (%s): %s",
                           self.config.base_url, exc)
        return self._ping_ok

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Run one chat completion. Returns the normalised assistant message."""
        client = self._build_client()
        if client is None:
            raise RuntimeError("LLM unavailable (client could not be built)")
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "timeout": self.config.timeout_s,
        }
        if tools:
            kwargs["tools"] = tools
        kwargs.update(self.config.extra)
        resp = client.chat.completions.create(**kwargs)
        return self._normalise(resp)

    @staticmethod
    def _normalise(resp) -> dict:
        msg = resp.choices[0].message
        out = {"role": msg.role, "content": msg.content or "", "tool_calls": []}
        for tc in msg.tool_calls or []:
            try:
                arguments = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                arguments = {}
            out["tool_calls"].append(
                {"id": tc.id, "name": tc.function.name, "arguments": arguments}
            )
        return out
