"""The JARVIS agent loop.

Turns a user request into an action. Each turn:

1. Pulls recent conversation history for the session from the memory store.
2. Recalls long-term memories relevant to the request (keyword/hybrid).
3. Calls the LLM with those as context plus the current environment.
4. Executes any requested tools (bounded by ``max_tool_iterations``).
5. Records the user turn and the final answer as episodes.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field

from .context import focused_window_title
from .llm import LLMClient
from .recall.retriever import Recaller, ScoredHit
from .recall.store import Episode, MemoryStore
from .tools import ToolRegistry
from .tools.tools import default_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Jarvis, a local-first personal assistant controlling this computer. "
    "Be concise. Use a tool when it helps; otherwise answer directly. "
    "You can remember long-term facts with the remember tool and recall them "
    "with the recall tool."
)


@dataclass
class AgentConfig:
    max_tool_iterations: int = 5
    history_limit: int = 10
    memory_limit: int = 5


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        store: MemoryStore,
        recaller: Recaller | None = None,
        registry: ToolRegistry | None = None,
        session_id: str | None = None,
        config: AgentConfig | None = None,
    ):
        self.llm = llm
        self.store = store
        self.recaller = recaller or Recaller(store)
        self.registry = registry or default_tools(store, self.recaller)
        self.session_id = session_id
        self.config = config or AgentConfig()
        self._tools_supported = True
        self._model_checked = False

    def handle_turn(self, text: str, session_id: str | None = None) -> str:
        """Process one user turn and return the assistant's final text."""
        self._ensure_model_once()
        sid = session_id or self.session_id
        if sid is None:
            sid = uuid.uuid4().hex
            self.session_id = sid

        history = self.recaller.recall_history(session_id=sid, limit=self.config.history_limit)
        memories = self.recaller.remember(text, limit=self.config.memory_limit)

        messages: list[dict] = [
            self._system_message(memories),
            *self._history_messages(history),
            {"role": "user", "content": text},
        ]
        self.store.add_episode(Episode("user", text, sid))

        final = ""
        schemas = self.registry.schemas()
        for _ in range(self.config.max_tool_iterations):
            response = self._chat(messages, schemas)
            messages.append(self._as_message(response))
            if not response["tool_calls"]:
                final = response["content"]
                break
            if not self._tools_supported:
                # model refused tools mid-loop; treat the reply as final
                final = response["content"]
                break
            for call in response["tool_calls"]:
                result = self.registry.execute(call["name"], call["arguments"])
                logger.info("tool %s -> %s", call["name"], result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })
        else:
            final = f"(no final answer within {self.config.max_tool_iterations} tool iterations)"

        self.store.add_episode(Episode("assistant", final, sid))
        return final

    def transcript(self, session_id: str | None = None, limit: int = 20) -> list[dict]:
        """Recent user/assistant episodes for HUD chat bubbles / transcript."""
        episodes = self.recaller.recall_history(
            session_id=session_id or self.session_id, limit=limit * 2
        )
        turns = [ep for ep in episodes if ep["role"] in ("user", "assistant")]
        return turns[-limit:]

    def _chat(self, messages: list[dict], schemas: list[dict]) -> dict:
        """Call the LLM, downgrading to tool-less chat if the model rejects tools.

        Some Ollama models (e.g. ``smallthinker``) return HTTP 400 for tool
        requests (ADR-003 per-model quirk). We retry once without tools so the
        agent keeps working, just without tool access.
        """
        try:
            return self.llm.chat(messages, tools=schemas if self._tools_supported else None)
        except Exception as exc:
            if self._tools_supported and "tool" in str(exc).lower():
                logger.warning("model does not support tools (%s); retrying without tools", exc)
                self._tools_supported = False
                return self.llm.chat(messages)
            raise

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _ensure_model_once(self) -> None:
        """Auto-install the LLM model on first use (first-run convenience)."""
        if self._model_checked:
            return
        self._model_checked = True
        ensure = getattr(self.llm, "ensure_model", None)
        if ensure is None:
            return
        try:
            ensure()
        except Exception as exc:
            logger.warning("ensure_model failed: %s", exc)

    def _system_message(self, memories: list[ScoredHit]) -> dict:
        parts = [SYSTEM_PROMPT, f"## Current environment\nFocused window: {focused_window_title()}"]
        if memories:
            lines = [f"- [{m.source}] {m.content}" for m in memories]
            parts.append("## Known long-term memories\n" + "\n".join(lines))
        return {"role": "system", "content": "\n\n".join(parts)}

    @staticmethod
    def _history_messages(history: list[dict]) -> list[dict]:
        return [
            {"role": ep["role"], "content": ep["content"]}
            for ep in history
            if ep["role"] in ("user", "assistant")
        ]

    @staticmethod
    def _as_message(response: dict) -> dict:
        message: dict = {"role": response["role"], "content": response["content"] or None}
        if response["tool_calls"]:
            message["tool_calls"] = [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"]),
                    },
                }
                for call in response["tool_calls"]
            ]
        return message
