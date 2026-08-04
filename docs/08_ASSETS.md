# 08 — Asset / Model Manifest

Every model, binary, and data asset the system needs. Store under `models/`. All are open-source/local unless marked cloud.

## Vision (MediaPipe Tasks) — downloaded from Google AI Edge / MediaPipe Studio

| Asset | Used by | Typical size | Source |
|---|---|---|---|
| Hand Landmarker (`.task`) | hand_tracker.py | ~10 MB | https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker |
| Gesture Recognizer (`.task`) | gesture classifier | ~10–30 MB | https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer |
| Pose Landmarker (`.task`) | optional pose_tracker.py | ~30 MB | https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker |
| Face Landmarker (`.task`) | optional gaze.py | ~10 MB | https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker |

> Model files come from the official model bundle zips linked on each solution page. Add checksums after first download (record sha256 in this table).

## Voice

| Asset | Used by | Size | Source |
|---|---|---|---|
| Whisper model (e.g. `small`/`base` multilingual) | stt.py (Faster-Whisper) | 150 MB–500 MB | Auto-downloaded by faster-whisper (HF Hub) |
| Piper TTS voice (e.g. `en_US-amy-medium`) | tts.py | ~60 MB | https://github.com/rhasspy/piper/releases |
| Wake word model (e.g. openWakeWord `hey jarvis`) | voice wake detector | ~10 MB | https://github.com/dscripka/openWakeWord |

## Transfer

| Asset | Used by | Source |
|---|---|---|
| LocalSend app (PC + tablet) | transfer layer | https://localsend.org |

## Local LLM (Phase 3)

| Asset | Size | Notes |
|---|---|---|
| Ollama runtime | ~1 GB | https://ollama.com |
| Llama 3.x / Qwen / Phi chat model (7–8B quantized) | ~4–5 GB | `ollama pull llama3.1:8b` (or Qwen3 / Phi-4) |

## Optional / Stretch

| Asset | Notes |
|---|---|
| LLaVA or Qwen-VL (vision-language) | "what am I pointing at" — large; GPU recommended |
| YAMNet (AudioSet classifier) | MediaPipe Audio Classifier model (music-vs-speech, sound events) |
| Coqui TTS models | Alternative to Piper (higher quality, heavier) |

## Management rules

1. Never commit model binaries to git — add `models/` to `.gitignore`.
2. Record sha256 + download date in this table when adding an asset.
3. Keep a `models/README.md` listing what's installed and how to fetch it.
