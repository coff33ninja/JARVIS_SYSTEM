# 12 — Voice Subsystem Spec

Voice makes the system feel like JARVIS. Layered so it can start text-only and add voice incrementally (Phase 3).

## Pipeline

```
Mic → Wake word detector → (keyword "Jarvis") → STT (Faster-Whisper)
                                                   ↓
                                     command text → agent (LLM)
                                                   ↓
                        TTS (Piper) → "Yes, sir." + HUD transcript
```

## Components

| Component | Default | Alternative | Notes |
|---|---|---|---|
| Wake word | openWakeWord (`hey jarvis`) | Picovoice Porcupine (cloud-free but licensing check), custom energy+VAD | Always-on, low CPU, runs on separate thread |
| STT | Faster-Whisper (`small` multilingual, `int8`) | `base` for speed, `medium` for accuracy; whisper.cpp | Local; model auto-downloads (see 08_ASSETS.md) |
| TTS | Piper (`en_US-amy-medium`) | Coqui TTS (higher quality/heavier), system `SAPI` voice | Local; low latency; supports pitch for a "Jarvis" feel |

## Behavior rules

- **Wake word gating:** STT/LLM only engages after wake. No audio leaves the device.
- **Command session:** after a wake, one utterance → one action. A 3 s end-of-speech timeout (VAD) finalizes the utterance.
- **HUD feedback:** always show "listening / processing / speaking" state; stream agent text to the HUD while TTS speaks.
- **Round-trip budget:** wake→action < 2 s locally (STT ~0.3 s, LLM streams first tokens ~1 s, TTS overlaps with text display). Treat voice as async — never block the gesture control loop.
- **Mic privacy:** auto-mute outside Chat/Command mode (T3 in 11_PRIVACY.md).
- **Cancel:** a gesture (open palm) or "Jarvis, stop" cancels the current utterance/action.
- **Personality:** TTS messages follow a short, dry, assistant tone; configurable via prompt template + TTS settings.

## Command grammar (start simple, expand later)

Natural-language, not rigid. The agent maps these to tools:

- "Open <app>" → app/window tool
- "Search for <q>" → web search tool
- "Volume up/down, mute" → media tool
- "Throw this to the tablet" → transfer tool (Phase 4)
- "What am I pointing at?" → screen+vision tool (Phase 5)
- "Switch to <mode>" → mode machine (`app/control/mode_voice.py` wired via `VoiceLoop.on_command`: "chat mode", "control mode", "idle", "transfer mode", "presentation mode"; agent skipped, confirmation spoken)

## Voice config

```
voice:
  wake_word: "hey jarvis"
  wake_model: models/openWakeWord/hey_jarvis.onnx
  stt_model: small
  stt_language: en
  tts_voice: en_US-amy-medium
  tts_pitch: +2
  auto_mute_outside_chat: true
  end_of_speech_timeout_ms: 3000
  roundtrip_budget_ms: 2000
```

## Verification (Phase 3 exit)

1. Wake word triggers only on keyword (test 10 negative phrases → 0 false wakes).
2. "Jarvis, open the project folder" opens the folder, HUD shows transcript, TTS responds — round-trip < 2 s.
3. Mic mutes automatically when leaving Chat mode.
