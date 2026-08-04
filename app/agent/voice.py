"""Voice loop: wake word -> STT -> agent -> TTS.

Per 12_VOICE.md: always-on listening that only triggers on the wake keyword
("jarvis"), one utterance at a time, local-only, never blocks the gesture
loop (run in its own thread). The agent replies are also recorded as
episodes, so the transcript is available via Agent.transcript().
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    wake_word: str = "jarvis"
    wake_mode: str = "keyword"     # keyword | push_to_talk | off
    max_seconds: float = 8.0
    min_rms: float = 0.005

    @classmethod
    def from_env(cls) -> "VoiceConfig":
        cfg = cls()
        cfg.wake_word = os.getenv("JARVIS_WAKE_WORD", cfg.wake_word)
        cfg.wake_mode = os.getenv("JARVIS_WAKE_MODE", cfg.wake_mode)
        return cfg


class VoiceLoop:
    def __init__(self, agent, stt, tts, mic=None, config: VoiceConfig | None = None,
                 on_command: Optional[Callable[[str], Optional[str]]] = None):
        self.agent = agent
        self.stt = stt
        self.tts = tts
        self.mic = mic
        self.config = config or VoiceConfig()
        # Optional mode-switch hook: given the wake-stripped command, return a
        # reply to speak (command handled, agent skipped) or None (not a mode
        # command -> the normal agent turn runs). Wired by the app to the mode
        # machine via app/control/mode_voice.py.
        self.on_command = on_command
        if self.mic is None:
            from .audio import MicInput

            self.mic = MicInput()

    @staticmethod
    def _strip_wake(text: str, wake_word: str) -> str:
        low = text.lower()
        wl = wake_word.lower()
        idx = low.find(wl)
        if idx == -1:
            return text
        return text[idx + len(wl):].lstrip(" ,.!-:;")

    def run_once(self, trigger: str | None = None) -> dict | None:
        """One full voice turn. Returns None when not a command.

        Captures a single utterance and transcribes it once. In ``keyword``
        mode the wake word must appear in the text and is stripped before the
        agent runs (matches the exit criteria "Jarvis, open X"). ``trigger``
        enables push-to-talk and skips the wake check.
        """
        cfg = self.config
        samples = self.mic.record_until_silence(max_seconds=cfg.max_seconds)
        if self.mic.rms(samples) < cfg.min_rms:
            return None

        raw = self.stt.transcribe(samples).strip()
        if not raw:
            return None

        if trigger is None and cfg.wake_mode == "keyword":
            if cfg.wake_word.lower() not in raw.lower():
                return None
            command = self._strip_wake(raw, cfg.wake_word).strip()
        else:
            command = raw
        if not command:
            return None

        # Mode-switch commands ("chat mode", "transfer mode", ...) short-circuit
        # the agent: the on_command hook switches the mode machine and returns
        # a confirmation phrase for the TTS.
        if self.on_command is not None:
            reply = self.on_command(command)
            if reply is not None:
                self.tts.say(reply)
                return {
                    "command": command,
                    "reply": reply,
                    "transcript": self.agent.transcript(),
                    "mode_change": True,
                }

        reply = self.agent.handle_turn(command)
        self.tts.say(reply)
        return {
            "command": command,
            "reply": reply,
            "transcript": self.agent.transcript(),
        }

    def run(self, stop_event: threading.Event | None = None, interval: float = 0.2) -> None:
        """Infinite loop; pass a threading.Event to stop."""
        while not (stop_event and stop_event.is_set()):
            try:
                result = self.run_once()
            except Exception as exc:
                logger.warning("voice turn failed: %s", exc)
                result = None
            if result:
                logger.info("VOICE >> %s | << %s", result["command"], result["reply"])
            if stop_event is not None:
                stop_event.wait(interval)
            else:
                time.sleep(interval)
