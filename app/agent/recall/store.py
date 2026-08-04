"""SQLite-backed memory store for the JARVIS agent.

Two kinds of rows:

* **facts** — durable long-term memories (facts, preferences, entities)
  with kind, tags, and importance for prioritised recall.
* **episodes** — conversation turns (system/user/assistant/tool), grouped
  by ``session_id`` for continuity across sessions.

Recall works through an FTS5 virtual table (``mem_fts``) covering both
tables. If the platform's SQLite lacks FTS5, searches transparently fall
back to ``LIKE``. Optional dense embeddings are stored in the
``embeddings`` table as float32 blobs and are used by the hybrid retriever.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content         TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'fact',   -- fact | preference | entity
    tags            TEXT NOT NULL DEFAULT '',       -- comma-separated
    importance      REAL NOT NULL DEFAULT 0.5,      -- 0..1
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    recall_count    INTEGER NOT NULL DEFAULT 0,
    last_recalled_at TEXT
);

CREATE TABLE IF NOT EXISTS episodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT,
    role        TEXT NOT NULL,                      -- system | user | assistant | tool
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS embeddings (
    table_name  TEXT NOT NULL,
    row_id      INTEGER NOT NULL,
    model       TEXT NOT NULL,
    vector      BLOB NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (table_name, row_id, model)
);

CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(
    content, tags, kind,
    table_name UNINDEXED, row_id UNINDEXED
);
"""

_FACT_COLS = (
    "id", "content", "kind", "tags", "importance",
    "created_at", "updated_at", "recall_count", "last_recalled_at",
)
_EPISODE_COLS = ("id", "session_id", "role", "content", "created_at")


@dataclass
class Fact:
    """A durable long-term memory."""

    content: str
    kind: str = "fact"
    tags: tuple[str, ...] = ()
    importance: float = 0.5


@dataclass
class Episode:
    """A single conversation turn."""

    role: str
    content: str
    session_id: str | None = None


class MemoryStore:
    """Persistent memory store. Use as a context manager for auto-close."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._fts_available = True
        self._init_schema()

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # writes
    # ------------------------------------------------------------------ #

    def add_fact(self, fact: Fact) -> int:
        tags = ",".join(fact.tags)
        cur = self._conn.execute(
            "INSERT INTO facts (content, kind, tags, importance) VALUES (?, ?, ?, ?)",
            (fact.content, fact.kind, tags, fact.importance),
        )
        row_id = cur.lastrowid
        self._insert_fts("facts", row_id, fact.content, tags, fact.kind)
        self._conn.commit()
        return row_id

    def add_episode(self, episode: Episode) -> int:
        cur = self._conn.execute(
            "INSERT INTO episodes (session_id, role, content) VALUES (?, ?, ?)",
            (episode.session_id, episode.role, episode.content),
        )
        row_id = cur.lastrowid
        self._insert_fts("episodes", row_id, episode.content, "", episode.role)
        self._conn.commit()
        return row_id

    def update_fact(
        self,
        fact_id: int,
        content: str | None = None,
        tags: tuple[str, ...] | None = None,
        importance: float | None = None,
    ) -> bool:
        existing = self.get_row("facts", fact_id)
        if existing is None:
            return False
        new_content = existing["content"] if content is None else content
        new_tags = existing["tags"] if tags is None else ",".join(tags)
        new_importance = existing["importance"] if importance is None else importance
        with self._conn:
            self._conn.execute(
                "UPDATE facts SET content=?, tags=?, importance=?, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                (new_content, new_tags, new_importance, fact_id),
            )
            self._replace_fts("facts", fact_id, new_content, new_tags)
            self._conn.execute(
                "DELETE FROM embeddings WHERE table_name='facts' AND row_id=?",
                (fact_id,),
            )
        return True

    def delete(self, table: str, row_id: int) -> bool:
        if table not in ("facts", "episodes"):
            raise ValueError(f"unknown table: {table}")
        with self._conn:
            cur = self._conn.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
            if cur.rowcount == 0:
                return False
            self._conn.execute(
                "DELETE FROM mem_fts WHERE table_name=? AND row_id=?",
                (table, row_id),
            )
            self._conn.execute(
                "DELETE FROM embeddings WHERE table_name=? AND row_id=?",
                (table, row_id),
            )
        return True

    def mark_recalled(self, table: str, row_id: int) -> None:
        """Bump recall frequency for ranking feedback (facts only)."""
        if table == "facts":
            self._conn.execute(
                "UPDATE facts SET recall_count=recall_count+1, "
                "last_recalled_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                (row_id,),
            )
            self._conn.commit()

    # ------------------------------------------------------------------ #
    # reads
    # ------------------------------------------------------------------ #

    def get_row(self, table: str, row_id: int) -> dict | None:
        if table == "facts":
            cols, tname = _FACT_COLS, "facts"
        elif table == "episodes":
            cols, tname = _EPISODE_COLS, "episodes"
        else:
            raise ValueError(f"unknown table: {table}")
        row = self._conn.execute(
            f"SELECT {', '.join(cols)} FROM {tname} WHERE id=?", (row_id,)
        ).fetchone()
        return dict(row) if row else None

    def recent_episodes(self, session_id: str | None = None, limit: int = 20) -> list[dict]:
        if session_id is None:
            cur = self._conn.execute(
                "SELECT * FROM episodes ORDER BY id DESC LIMIT ?", (limit,)
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM episodes WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            )
        return [dict(r) for r in reversed(cur.fetchall())]

    def keyword_search(
        self, query: str, limit: int = 10, tables: tuple[str, ...] = ("facts", "episodes")
    ) -> list[dict]:
        """BM25 (FTS5) search over facts + episodes, else LIKE fallback."""
        hits = self._fts_search(query, limit, tables)
        if hits is None:
            hits = self._like_search(query, limit, tables)
        results: list[dict] = []
        for table, row_id, score in hits:
            row = self.get_row(table, row_id)
            if row is None:
                continue
            row = dict(row)
            row["table"] = table
            row["row_id"] = row_id
            row["score"] = score
            results.append(row)
        return results

    def iter_embeddings(self, model: str) -> list[tuple[str, int, bytes]]:
        cur = self._conn.execute(
            "SELECT table_name, row_id, vector FROM embeddings WHERE model=? ORDER BY row_id",
            (model,),
        )
        return [(r["table_name"], r["row_id"], r["vector"]) for r in cur.fetchall()]

    def store_embedding(self, table: str, row_id: int, model: str, vector: bytes) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO embeddings (table_name, row_id, model, vector) "
            "VALUES (?, ?, ?, ?)",
            (table, row_id, model, vector),
        )
        self._conn.commit()

    def rows_needing_embedding(self, model: str) -> list[tuple[str, int]]:
        cur = self._conn.execute(
            "SELECT table_name, id FROM ("
            "  SELECT 'facts' AS table_name, id FROM facts "
            "  UNION ALL SELECT 'episodes', id FROM episodes"
            ") WHERE (table_name, id) NOT IN ("
            "  SELECT table_name, row_id FROM embeddings WHERE model=?"
            ") ORDER BY id",
            (model,),
        )
        return [(r["table_name"], r["id"]) for r in cur.fetchall()]

    def stats(self) -> dict:
        counts = {}
        for table in ("facts", "episodes"):
            counts[table] = self._conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
        counts["embeddings"] = self._conn.execute(
            "SELECT COUNT(*) FROM embeddings"
        ).fetchone()[0]
        return counts

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _insert_fts(self, table: str, row_id: int, content: str, tags: str, kind: str) -> None:
        if not self._fts_available:
            return
        try:
            self._conn.execute(
                "INSERT INTO mem_fts (table_name, row_id, content, tags, kind) "
                "VALUES (?, ?, ?, ?, ?)",
                (table, row_id, content, tags, kind),
            )
        except sqlite3.OperationalError:
            self._fts_available = False

    def _replace_fts(self, table: str, row_id: int, content: str, tags: str) -> None:
        if not self._fts_available:
            return
        self._conn.execute(
            "DELETE FROM mem_fts WHERE table_name=? AND row_id=?", (table, row_id)
        )
        self._insert_fts(table, row_id, content, tags, "")

    def _fts_search(
        self, query: str, limit: int, tables: tuple[str, ...]
    ) -> list[tuple[str, int, float]] | None:
        if not self._fts_available:
            return None
        if "facts" in tables:
            q = query
            if "episodes" not in tables:
                q = f"table_name:facts AND ({query})"
        elif "episodes" in tables:
            q = f"table_name:episodes AND ({query})"
        else:
            return None
        try:
            cur = self._conn.execute(
                "SELECT table_name, row_id, bm25(mem_fts) AS score FROM mem_fts "
                "WHERE mem_fts MATCH ? ORDER BY score LIMIT ?",
                (q, limit),
            )
        except sqlite3.OperationalError:
            return None
        return [(r["table_name"], r["row_id"], -r["score"]) for r in cur.fetchall()]

    def _like_search(
        self, query: str, limit: int, tables: tuple[str, ...]
    ) -> list[tuple[str, int, float]]:
        like = f"%{query}%"
        results: list[tuple[str, int, float]] = []
        if "facts" in tables:
            for r in self._conn.execute(
                "SELECT id FROM facts WHERE content LIKE ? OR tags LIKE ?",
                (like, like),
            ):
                results.append(("facts", r["id"], 0.0))
        if "episodes" in tables:
            for r in self._conn.execute(
                "SELECT id FROM episodes WHERE content LIKE ?", (like,)
            ):
                results.append(("episodes", r["id"], 0.0))
        return results[:limit]
