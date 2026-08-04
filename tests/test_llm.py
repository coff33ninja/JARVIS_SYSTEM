"""Tests for the OpenAI-compatible LLM client (no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent.llm import LLMClient, LLMConfig


def _msg(role="assistant", content="", tool_calls=None):
    tcs = None
    if tool_calls:
        tcs = [
            SimpleNamespace(
                id=tc_id,
                function=SimpleNamespace(name=name, arguments=arguments),
            )
            for tc_id, name, arguments in tool_calls
        ]
    return SimpleNamespace(role=role, content=content, tool_calls=tcs)


def _resp(*messages):
    return SimpleNamespace(choices=[SimpleNamespace(message=m) for m in messages])


class FakeChat:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeModels:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = 0

    def list(self):
        self.calls += 1
        if not self.ok:
            raise RuntimeError("connection refused")
        return [SimpleNamespace(id="fake")]


class FakeClient:
    def __init__(self, responses=None, models_ok=True):
        self.chat = SimpleNamespace(completions=FakeChat(responses or []))
        self.models = FakeModels(models_ok)


def _make_client(responses=None, models_ok=True, monkeypatch=None):
    client = LLMClient(LLMConfig(base_url="http://localhost:9/v1", model="fake"))
    fake = FakeClient(responses, models_ok)
    client._build_client = lambda: fake
    return client, fake


def test_available_true_and_cached(monkeypatch):
    client, fake = _make_client(models_ok=True, monkeypatch=monkeypatch)
    assert client.available is True
    assert client.available is True
    assert fake.models.calls == 1  # probe result cached, no second ping


def test_available_false_when_down(monkeypatch):
    client, _ = _make_client(models_ok=False, monkeypatch=monkeypatch)
    assert client.available is False


def test_chat_normalises_plain_response(monkeypatch):
    client, fake = _make_client(
        responses=[_resp(_msg(content="hello there"))], monkeypatch=monkeypatch
    )
    out = client.chat([{"role": "user", "content": "hi"}])
    assert out == {"role": "assistant", "content": "hello there", "tool_calls": []}
    assert fake.chat.completions.calls[0]["model"] == "fake"


def test_chat_normalises_tool_calls(monkeypatch):
    client, _ = _make_client(
        responses=[_resp(_msg(tool_calls=[("tc1", "remember", '{"content": "tea"}')]))],
        monkeypatch=monkeypatch,
    )
    out = client.chat([{"role": "user", "content": "remember this"}])
    assert out["tool_calls"] == [
        {"id": "tc1", "name": "remember", "arguments": {"content": "tea"}}
    ]


def test_chat_parses_bad_tool_arguments_as_empty(monkeypatch):
    client, _ = _make_client(
        responses=[_resp(_msg(tool_calls=[("tc2", "open_app", "not-json")]))],
        monkeypatch=monkeypatch,
    )
    out = client.chat([{"role": "user", "content": "x"}])
    assert out["tool_calls"][0]["arguments"] == {}


def test_chat_passes_tools_only_when_given(monkeypatch):
    client, fake = _make_client(
        responses=[_resp(_msg(content="ok"))], monkeypatch=monkeypatch
    )
    client.chat([{"role": "user", "content": "x"}], tools=[{"type": "function"}])
    call = fake.chat.completions.calls[0]
    assert call["tools"] == [{"type": "function"}]


def test_chat_raises_when_client_unavailable(monkeypatch):
    client = LLMClient(LLMConfig())
    client._build_client = lambda: None
    with pytest.raises(RuntimeError):
        client.chat([{"role": "user", "content": "x"}])
