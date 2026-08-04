"""Tests for the SQLite-backed MemoryStore."""

from __future__ import annotations

import sqlite3

import pytest

from app.agent.recall.store import Episode, Fact, MemoryStore


def test_add_and_get_fact(store):
    fid = store.add_fact(Fact("User prefers the terminal", tags=("preference",)))
    row = store.get_row("facts", fid)
    assert row["content"] == "User prefers the terminal"
    assert row["tags"] == "preference"
    assert row["importance"] == 0.5


def test_add_episode_scoped_to_session(store):
    store.add_episode(Episode("user", "open the project folder", session_id="s1"))
    store.add_episode(Episode("assistant", "done", session_id="s1"))
    store.add_episode(Episode("user", "unrelated", session_id="s2"))
    history = store.recent_episodes(session_id="s1")
    assert [e["role"] for e in history] == ["user", "assistant"]


def test_keyword_search_finds_relevant_fact(store):
    store.add_fact(Fact("User prefers the terminal over GUI", tags=("preference",)))
    store.add_fact(Fact("Default output directory is D:/outputs"))
    hits = store.keyword_search("terminal")
    assert len(hits) == 1
    assert hits[0]["table"] == "facts"
    assert "terminal" in hits[0]["content"]


def test_keyword_search_spans_episodes(store):
    store.add_episode(Episode("user", "how do I throw a file?", session_id="s1"))
    hits = store.keyword_search("throw")
    assert hits[0]["table"] == "episodes"


def test_update_fact_refreshes_fts(store):
    fid = store.add_fact(Fact("old keyword content"))
    assert store.keyword_search("old") and not store.keyword_search("new")
    assert store.update_fact(fid, content="new keyword content")
    assert store.keyword_search("new") and not store.keyword_search("old")


def test_delete_removes_from_fts(store):
    fid = store.add_fact(Fact("delete me please"))
    assert store.keyword_search("delete")
    assert store.delete("facts", fid) is True
    assert not store.keyword_search("delete")
    assert store.delete("facts", fid) is False


def test_mark_recalled_tracks_frequency(store):
    fid = store.add_fact(Fact("frequently asked fact"))
    store.mark_recalled("facts", fid)
    store.mark_recalled("facts", fid)
    assert store.get_row("facts", fid)["recall_count"] == 2
    assert store.get_row("facts", fid)["last_recalled_at"] is not None


def test_embeddings_round_trip(store):
    fid = store.add_fact(Fact("fact to embed"))
    store.store_embedding("facts", fid, "model-x", b"\x00\x00\x80\x3f")
    rows = store.iter_embeddings("model-x")
    assert rows == [("facts", fid, b"\x00\x00\x80\x3f")]
    assert store.rows_needing_embedding("model-x") == []
    assert store.get_row("facts", fid)["content"] == "fact to embed"


def test_delete_drops_embedding(store):
    fid = store.add_fact(Fact("embed me"))
    store.store_embedding("facts", fid, "model-x", b"\x00\x00\x80\x3f")
    store.delete("facts", fid)
    assert store.iter_embeddings("model-x") == []


def test_persists_across_reopen(tmp_path):
    db = tmp_path / "mem.db"
    with MemoryStore(db) as ms:
        ms.add_fact(Fact("survives restart"))
    with MemoryStore(db) as ms:
        hits = ms.keyword_search("survives")
        assert len(hits) == 1


def test_stats(store):
    store.add_fact(Fact("a"))
    store.add_episode(Episode("user", "b"))
    stats = store.stats()
    assert stats["facts"] == 1
    assert stats["episodes"] == 1


def test_fts_fallback_on_bad_query(store):
    store.add_fact(Fact("plain content here"))
    hits = store.keyword_search("plain )(")
    assert isinstance(hits, list)  # never raises, even on FTS syntax errors


def test_like_fallback_when_fts_disabled(store):
    store.add_fact(Fact("find me by substring"))
    store._fts_available = False
    hits = store.keyword_search("substring")
    assert len(hits) == 1
    assert "substring" in hits[0]["content"]
