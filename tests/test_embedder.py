"""Tests for the optional Ollama-backed embedder (no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent.recall.config import EmbedderConfig
from app.agent.recall.embedder import Embedder


class FakeEmbeddings:
    def __init__(self, vectors):
        self._vectors = vectors

    def create(self, model, input):
        rows = [input] if isinstance(input, str) else list(input)
        data = [
            SimpleNamespace(index=i, embedding=self._vectors[i % len(self._vectors)])
            for i in range(len(rows))
        ]
        return SimpleNamespace(data=data)


class FakeOpenAIClient:
    def __init__(self, vectors, models_ok=True):
        self.embeddings = FakeEmbeddings(vectors)
        self.models_ok = models_ok

    def models(self):
        if not self.models_ok:
            raise RuntimeError("connection refused")
        return SimpleNamespace(list=lambda: [SimpleNamespace(id="fake")])


@pytest.fixture
def embedder(monkeypatch):
    cfg = EmbedderConfig(base_url="http://localhost:9/v1", model="fake")
    emb = Embedder(cfg)
    emb._build_client = lambda: FakeOpenAIClient([[0.1, 0.2], [0.3, 0.4]])
    return emb


def test_available_true_when_endpoint_responds(embedder):
    assert embedder.available is True
    assert embedder.available is True  # cached, no second probe


def test_embed_single_and_batch(embedder):
    single = embedder.embed("hello")
    assert single == [0.1, 0.2]
    batch = embedder.embed(["a", "b"])
    assert batch == [[0.1, 0.2], [0.3, 0.4]]


def test_available_false_when_endpoint_down(monkeypatch):
    cfg = EmbedderConfig(enabled=True)
    emb = Embedder(cfg)
    emb._build_client = lambda: FakeOpenAIClient([[1.0]], models_ok=False)
    assert emb.available is False


def test_unavailable_client_raises_on_embed(monkeypatch):
    cfg = EmbedderConfig(enabled=True)
    emb = Embedder(cfg)
    emb._build_client = lambda: None
    assert emb.available is False
    with pytest.raises(RuntimeError):
        emb.embed("x")
