"""Tests for the agent context builder."""

from __future__ import annotations

from app.agent.context import AgentContext, build_context
from app.agent.recall.retriever import Recaller
from app.agent.recall.store import Episode, Fact


def test_build_context_combines_history_and_memories(store):
    store.add_episode(Episode("user", "open the project folder", session_id="s1"))
    store.add_episode(Episode("assistant", "opened it", session_id="s1"))
    store.add_fact(Fact("User prefers the terminal", tags=("preference",)))
    recaller = Recaller(store)  # no embedder -> keyword recall

    ctx = build_context(store, recaller, "terminal preference", session_id="s1")

    assert isinstance(ctx, AgentContext)
    assert [e["role"] for e in ctx.history] == ["user", "assistant"]
    assert ctx.memories
    assert ctx.memories[0].source == "keyword"
    assert "terminal" in ctx.memories[0].content


def test_to_prompt_includes_all_sections(store):
    store.add_episode(Episode("user", "say hello", session_id="s2"))
    store.add_fact(Fact("Jarvis answers in short replies"))
    recaller = Recaller(store)
    ctx = build_context(store, recaller, "short replies", session_id="s2")

    prompt = ctx.to_prompt()
    assert "## Current request\nshort replies" in prompt
    assert "## Recent conversation" in prompt
    assert "- user: say hello" in prompt
    assert "## Relevant long-term memories" in prompt
    assert "short replies" in prompt


def test_to_prompt_with_empty_memory(store):
    recaller = Recaller(store)
    ctx = build_context(store, recaller, "nothing here")
    prompt = ctx.to_prompt()
    assert "## Current request" in prompt
    assert "## Recent conversation" not in prompt
    assert "## Relevant long-term memories" not in prompt
