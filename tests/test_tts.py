"""Tests for the TTS engine (SAPI default + optional Piper backend)."""

from __future__ import annotations

import winsound

import pytest

from app.agent.tts import TTSConfig, TTSEngine


class _FakeVoice:
    def __init__(self, desc):
        self.desc = desc

    def GetDescription(self):
        return self.desc


class _FakeVoices:
    def __init__(self, items):
        self.items = items

    @property
    def Count(self):
        return len(self.items)

    def Item(self, i):
        return self.items[i]


class _FakeSpeaker:
    def __init__(self, voices=("Microsoft Zira - English (United States)",)):
        self._voices = _FakeVoices([_FakeVoice(v) for v in voices])
        self.Rate = 0
        self.Voice = None
        self.spoken = []

    def GetVoices(self):
        return self._voices

    def Speak(self, text):
        self.spoken.append(text)


def _make_engine(monkeypatch, speaker=None, **cfg_kwargs):
    speaker = speaker or _FakeSpeaker()
    monkeypatch.setattr("win32com.client.Dispatch", lambda _: speaker)
    return TTSEngine(TTSConfig(**cfg_kwargs)), speaker


def test_sapi_speak_calls_speaker(monkeypatch):
    engine, speaker = _make_engine(monkeypatch)
    engine.speak("hello world")
    assert speaker.spoken == ["hello world"]


def test_sapi_voice_selected_by_substring(monkeypatch):
    engine, speaker = _make_engine(
        monkeypatch, voice="zira",
        speaker=_FakeSpeaker(voices=("Microsoft David", "Microsoft Zira - English")),
    )
    engine.speak("hi")
    assert speaker.Voice.desc == "Microsoft Zira - English"


def test_sapi_pitch_wraps_in_xml(monkeypatch):
    engine, speaker = _make_engine(monkeypatch, pitch=2)
    engine.speak("a & b")
    assert "<pitch absmiddle=\"2\">a &amp; b</pitch>" in speaker.spoken[0]


def test_sapi_available_false_when_no_sapi(monkeypatch):
    def boom(_):
        raise ImportError("pywin32 missing")

    monkeypatch.setattr("win32com.client.Dispatch", boom)
    engine = TTSEngine(TTSConfig())
    assert engine.available is False


def test_empty_text_does_nothing(monkeypatch):
    engine, speaker = _make_engine(monkeypatch)
    engine.speak("")
    assert speaker.spoken == []


def test_piper_unavailable_without_files():
    engine = TTSEngine(TTSConfig(backend="piper"))
    assert engine.available is False


def test_piper_speak_pipes_to_binary(monkeypatch, tmp_path):
    model = tmp_path / "voice.onnx"
    binary = tmp_path / "piper.exe"
    model.write_bytes(b"onnx")
    binary.write_bytes(b"elf")
    calls = {"subprocess": []}

    def fake_run(cmd, **kwargs):
        calls["subprocess"].append((cmd, kwargs["input"]))
        import types

        return types.SimpleNamespace(returncode=0, stderr=b"")

    def fake_play(path, _flags):
        calls["play"] = path

    monkeypatch.setattr("app.agent.tts.subprocess.run", fake_run)
    monkeypatch.setattr(winsound, "PlaySound", fake_play)
    engine = TTSEngine(TTSConfig(backend="piper", piper_binary=str(binary), piper_model=str(model)))
    assert engine.available is True
    engine.speak("hey jarvis")
    cmd, payload = calls["subprocess"][0]
    assert payload == b"hey jarvis"
    assert any("voice.onnx" in part for part in cmd)


def test_piper_run_failure_raises(monkeypatch, tmp_path):
    model = tmp_path / "voice.onnx"
    binary = tmp_path / "piper.exe"
    model.write_bytes(b"onnx")
    binary.write_bytes(b"elf")

    def fake_run(cmd, **kwargs):
        import types

        return types.SimpleNamespace(returncode=1, stderr=b"bad")

    monkeypatch.setattr("app.agent.tts.subprocess.run", fake_run)
    engine = TTSEngine(TTSConfig(backend="piper", piper_binary=str(binary), piper_model=str(model)))
    with pytest.raises(RuntimeError):
        engine.speak("boom")


def test_from_env_overrides_backend(monkeypatch):
    monkeypatch.setenv("JARVIS_TTS_BACKEND", "piper")
    assert TTSConfig.from_env().backend == "piper"
