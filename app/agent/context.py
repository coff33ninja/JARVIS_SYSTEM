"""Agent context builder.

Composes the two recall outputs into prompt-ready context for the LLM:
recent conversation history (episodes) plus the top long-term memories
relevant to the current query. Keyword-only by default; semantic memories
appear automatically once the embedder is available and rows are indexed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .recall.retriever import Recaller, ScoredHit
from .recall.store import MemoryStore


@dataclass
class AgentContext:
    """Everything the LLM should see for one turn."""

    query: str
    history: list[dict] = field(default_factory=list)
    memories: list[ScoredHit] = field(default_factory=list)
    session_id: str | None = None

    def to_prompt(self) -> str:
        blocks = [f"## Current request\n{self.query}"]
        if self.history:
            lines = [f"- {ep['role']}: {ep['content']}" for ep in self.history]
            blocks.append("## Recent conversation\n" + "\n".join(lines))
        if self.memories:
            lines = [
                f"- [{m.source}] {m.content} (score {m.score:.2f})" for m in self.memories
            ]
            blocks.append("## Relevant long-term memories\n" + "\n".join(lines))
        return "\n\n".join(blocks)


def build_context(
    store: MemoryStore,
    recaller: Recaller,
    query: str,
    session_id: str | None = None,
    history_limit: int = 10,
    memory_limit: int = 5,
) -> AgentContext:
    """Gather recent history and relevant memories for ``query``."""
    return AgentContext(
        query=query,
        session_id=session_id,
        history=recaller.recall_history(session_id=session_id, limit=history_limit),
        memories=recaller.remember(query, limit=memory_limit),
    )
