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
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:11434/v1"
    model: str = "llama3.2"
    api_key: str = "ollama"
    temperature: float = 0.2
    timeout_s: float = 30.0
    auto_pull: bool = True
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        cfg = cls()
        cfg.base_url = os.getenv("JARVIS_LLM_BASE_URL", cfg.base_url)
        cfg.model = os.getenv("JARVIS_LLM_MODEL", cfg.model)
        pull = os.getenv("JARVIS_LLM_AUTO_PULL", "1")
        cfg.auto_pull = pull.strip().lower() not in ("0", "false", "no", "off")
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

    # ------------------------------------------------------------------ #
    # first-run model auto-install
    # ------------------------------------------------------------------ #

    def installed_models(self) -> list[str]:
        """IDs of models currently installed on the endpoint."""
        client = self._build_client()
        if client is None:
            return []
        try:
            rows = client.models.list()
            data = rows.data if hasattr(rows, "data") else rows
            return [getattr(m, "id", str(m)) for m in data]
        except Exception as exc:
            logger.warning("could not list models: %s", exc)
            return []

    def ensure_model(self) -> bool:
        """Make sure the configured model is installed. Returns True if usable.

        On first run, if the model is missing and the endpoint is Ollama,
        auto-pulls it (so setup is "install the app and go"). Non-Ollama
        endpoints (LM Studio / cloud) can't be pulled to; we log a hint and
        return False. Safe to call every turn — it's a cheap no-op once the
        model exists.
        """
        if not self.available:
            return False
        want = self.config.model.split(":")[0]
        installed = {m.split(":")[0] for m in self.installed_models()}
        if want in installed:
            return True
        if not self.config.auto_pull:
            logger.info("model '%s' not installed and auto-pull is disabled "
                        "(JARVIS_LLM_AUTO_PULL=0)", self.config.model)
            return False
        if self._ollama_pull(self.config.model):
            return True
        logger.info("could not auto-install '%s'; run `ollama pull %s`",
                    self.config.model, self.config.model)
        return False

    def _ollama_base(self) -> str:
        base = self.config.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        return base.rstrip("/")

    def _ollama_pull(self, name: str) -> bool:
        """Pull a model via the native Ollama API. False when not Ollama."""
        base = self._ollama_base()
        try:
            with urllib.request.urlopen(f"{base}/api/tags", timeout=5) as resp:
                json.loads(resp.read().decode())
        except Exception as exc:
            logger.info("endpoint is not Ollama (%s); skipping auto-pull", exc)
            return False
        req = urllib.request.Request(
            f"{base}/api/pull",
            data=json.dumps({"name": name, "stream": False}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3600) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as exc:
            logger.warning("ollama pull failed: %s", exc)
            return False
        return payload.get("status") == "success"

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
