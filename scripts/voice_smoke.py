"""Voice round-trip smoke test for the Phase 3 exit criteria.

Synthesizes a spoken phrase with the Windows SAPI voice (no mic needed),
transcribes it with Faster-Whisper, strips the wake word, runs the agent
(which may open the project folder), and speaks the reply. Reports
per-stage timing so the "< 2 s wake -> action" budget can be measured.

Usage:
    uv run python scripts/voice_smoke.py
    uv run python scripts/voice_smoke.py --phrase "jarvis open the project folder"
    uv run python scripts/voice_smoke.py --stt-model tiny --no-open
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import win32com.client

from app.agent.agent import Agent
from app.agent.llm import LLMClient, LLMConfig
from app.agent.recall.retriever import Recaller
from app.agent.recall.store import MemoryStore
from app.agent.stt import STTConfig, STTEngine
from app.agent.tools.tools import default_tools
from app.agent.tts import TTSConfig, TTSEngine
from app.agent.voice import VoiceConfig, VoiceLoop

DEFAULT_PHRASE = "jarvis open the project folder"


def synthesize(phrase: str, path: str) -> float:
    t0 = time.perf_counter()
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    stream.Open(path, 3)  # SSFMCreateForWrite
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    speaker.AudioOutputStream = stream
    speaker.Speak(phrase)
    stream.Close()
    return time.perf_counter() - t0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phrase",
        default=DEFAULT_PHRASE,
        help="phrase to synthesize and run (default: %(default)s)",
    )
    parser.add_argument(
        "--stt-model",
        default="tiny",
        help="faster-whisper size for the smoke (default: %(default)s)",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="LLM model (default: JARVIS_LLM_MODEL or llama3.2)",
    )
    parser.add_argument(
        "--llm-timeout",
        type=float,
        default=120.0,
        help="LLM request timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="do not let the agent actually open the folder",
    )
    args = parser.parse_args()

    llm = LLMClient(
        LLMConfig(model=args.llm_model or LLMConfig().model, timeout_s=args.llm_timeout)
    )
    print(f"[1/5] LLM available: {llm.available}")
    print(f"      ensure_model({llm.config.model}) -> {llm.ensure_model()}")

    stt = STTEngine(STTConfig(model_size=args.stt_model))
    if not stt.available:
        print(
            "STT model could not be loaded — run again once the download "
            "finishes, or check network.",
            file=sys.stderr,
        )
        return 1

    tts = TTSEngine(TTSConfig())
    print(f"[2/5] SAPI TTS available: {tts.available}")

    voice_cfg = VoiceConfig.from_env()
    print(f"      wake word: '{voice_cfg.wake_word}'")

    with tempfile.TemporaryDirectory() as tmp:
        wav = tmp + "\\utterance.wav"
        synth_s = synthesize(args.phrase, wav)
        print(f"[3/5] synthesized '{args.phrase}' -> {wav} ({synth_s:.2f}s)")

        t0 = time.perf_counter()
        text = stt.transcribe_file(wav)
        stt_s = time.perf_counter() - t0
        print(f"[4/5] STT: '{text}' ({stt_s:.2f}s)")

        command = VoiceLoop._strip_wake(text.strip(), voice_cfg.wake_word).strip()
        if not command:
            print(
                f"wake word '{voice_cfg.wake_word}' not heard in transcription",
                file=sys.stderr,
            )
            return 1
        print(f"      command (wake stripped): '{command}'")

        with MemoryStore("./jarvis.db") as store:
            registry = default_tools(store, Recaller(store))
            if args.no_open:
                from app.agent.tools import ToolRegistry

                keep = [t for t in registry._tools.values() if t.name != "open_path"]
                registry = ToolRegistry()
                for tool in keep:
                    registry.register(tool)
            agent = Agent(llm, store, recaller=Recaller(store), registry=registry)

            t0 = time.perf_counter()
            reply = agent.handle_turn(command)
            agent_s = time.perf_counter() - t0
            print(f"[5/5] agent: '{reply}' ({agent_s:.2f}s)")

            t0 = time.perf_counter()
            tts.say(reply)
            tts_s = time.perf_counter() - t0
            print(f"      TTS reply spoken ({tts_s:.2f}s)")

    total = stt_s + agent_s + tts_s
    print("-" * 50)
    print(f"voice round-trip (STT + agent + TTS): {total:.2f}s")
    print(f"  STT {stt_s:.2f}s | agent {agent_s:.2f}s | TTS {tts_s:.2f}s")
    print(
        "exit criteria: '< 2 s wake -> action'",
        "PASS" if stt_s + agent_s < 2.0 else "OVER BUDGET",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
