"""Tests for mic capture (sounddevice stubbed with a fake)."""

from __future__ import annotations

import numpy as np

from app.agent.audio import MicConfig, MicInput


class FakeSD:
    def __init__(self, blocks):
        self.blocks = list(blocks)
        self.records = []

    def rec(self, frames, samplerate, channels, dtype, device):
        self.records.append((frames, samplerate, channels, dtype, device))
        block = (
            self.blocks.pop(0) if self.blocks else np.zeros(frames, dtype=np.float32)
        )
        return block.astype(dtype)

    def wait(self):
        return 0


def _mic_with(monkeypatch, blocks, **cfg):
    mic = MicInput(MicConfig(silence_timeout_seconds=0.5, chunk_seconds=0.25, **cfg))
    fake = FakeSD(blocks)
    monkeypatch.setattr(mic, "_sd", lambda: fake)
    return mic, fake


def test_rms_of_silence_is_zero():
    assert MicInput.rms(np.zeros(10, dtype=np.float32)) == 0.0


def test_rms_of_loud_signal():
    assert MicInput.rms(np.full(10, 0.5, dtype=np.float32)) > 0.4


def test_record_until_silence_stops_after_quiet_tail(monkeypatch):
    loud = np.full(4000, 0.5, dtype=np.float32)  # 0.25 s speech
    quiet = np.zeros(4000, dtype=np.float32)  # 0.25 s silence
    mic, fake = _mic_with(monkeypatch, [loud, quiet, quiet])  # 2 quiet = 0.5 s >= 0.5 s
    out = mic.record_until_silence()
    assert len(fake.records) == 3  # loud + 2 quiet, stops once timeout reached
    assert out.size == 12000
    assert MicInput.rms(out) > 0.1


def test_record_until_silence_ignores_leading_silence(monkeypatch):
    quiet = np.zeros(4000, dtype=np.float32)
    loud = np.full(4000, 0.5, dtype=np.float32)
    mic, fake = _mic_with(monkeypatch, [quiet, loud])
    out = mic.record_until_silence()
    assert len(fake.records) == 4  # kept going past the silent opener
    assert out.size == 16000
    assert MicInput.rms(out) > 0


def test_record_hard_caps_at_max_seconds(monkeypatch):
    loud = np.full(4000, 0.5, dtype=np.float32)
    mic, fake = _mic_with(monkeypatch, [loud, loud, loud, loud], max_seconds=1.0)
    mic.record_until_silence()
    assert len(fake.records) == 4
