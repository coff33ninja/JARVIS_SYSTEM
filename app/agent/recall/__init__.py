"""Recall memory — Jarvis's long-term memory subsystem.

Public API:

* :class:`MemoryStore` — SQLite + FTS5 persistence for facts and episodes.
* :class:`Recaller` — hybrid (keyword + semantic) query-time retrieval.
* :class:`Embedder` — optional Ollama embeddings client for semantic recall.
* :class:`Fact`, :class:`Episode` — input records.
* :class:`RecallConfig`, :class:`EmbedderConfig` — configuration.

Usage::

    from app.agent.recall import MemoryStore, Recaller, Fact

    with MemoryStore("jarvis_memory.db") as store:
        store.add_fact(Fact("User prefers the terminal to the file manager", tags=("preference",)))
        hit = Recaller(store).remember("what does the user prefer?")
"""

from .config import EmbedderConfig, RecallConfig
from .embedder import Embedder
from .retriever import Recaller, ScoredHit
from .store import Episode, Fact, MemoryStore

__all__ = [
    "Embedder",
    "EmbedderConfig",
    "Episode",
    "Fact",
    "MemoryStore",
    "Recaller",
    "RecallConfig",
    "ScoredHit",
]
