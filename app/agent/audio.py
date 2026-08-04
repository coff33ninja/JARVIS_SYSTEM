"""Microphone capture with end-of-speech (silence) detection.

Uses sounddevice for blocking block-wise recording. Wrappers keep the class
stubbable in tests (the voice loop never touches sounddevice directly).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MicConfig:
    sample_rate: int = 16000
    chunk_seconds: float = 0.25
    max_seconds: float = 8.0
    silence_timeout_seconds: float = 3.0
    silence_threshold: float = 0.01

    @classmethod
    def from_env(cls) -> "MicConfig":
        cfg = cls()
        cfg.sample_rate = int(os.getenv("JARVIS_MIC_RATE", cfg.sample_rate))
        return cfg


class MicInput:
    """Records raw float32 mono samples at 16 kHz."""

    def __init__(self, config: MicConfig | None = None, device=None):
        self.config = config or MicConfig()
        self.device = device

    def _sd(self):
        import sounddevice as sd

        return sd

    @staticmethod
    def rms(samples: np.ndarray) -> float:
        if samples is None or samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))

    def record(self, seconds: float) -> np.ndarray:
        sd = self._sd()
        frames = max(1, int(seconds * self.config.sample_rate))
        block = sd.rec(
            frames,
            samplerate=self.config.sample_rate,
            channels=1,
            dtype="float32",
            device=self.device,
        )
        sd.wait()
        return block.flatten()

    def record_until_silence(
        self,
        max_seconds: float | None = None,
        silence_timeout: float | None = None,
    ) -> np.ndarray:
        """Record one utterance; stop after `silence_timeout` of quiet.

        Ignores leading silence (keeps listening until speech starts) and
        hard-stops at `max_seconds`. Returns float32 samples (may be empty
        if nothing was ever spoken within the window).
        """
        max_seconds = max_seconds or self.config.max_seconds
        silence_timeout = silence_timeout or self.config.silence_timeout_seconds
        chunk = self.config.chunk_seconds
        sd = self._sd()
        frames = max(1, int(chunk * self.config.sample_rate))

        parts: list[np.ndarray] = []
        total = 0.0
        silent = 0.0
        heard = False
        while total < max_seconds:
            block = sd.rec(
                frames,
                samplerate=self.config.sample_rate,
                channels=1,
                dtype="float32",
                device=self.device,
            )
            sd.wait()
            block = block.flatten()
            parts.append(block)
            total += chunk
            if self.rms(block) >= self.config.silence_threshold:
                heard = True
                silent = 0.0
            elif heard:
                silent += chunk
                if silent >= silence_timeout:
                    break
        if not parts:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(parts)
