"""Shared test fixtures for the recall memory subsystem."""

from __future__ import annotations

import numpy as np
import pytest

from app.agent.recall.config import EmbedderConfig
from app.agent.recall.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    with MemoryStore(tmp_path / "test_memory.db") as ms:
        yield ms


CONCEPT_SYNONYMS = {
    "file": ("file", "transfer", "throw", "catch", "send", "tablet"),
    "gesture": ("gesture", "hand", "wave", "flick", "cursor"),
    "voice": ("voice", "speak", "speech", "audio", "command"),
    "jarvis": ("jarvis", "assistant", "agent"),
}


class FakeEmbedder:
    """Duck-typed embedder: concept bag-of-words vectors, no network.

    Synonyms decouple semantic similarity from literal keyword overlap so
    tests can exercise semantic-only and hybrid paths.
    """

    def __init__(self):
        self.config = EmbedderConfig(enabled=True, model="fake-embed")
        self.vocab = tuple(CONCEPT_SYNONYMS)

    @property
    def available(self) -> bool:
        return True

    def embed(self, texts):
        single = isinstance(texts, str)
        inputs = [texts] if single else list(texts)
        out = [self._vector(t) for t in inputs]
        return out[0] if single else out

    def _vector(self, text: str) -> list[float]:
        text = text.lower()
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        for i, concept in enumerate(self.vocab):
            if any(syn in text for syn in CONCEPT_SYNONYMS[concept]):
                vec[i] = 1.0
        return vec.tolist()


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()
