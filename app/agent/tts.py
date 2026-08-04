"""Text-to-speech (local, per ADR-005 / 12_VOICE.md).

Default backend is Windows SAPI (zero downloads, instant). Optional Piper
backend (en_US-amy-medium) used when configured. No audio leaves the device.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

BACKENDS = ("sapi", "piper")


@dataclass
class TTSConfig:
    backend: str = "sapi"              # sapi | piper
    voice: str = "en_US-amy-medium"    # piper voice id, or SAPI voice substring
    piper_binary: str = ""             # path to piper.exe
    piper_model: str = ""              # path to voice .onnx
    rate: int = 0                      # SAPI rate (-10..10), 0 = default
    pitch: int = 0                     # SAPI pitch semitones; 0 = off

    @classmethod
    def from_env(cls) -> "TTSConfig":
        cfg = cls()
        cfg.backend = os.getenv("JARVIS_TTS_BACKEND", cfg.backend)
        cfg.voice = os.getenv("JARVIS_TTS_VOICE", cfg.voice)
        cfg.piper_binary = os.getenv("JARVIS_PIPER_BINARY", cfg.piper_binary)
        cfg.piper_model = os.getenv("JARVIS_PIPER_MODEL", cfg.piper_model)
        return cfg


class TTSEngine:
    """Speaks text using the configured backend. Degrades gracefully."""

    def __init__(self, config: TTSConfig | None = None):
        self.config = config or TTSConfig()
        self._sapi = None
        if self.config.backend not in BACKENDS:
            raise ValueError(f"unknown TTS backend: {self.config.backend}")

    @property
    def available(self) -> bool:
        if self.config.backend == "piper":
            ok = bool(self.config.piper_binary and self.config.piper_model)
            ok = ok and os.path.isfile(self.config.piper_binary)
            ok = ok and os.path.isfile(self.config.piper_model)
            if not ok:
                logger.warning("Piper TTS unavailable: set JARVIS_PIPER_BINARY and JARVIS_PIPER_MODEL")
            return ok
        try:
            self._speaker()
            return True
        except Exception as exc:
            logger.warning("SAPI TTS unavailable: %s", exc)
            return False

    def _speaker(self):
        if self._sapi is None:
            import win32com.client

            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            try:
                speaker.Rate = self.config.rate
            except Exception:
                pass
            self._select_voice(speaker)
            self._sapi = speaker
        return self._sapi

    def _select_voice(self, speaker):
        try:
            want = self.config.voice.lower()
            voices = speaker.GetVoices()
            for i in range(voices.Count):
                desc = voices.Item(i).GetDescription().lower()
                if want and want in desc:
                    speaker.Voice = voices.Item(i)
                    return
        except Exception as exc:
            logger.debug("voice selection skipped: %s", exc)

    def speak(self, text: str) -> None:
        if not text:
            return
        if self.config.backend == "piper":
            self._speak_piper(text)
        else:
            self._speak_sapi(text)

    def _speak_sapi(self, text: str) -> None:
        speaker = self._speaker()
        if self.config.pitch:
            payload = f'<pitch absmiddle="{int(self.config.pitch)}">{escape(text)}</pitch>'
        else:
            payload = text
        speaker.Speak(payload)

    def _speak_piper(self, text: str) -> None:
        import winsound

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            proc = subprocess.run(
                [self.config.piper_binary, "--model", self.config.piper_model, "--output_file", tmp_path],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"piper failed ({proc.returncode}): {proc.stderr.decode(errors='replace')}")
            winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def say(self, text: str) -> None:
        """Async-friendly alias: catches failures so callers never crash."""
        try:
            if self.available:
                self.speak(text)
        except Exception as exc:
            logger.warning("TTS failed: %s", exc)
