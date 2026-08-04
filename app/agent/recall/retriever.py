"""Hybrid recall: fuse FTS5 keyword hits with semantic hits.

Ranks are min-max normalised per source, then combined with configurable
weights (keyword + semantic). If the embedder is missing, disabled, or
unreachable, recall silently degrades to keyword-only (graceful
degradation is a core project principle).
"""

from __future__ import annotations

import logging
from typing import NamedTuple

import numpy as np

from .config import RecallConfig
from .store import MemoryStore

logger = logging.getLogger(__name__)


class ScoredHit(NamedTuple):
    table: str
    row_id: int
    content: str
    score: float
    source: str  # 'keyword' | 'semantic' | 'hybrid'
    extra: dict


def _decode_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


class Recaller:
    """Query-time hybrid retrieval against a :class:`MemoryStore`."""

    def __init__(self, store: MemoryStore, embedder=None, config: RecallConfig | None = None):
        self.store = store
        self.embedder = embedder
        self.config = config or RecallConfig()

    def remember(
        self, query: str, limit: int | None = None, min_score: float | None = None
    ) -> list[ScoredHit]:
        """Return the best matching memories for ``query``, best first."""
        limit = self.config.top_k if limit is None else limit
        floor = self.config.min_score if min_score is None else min_score

        kw_hits = self._keyword_hits(query, limit)
        sem_hits = self._semantic_hits(query, limit)

        kw_scores = self._normalise([h.score for h in kw_hits])
        sem_scores = self._normalise([h.score for h in sem_hits])

        use_kw = self.config.keyword_weight if kw_hits else 0.0
        use_sem = self.config.semantic_weight if sem_hits else 0.0
        total = use_kw + use_sem
        if total <= 0.0:
            return []
        use_kw, use_sem = use_kw / total, use_sem / total

        # Fuse per-row: accumulate weighted normalised scores.
        fused: dict[tuple[str, int], dict] = {}
        for hit, norm in zip(kw_hits, kw_scores):
            self._accumulate(fused, hit, norm * use_kw)
        for hit, norm in zip(sem_hits, sem_scores):
            self._accumulate(fused, hit, norm * use_sem)

        results: list[ScoredHit] = []
        for (table, row_id), acc in fused.items():
            source = "hybrid"
            if not kw_hits and sem_hits:
                source = "semantic"
            elif kw_hits and not sem_hits:
                source = "keyword"
            results.append(
                ScoredHit(table, row_id, acc["content"], acc["score"], source, acc["extra"])
            )
        results.sort(key=lambda r: r.score, reverse=True)
        return [r for r in results[:limit] if r.score >= floor]

    def recall_history(
        self, session_id: str | None = None, limit: int = 20
    ) -> list[dict]:
        """Recent conversation turns, oldest first (for agent context)."""
        return self.store.recent_episodes(session_id=session_id, limit=limit)

    def index(self, batch_size: int | None = None) -> int:
        """Backfill embeddings for every row that lacks one. Returns rows embedded."""
        if self.embedder is None or not getattr(self.embedder, "config", None):
            return 0
        try:
            available = self.embedder.available
        except Exception as exc:
            logger.warning("embedder unavailable during index(): %s", exc)
            return 0
        if not available:
            return 0
        model = self.embedder.config.model
        batch_size = batch_size or 32
        pending = self.store.rows_needing_embedding(model)
        embedded = 0
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            rows = [self.store.get_row(t, rid) for t, rid in batch]
            texts = [r["content"] for r in rows if r]
            if not texts:
                continue
            try:
                vectors = self.embedder.embed(texts)
            except Exception as exc:
                logger.warning("embedding batch failed: %s", exc)
                break
            for (table, row_id), vec in zip(batch, vectors):
                self.store.store_embedding(
                    table, row_id, model, np.asarray(vec, dtype=np.float32).tobytes()
                )
                embedded += 1
        return embedded

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _keyword_hits(self, query: str, limit: int) -> list[ScoredHit]:
        rows = self.store.keyword_search(query, limit=limit)
        return [
            ScoredHit(r["table"], r["row_id"], r["content"], float(r["score"]), "keyword", r)
            for r in rows
        ]

    def _semantic_hits(self, query: str, limit: int) -> list[ScoredHit]:
        if self.embedder is None:
            return []
        try:
            if not self.embedder.available:
                return []
            qvec = np.asarray(self.embedder.embed(query), dtype=np.float32)
        except Exception as exc:
            logger.warning("semantic recall unavailable: %s", exc)
            return []
        model = self.embedder.config.model
        qnorm = float(np.linalg.norm(qvec))
        if qnorm == 0.0:
            return []
        scored: list[tuple[float, dict]] = []
        for table, row_id, blob in self.store.iter_embeddings(model):
            vec = _decode_vector(blob)
            sim = float(np.dot(qvec, vec) / (qnorm * np.linalg.norm(vec) + 1e-9))
            row = self.store.get_row(table, row_id)
            if row:
                scored.append((sim, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            ScoredHit(r["table"], r["row_id"], r["content"], sim, "semantic", r)
            for sim, r in scored[:limit]
        ]

    @staticmethod
    def _accumulate(
        fused: dict, hit: ScoredHit, contribution: float
    ) -> None:
        key = (hit.table, hit.row_id)
        acc = fused.setdefault(
            key, {"score": 0.0, "content": hit.content, "extra": hit.extra}
        )
        acc["score"] += contribution

    @staticmethod
    def _normalise(scores: list[float]) -> list[float]:
        if not scores:
            return []
        lo, hi = min(scores), max(scores)
        if hi - lo < 1e-9:
            return [1.0] * len(scores)
        return [(s - lo) / (hi - lo) for s in scores]
