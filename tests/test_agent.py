"""Tests for the agent loop (stubbed LLM, real memory store)."""

from __future__ import annotations

from app.agent.agent import Agent, AgentConfig
from app.agent.recall.retriever import Recaller
from app.agent.recall.store import Fact


class StubLLM:
    """Returns pre-scripted normalised responses; records what it saw."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, tools=None):
        self.calls.append((messages, tools))
        return self.responses.pop(0)


class ToolRefusingLLM:
    """Raises like Ollama when a model has no tool support, then works."""

    def __init__(self, fallback):
        self.fallback = fallback
        self.calls = []

    def chat(self, messages, tools=None):
        self.calls.append((messages, tools))
        if tools:
            raise RuntimeError(
                "Error code: 400 - {'message': 'registry.ollama.ai/library/x:latest "
                "does not support tools'}"
            )
        return self.fallback


def _plain(text):
    return {"role": "assistant", "content": text, "tool_calls": []}


def _tool_call(tc_id, name, arguments):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": tc_id, "name": name, "arguments": arguments}],
    }


def make_agent(store, llm, **kwargs):
    return Agent(llm, store, recaller=Recaller(store), **kwargs)


def test_plain_reply_records_episodes(store):
    agent = make_agent(store, StubLLM([_plain("hello there")]))
    reply = agent.handle_turn("say hi")
    assert reply == "hello there"
    roles = [e["role"] for e in store.recent_episodes(limit=10)]
    assert roles == ["user", "assistant"]


def test_system_prompt_has_context_and_memories(store):
    store.add_fact(Fact("User prefers the terminal", tags=("preference",)))
    llm = StubLLM([_plain("ok")])
    agent = make_agent(store, llm)
    agent.handle_turn("terminal")
    messages = llm.calls[0][0]
    system = messages[0]["content"]
    assert "You are Jarvis" in system
    assert "Focused window:" in system
    assert "terminal" in system  # recalled memory injected
    assert messages[-2]["role"] == "user"  # assistant reply appended after the call


def test_tool_call_remember_then_reply(store):
    llm = StubLLM(
        [
            _tool_call("c1", "remember", {"content": "User likes tea"}),
            _plain("remembered"),
        ]
    )
    agent = make_agent(store, llm)
    reply = agent.handle_turn("remember I like tea")
    assert reply == "remembered"
    assert store.keyword_search("tea")
    # the tool result was fed back to the model
    call_messages, tools = llm.calls[1]
    assert call_messages[-2]["role"] == "tool"
    assert "stored fact" in call_messages[-2]["content"]
    tool_names = [t["function"]["name"] for t in tools]
    assert "remember" in tool_names and "recall" in tool_names


def test_unknown_tool_result_is_safe(store):
    llm = StubLLM(
        [
            _tool_call("c2", "definitely_not_a_tool", {}),
            _plain("recovered"),
        ]
    )
    agent = make_agent(store, llm)
    reply = agent.handle_turn("do the impossible")
    assert reply == "recovered"
    assert "unknown tool" in llm.calls[1][0][-2]["content"]


def test_max_iterations_bounded(store):
    llm = StubLLM(
        [
            _tool_call("c3", "recall", {"query": "x"}),
            _tool_call("c4", "recall", {"query": "x"}),
            _tool_call("c5", "recall", {"query": "x"}),
            _tool_call("c6", "recall", {"query": "x"}),
            _tool_call("c7", "recall", {"query": "x"}),
            _tool_call("c8", "recall", {"query": "x"}),  # 6th call, beyond limit
        ]
    )
    agent = make_agent(store, llm, config=AgentConfig(max_tool_iterations=5))
    reply = agent.handle_turn("loop forever")
    assert "no final answer" in reply
    assert len(llm.calls) == 5


def test_conversation_history_carries_across_turns(store):
    llm = StubLLM([_plain("first reply"), _plain("second reply")])
    agent = make_agent(store, llm)
    agent.handle_turn("first message")
    agent.handle_turn("second message")
    # second call included the first exchange as history
    messages = llm.calls[1][0]
    assert {"role": "user", "content": "first message"} in messages
    assert {"role": "assistant", "content": "first reply"} in messages


def test_degrades_to_no_tools_when_model_refuses(store):
    llm = ToolRefusingLLM(_plain("I cannot use tools but here is the answer"))
    agent = make_agent(store, llm)
    reply = agent.handle_turn("open notepad")
    assert "here is the answer" in reply
    # first call asked for tools, retry did not
    assert llm.calls[0][1] is not None
    assert llm.calls[1][1] is None
    assert agent._tools_supported is False
    roles = [e["role"] for e in store.recent_episodes(limit=10)]
    assert roles == ["user", "assistant"]
