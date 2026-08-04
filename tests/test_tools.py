"""Tests for the tool registry and built-in tools."""

from __future__ import annotations

from app.agent.recall.retriever import Recaller
from app.agent.recall.store import Fact
from app.agent.tools import Tool, ToolRegistry
from app.agent.tools.tools import default_tools


def test_registry_register_get_schemas():
    reg = ToolRegistry()
    reg.register(Tool("ping", "returns pong", {"type": "object"}, lambda: "pong"))
    assert reg.get("ping").fn() == "pong"
    assert reg.names() == ["ping"]
    schema = reg.schemas()[0]
    assert schema["function"]["name"] == "ping"
    assert schema["function"]["description"] == "returns pong"


def test_registry_execute_returns_strings_never_raises():
    reg = ToolRegistry()
    reg.register(Tool("boom", "always fails", {"type": "object"}, lambda: 1 / 0))
    assert "failed" in reg.execute("boom", {})
    assert "unknown tool" in reg.execute("nope", {})
    assert "bad arguments" in reg.execute("boom", {"unexpected": 1})


def test_remember_tool_stores_fact(store):
    reg = default_tools(store, Recaller(store))
    result = reg.execute("remember", {"content": "User likes tea", "kind": "preference"})
    assert "stored fact" in result
    hits = store.keyword_search("tea")
    assert hits[0]["kind"] == "preference"
    assert hits[0]["tags"] == ""


def test_remember_tool_accepts_string_or_list_tags(store):
    reg = default_tools(store, Recaller(store))
    reg.execute("remember", {"content": "a", "tags": "x, y"})
    reg.execute("remember", {"content": "b", "tags": ["p", "q"]})
    assert store.get_row("facts", 1)["tags"] == "x,y"
    assert store.get_row("facts", 2)["tags"] == "p,q"


def test_recall_tool_returns_memories(store):
    store.add_fact(Fact("User prefers the terminal", tags=("preference",)))
    reg = default_tools(store, Recaller(store))
    result = reg.execute("recall", {"query": "terminal"})
    assert "terminal" in result
    assert reg.execute("recall", {"query": "zzzz-no-such-word"}) == "nothing found in memory"


def test_web_search_opens_browser(monkeypatch, store):
    opened = []
    monkeypatch.setattr("app.agent.tools.tools.webbrowser.open", lambda url: opened.append(url))
    reg = default_tools(store, Recaller(store))
    result = reg.execute("web_search", {"query": "local LLM"})
    assert result.startswith("opened browser")
    assert opened and "q=local%20LLM" in opened[0]


def test_open_path_uses_startfile(monkeypatch, store):
    started = []
    monkeypatch.setattr("app.agent.tools.tools.os.startfile", lambda p: started.append(p))
    reg = default_tools(store, Recaller(store))
    result = reg.execute("open_path", {"path": "~/Documents"})
    assert result.startswith("opened")
    assert "Documents" in started[0]


def test_open_app_launches_subprocess(monkeypatch, store):
    calls = []
    monkeypatch.setattr(
        "app.agent.tools.tools.subprocess.Popen",
        lambda cmd, **kwargs: calls.append((cmd, kwargs)),
    )
    reg = default_tools(store, Recaller(store))
    result = reg.execute("open_app", {"target": "notepad"})
    assert result.startswith("launched")
    assert "notepad" in calls[0][0]
