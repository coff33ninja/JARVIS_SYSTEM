"""Tests for the voice loop (fake mic/STT/TTS, real agent + store)."""

from __future__ import annotations

import numpy as np

from app.agent.agent import Agent
from app.agent.recall.retriever import Recaller
from app.agent.voice import VoiceConfig, VoiceLoop

LOUD = np.ones(16000, dtype=np.float32) * 0.1
QUIET = np.zeros(16000, dtype=np.float32)


class StubLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, tools=None):
        self.calls.append((messages, tools))
        return self.responses.pop(0)


def _plain(text):
    return {"role": "assistant", "content": text, "tool_calls": []}


class FakeSTT:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = 0

    def transcribe(self, audio):
        self.calls += 1
        return self.texts.pop(0)


class FakeTTS:
    def __init__(self, available=True):
        self.available = available
        self.said = []

    def say(self, text):
        self.said.append(text)


class FakeMic:
    @staticmethod
    def rms(samples):
        if samples is None or samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))

    def __init__(self, samples):
        self.samples = samples
        self.recorded = 0

    def record_until_silence(self, **kwargs):
        self.recorded += 1
        return self.samples


def make_loop(
    store, mic_samples, stt_texts, wake="jarvis", mode="keyword", llm_responses=None
):
    llm = StubLLM(llm_responses or [_plain("on it")])
    agent = Agent(llm, store, recaller=Recaller(store))
    return (
        VoiceLoop(
            agent,
            FakeSTT(stt_texts),
            FakeTTS(),
            mic=FakeMic(mic_samples),
            config=VoiceConfig(wake_word=wake, wake_mode=mode),
        ),
        agent,
    )


def test_no_wake_word_ignored(store):
    loop, agent = make_loop(store, LOUD, ["hello computer"])
    result = loop.run_once()
    assert result is None
    assert agent.llm.calls == []
    assert loop.tts.said == []


def test_silence_ignored(store):
    loop, _ = make_loop(store, QUIET, ["jarvis hello"])
    assert loop.run_once() is None


def test_wake_word_triggers_turn(store):
    loop, agent = make_loop(store, LOUD, ["jarvis open notepad"])
    result = loop.run_once()
    assert result["command"] == "open notepad"
    assert len(agent.llm.calls) == 1
    assert loop.tts.said == ["on it"]
    assert result["reply"] == "on it"
    assert result["transcript"]  # episodes recorded for the HUD


def test_wake_word_case_insensitive(store):
    loop, _ = make_loop(store, LOUD, ["JARVIS, open the project folder"], wake="Jarvis")
    result = loop.run_once()
    assert result["command"] == "open the project folder"


def test_wake_word_stripped_with_punctuation(store):
    loop, _ = make_loop(store, LOUD, ["hey jarvis... open settings"])
    result = loop.run_once()
    assert result["command"] == "open settings"


def test_wake_phrase_only_yields_no_command(store):
    loop, _ = make_loop(store, LOUD, ["jarvis"])
    assert loop.run_once() is None


def test_push_to_talk_skips_wake_check(store):
    loop, agent = make_loop(store, LOUD, ["open calculator"], mode="push_to_talk")
    result = loop.run_once(trigger="ptt")
    assert result["command"] == "open calculator"
    assert len(agent.llm.calls) == 1


def test_wake_mode_off_acts_on_any_speech(store):
    loop, agent = make_loop(store, LOUD, ["what time is it"], mode="off")
    result = loop.run_once()
    assert result["command"] == "what time is it"
    assert len(agent.llm.calls) == 1


# --------------------------------------------------------------------- #
# on_command mode-switch hook
# --------------------------------------------------------------------- #


def _command_hook(command):
    if "chat" in command.lower():
        return "Chat mode."
    return None


def test_mode_command_short_circuits_agent(store):
    loop, agent = make_loop(store, LOUD, ["jarvis chat mode"])
    loop.on_command = _command_hook
    result = loop.run_once()
    assert result["command"] == "chat mode"
    assert result["mode_change"] is True
    assert result["reply"] == "Chat mode."
    assert agent.llm.calls == []  # mode switch never hit the LLM
    assert loop.tts.said == ["Chat mode."]


def test_non_mode_command_still_runs_agent(store):
    loop, agent = make_loop(
        store, LOUD, ["jarvis open settings"], llm_responses=[_plain("done")]
    )
    loop.on_command = _command_hook
    result = loop.run_once()
    assert result["command"] == "open settings"
    assert "mode_change" not in result
    assert len(agent.llm.calls) == 1
    assert loop.tts.said == ["done"]
