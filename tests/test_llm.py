"""Tests for the OpenAI-compatible LLM client (no network)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
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
    def __init__(self, ok=True, ids=("fake",)):
        self.ok = ok
        self.calls = 0
        self.ids = list(ids)

    def list(self):
        self.calls += 1
        if not self.ok:
            raise RuntimeError("connection refused")
        return SimpleNamespace(data=[SimpleNamespace(id=i) for i in self.ids])


class FakeClient:
    def __init__(self, responses=None, models_ok=True, model_ids=("fake",)):
        self.chat = SimpleNamespace(completions=FakeChat(responses or []))
        self.models = FakeModels(models_ok, model_ids)


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


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeURLopener:
    """Queue of responses/errors, one per urlopen call."""

    def __init__(self, handlers):
        self.handlers = list(handlers)
        self.calls = []

    def __call__(self, url, timeout=None, **kw):
        self.calls.append((url, timeout))
        handler = self.handlers.pop(0)
        if isinstance(handler, Exception):
            raise handler
        return FakeResponse(json.dumps(handler).encode())


def _make_auto_pull_client(
    monkeypatch, model="llama3.2", ids=("other",), auto_pull=True, models_ok=True
):
    client = LLMClient(
        LLMConfig(
            base_url="http://localhost:9/v1",
            model=model,
            auto_pull=auto_pull,
        )
    )
    fake = FakeClient(models_ok=models_ok, model_ids=ids)
    client._build_client = lambda: fake
    return client, fake


def test_ensure_model_true_when_installed(monkeypatch):
    opener = FakeURLopener([])
    monkeypatch.setattr(urllib.request, "urlopen", opener)
    client, _ = _make_auto_pull_client(monkeypatch, ids=("llama3.2",))
    assert client.ensure_model() is True
    assert opener.calls == []  # no pull needed


def test_ensure_model_pulls_when_missing(monkeypatch):
    opener = FakeURLopener(
        [
            {"models": [{"name": "other"}]},  # GET /api/tags
            {"status": "success"},  # POST /api/pull
        ]
    )
    monkeypatch.setattr(urllib.request, "urlopen", opener)
    client, _ = _make_auto_pull_client(monkeypatch)
    assert client.ensure_model() is True
    tags_url, _ = opener.calls[0]
    assert tags_url == "http://localhost:9/api/tags"
    pull_url, pull_timeout = opener.calls[1]
    assert pull_url.full_url == "http://localhost:9/api/pull"
    assert pull_timeout == 3600


def test_ensure_model_ignores_tag_suffix(monkeypatch):
    opener = FakeURLopener([])
    monkeypatch.setattr(urllib.request, "urlopen", opener)
    client, _ = _make_auto_pull_client(
        monkeypatch, model="llama3.2:latest", ids=("llama3.2",)
    )
    assert client.ensure_model() is True
    assert opener.calls == []


def test_ensure_model_false_when_not_ollama(monkeypatch):
    opener = FakeURLopener([urllib.error.URLError("no /api/tags")])
    monkeypatch.setattr(urllib.request, "urlopen", opener)
    client, _ = _make_auto_pull_client(monkeypatch)
    assert client.ensure_model() is False
    assert len(opener.calls) == 1  # never attempted a pull


def test_ensure_model_disabled(monkeypatch):
    client, _ = _make_auto_pull_client(monkeypatch, auto_pull=False)
    assert client.ensure_model() is False


def test_ensure_model_false_when_endpoint_down(monkeypatch):
    client, _ = _make_auto_pull_client(monkeypatch, models_ok=False)
    assert client.ensure_model() is False


def test_ensure_model_pull_failure(monkeypatch):
    opener = FakeURLopener(
        [
            {"models": []},
            {"status": "error", "error": "blob unknown"},
        ]
    )
    monkeypatch.setattr(urllib.request, "urlopen", opener)
    client, _ = _make_auto_pull_client(monkeypatch)
    assert client.ensure_model() is False


def test_ensure_model_pull_network_error(monkeypatch):
    opener = FakeURLopener(
        [
            {"models": []},
            urllib.error.URLError("timeout"),
        ]
    )
    monkeypatch.setattr(urllib.request, "urlopen", opener)
    client, _ = _make_auto_pull_client(monkeypatch)
    assert client.ensure_model() is False


def test_from_env_auto_pull_parsing(monkeypatch):
    monkeypatch.setenv("JARVIS_LLM_AUTO_PULL", "0")
    assert LLMConfig.from_env().auto_pull is False
    monkeypatch.setenv("JARVIS_LLM_AUTO_PULL", "true")
    assert LLMConfig.from_env().auto_pull is True
