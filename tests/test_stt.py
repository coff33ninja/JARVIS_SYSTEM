"""Tests for the STT engine (Faster-Whisper wrapper, no model download)."""

from __future__ import annotations

import numpy as np
import pytest

from app.agent.stt import STTConfig, STTEngine


class _Segment:
    def __init__(self, text):
        self.text = text


class _FakeModel:
    def __init__(self, texts):
        self.texts = texts
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))
        return ([_Segment(t) for t in self.texts], None)


class _FakeWhisper:
    def __init__(self, texts):
        self._model = _FakeModel(texts)

    def WhisperModel(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self._model


def _make_engine(monkeypatch, texts, **cfg_kwargs):
    fake = _FakeWhisper(texts)
    monkeypatch.setattr("faster_whisper.WhisperModel", fake.WhisperModel)
    return STTEngine(STTConfig(**cfg_kwargs)), fake


def test_transcribe_joins_segments(monkeypatch):
    engine, fake = _make_engine(monkeypatch, ["hello ", "world"])
    out = engine.transcribe(np.zeros(16000, dtype=np.float32))
    assert out == "hello world"
    assert fake._model.calls[0][1]["language"] == "en"


def test_transcribe_file_passes_path(monkeypatch):
    engine, fake = _make_engine(monkeypatch, ["ok"])
    out = engine.transcribe_file("C:/tmp/utterance.wav")
    assert out == "ok"
    assert fake._model.calls[0][0] == "C:/tmp/utterance.wav"


def test_available_caches_model(monkeypatch):
    engine, fake = _make_engine(monkeypatch, ["x"])
    assert engine.available is True
    assert engine.available is True
    assert engine._model is not None


def test_available_false_when_model_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("no network")

    monkeypatch.setattr("faster_whisper.WhisperModel", boom)
    engine = STTEngine(STTConfig())
    assert engine.available is False
    with pytest.raises(RuntimeError):
        engine.transcribe(np.zeros(100, dtype=np.float32))


def test_from_env_overrides_model(monkeypatch):
    monkeypatch.setenv("JARVIS_STT_MODEL", "tiny")
    cfg = STTConfig.from_env()
    assert cfg.model_size == "tiny"
