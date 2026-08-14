"""Recall memory configuration.

Local-first by default (ADR-005): the store is a plain SQLite file. The
semantic embedder talks to a local OpenAI-compatible endpoint (ADR-003,
default Ollama on ``localhost:11434``) and is strictly optional.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_DB_PATH = "jarvis_memory.db"
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_EMBED_DIM = 768


@dataclass
class EmbedderConfig:
    """Semantic embedding settings. Disable via ``enabled=False``."""

    enabled: bool = True
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_EMBED_MODEL
    dimension: int = DEFAULT_EMBED_DIM
    api_key: str = "ollama"  # Ollama ignores it; kept for OpenAI-compat clients
    timeout_s: float = 5.0


@dataclass
class RecallConfig:
    """Top-level configuration for the recall memory subsystem."""

    db_path: str = DEFAULT_DB_PATH
    embedder: EmbedderConfig = field(default_factory=EmbedderConfig)
    top_k: int = 8
    keyword_weight: float = 0.4
    semantic_weight: float = 0.6
    min_score: float = 0.0

    @classmethod
    def from_env(cls) -> RecallConfig:
        """Build config from ``JARVIS_*`` env vars, falling back to defaults."""
        cfg = cls()
        cfg.db_path = os.getenv("JARVIS_MEMORY_DB", cfg.db_path)
        cfg.embedder.enabled = os.getenv("JARVIS_RECALL_EMBED", "1") == "1"
        cfg.embedder.base_url = os.getenv("OLLAMA_BASE_URL", cfg.embedder.base_url)
        cfg.embedder.model = os.getenv("JARVIS_EMBED_MODEL", cfg.embedder.model)
        return cfg
