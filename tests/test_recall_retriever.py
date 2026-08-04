"""Tests for hybrid recall: keyword, semantic, and graceful degradation."""

from __future__ import annotations

from app.agent.recall.config import RecallConfig
from app.agent.recall.retriever import Recaller
from app.agent.recall.store import Fact, MemoryStore


class FlakyEmbedder:
    """Embedder whose endpoint dies after ``fail_after`` embeds."""

    def __init__(self, embedder, fail_after: int = 0):
        self._inner = embedder
        self.config = embedder.config
        self._calls = 0
        self.fail_after = fail_after

    @property
    def available(self) -> bool:
        return True

    def embed(self, texts):
        if self.fail_after and self._calls >= self.fail_after:
            raise RuntimeError("endpoint down")
        self._calls += 1
        return self._inner.embed(texts)


def test_keyword_only_when_no_embedder(store, fake_embedder):
    store.add_fact(Fact("User prefers the terminal", tags=("preference",)))
    store.add_fact(Fact("Default output directory is D:/outputs"))
    recaller = Recaller(store, embedder=None)
    hits = recaller.remember("terminal")
    assert len(hits) == 1
    assert hits[0].source == "keyword"
    assert "terminal" in hits[0].content


def test_semantic_only_when_no_keyword_hit(store, fake_embedder):
    store.add_fact(Fact("The hand wave starts a gesture", tags=("vocab",)))
    recaller = Recaller(store, embedder=fake_embedder)
    hits = recaller.remember("hand gesture")
    assert hits
    assert hits[0].source == "semantic"
    assert "gesture" in hits[0].content


def test_hybrid_ranks_relevant_higher(store, fake_embedder):
    store.add_fact(Fact("Jarvis recognises a voice command", tags=("voice",)))
    store.add_fact(Fact("The reticle follows the cursor"))
    recaller = Recaller(store, embedder=fake_embedder)
    hits = recaller.remember("voice command jarvis")
    assert hits
    assert "voice command" in hits[0].content
    assert hits[0].source == "hybrid"


def test_degrades_to_keyword_when_embedder_dies(store, fake_embedder):
    store.add_fact(Fact("Transfer a file with a throw gesture", tags=("file",)))
    recaller = Recaller(store, embedder=FlakyEmbedder(fake_embedder, fail_after=1))
    # query embedding fails; keyword recall must still return the fact
    hits = recaller.remember("throw file")
    assert hits
    assert "throw gesture" in hits[0].content
    assert hits[0].source == "keyword"


def test_remember_uses_top_k_and_floor(store, fake_embedder):
    cfg = RecallConfig(top_k=1, min_score=0.0)
    store.add_fact(Fact("alpha fact about gesture"))
    store.add_fact(Fact("beta fact about gesture"))
    recaller = Recaller(store, embedder=fake_embedder, config=cfg)
    hits = recaller.remember("gesture")
    assert len(hits) == 1


def test_recall_history_is_chronological(store):
    store.add_fact(Fact("unrelated"))
    for role, content in (("user", "first"), ("assistant", "second")):
        store.add_fact(Fact(f"{role} {content}"))
    recaller = Recaller(store)
    history = recaller.recall_history(limit=5)
    assert history  # episodes only; facts are excluded


def test_index_backfills_embeddings(store, fake_embedder):
    store.add_fact(Fact("jarvis file transfer"))
    store.add_fact(Fact("voice control enabled"))
    recaller = Recaller(store, embedder=fake_embedder)
    embedded = recaller.index()
    assert embedded == 2
    assert len(store.iter_embeddings("fake-embed")) == 2
    assert recaller.index() == 0  # idempotent


def test_index_noop_without_embedder(store):
    recaller = Recaller(store, embedder=None)
    assert recaller.index() == 0
