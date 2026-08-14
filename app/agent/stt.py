"""Speech-to-text via Faster-Whisper (local, per ADR-005 / 12_VOICE.md).

Model auto-downloads on first use (see 08_ASSETS.md). Loading is lazy so
the rest of the system imports cleanly before a model exists.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class STTConfig:
    model_size: str = "small"  # tiny | base | small | medium
    device: str = "cpu"  # cpu | cuda
    compute_type: str = "int8"
    language: str | None = "en"
    beam_size: int = 1
    vad_filter: bool = True

    @classmethod
    def from_env(cls) -> STTConfig:
        cfg = cls()
        cfg.model_size = os.getenv("JARVIS_STT_MODEL", cfg.model_size)
        cfg.language = os.getenv("JARVIS_STT_LANGUAGE", cfg.language or "en")
        return cfg


class STTEngine:
    """Wraps a lazily-loaded Faster-Whisper model."""

    def __init__(self, config: STTConfig | None = None):
        self.config = config or STTConfig()
        self._model = None
        self._load_error: str | None = None

    def _load(self):
        if self._model is None:
            if self._load_error:
                raise RuntimeError(self._load_error)
            try:
                import faster_whisper

                self._model = faster_whisper.WhisperModel(
                    self.config.model_size,
                    device=self.config.device,
                    compute_type=self.config.compute_type,
                )
            except Exception as exc:
                self._load_error = f"failed to load whisper model: {exc}"
                raise RuntimeError(self._load_error)
        return self._model

    @property
    def available(self) -> bool:
        try:
            self._load()
            return True
        except Exception as exc:
            logger.warning("STT unavailable: %s", exc)
            return False

    def transcribe(self, audio, sample_rate: int = 16000) -> str:
        """Transcribe raw float32 mono samples (16 kHz by default)."""
        model = self._load()
        segments, _info = model.transcribe(
            audio,
            language=self.config.language,
            beam_size=self.config.beam_size,
            vad_filter=self.config.vad_filter,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def transcribe_file(self, path: str) -> str:
        """Transcribe an audio file (wav/mp3/etc. — anything FFmpeg reads)."""
        model = self._load()
        segments, _info = model.transcribe(
            str(path),
            language=self.config.language,
            beam_size=self.config.beam_size,
            vad_filter=self.config.vad_filter,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
