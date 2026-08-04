# 03 — Architecture

## Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Vision | **MediaPipe Tasks** (Hands + Gesture Recognizer primary; Pose + Face Landmarker optional) | Real-time on-device, 21 hand landmarks, cross-platform, Apache-2.0 |
| Desktop Control | **PyAutoGUI / pynput / Win32** | Proven input injection on Windows |
| Overlay / HUD | **Python core + web frontend in transparent Chromium** (Electron/Tauri), or PyQt/Dear PyGui for pure-Python | Multi-monitor transparency + rich web visuals (Three.js) |
| LLM & Agent | **Ollama** (local) with OpenAI-compatible API; agent framework of choice (Open Interpreter/Continue or hand-rolled tool loop) | Easiest local setup, standard API |
| Voice | **Faster-Whisper** (STT) + **Piper / Coqui TTS** | Local, low-latency |
| File Transfer | **LocalSend** (primary) + custom trigger API | Mature, encrypted, cross-platform, LAN-only |
| Networking | mDNS device discovery + WebSocket/HTTP | Local network only |
| Language | **Python** (core/perception/agent) + **TypeScript/JS** (HUD) | Python dominates MediaPipe + agents; web for HUD |
| Config | JSON/YAML config + calibration UI | Every gesture/sensitivity tunable |

## High-Level Data Flow

```
Webcam → MediaPipe (Hands + Face + Pose)
                 ↓
        Perception layer
   hand positions, velocity, gesture labels, pointing dir, confidence
                 ↓
        Interaction & Control layer        ←── smoothing (1-Euro)
   virtual mouse/keyboard, window/media, mode switching
                 ↓                          ↓
        HUD / Overlay (transparent, multi-monitor)
                 ↓                          ↓
        LLM Agent (voice in via STT) ──→ tools: mouse, keyboard,
   apps, search, screen+vision, transfer   Home Assistant, calendar
                 ↓
        Transfer layer (LocalSend)  ←── throw/catch gestures
   Tablet / other PCs
```

## Proposed Folder Structure

```
jarvis-system/
├── app/                      # Python core
│   ├── main.py               # entrypoint, event loop, orchestration
│   ├── config.py             # config load/save + defaults
│   ├── perception/
│   │   ├── camera.py         # webcam capture
│   │   ├── hand_tracker.py   # MediaPipe Hand Landmarker
│   │   ├── pose_tracker.py   # optional full-body
│   │   ├── gaze.py           # optional face/gaze
│   │   └── smoothing.py      # 1-Euro / EMA filters
│   ├── control/
│   │   ├── virtual_mouse.py  # cursor, click, drag, scroll
│   │   ├── virtual_keyboard.py
│   │   ├── window_manager.py # Win32 window/app control
│   │   ├── media_control.py  # volume/playback
│   │   └── modes.py          # Idle/Control/Chat/Transfer/Presentation
│   ├── hud/
│   │   ├── hud_server.py     # serves HUD to transparent browser window
│   │   └── events.py         # JSON events to HUD (skeleton, reticle, status)
│   ├── agent/
│   │   ├── llm.py            # OpenAI-compatible client (Ollama/LM Studio)
│   │   ├── stt.py            # Faster-Whisper (STTEngine)
│   │   ├── tts.py            # SAPI default / Piper (TTSEngine)
│   │   ├── audio.py          # mic capture + end-of-speech (MicInput)
│   │   ├── voice.py          # wake word → STT → agent → TTS (VoiceLoop)
│   │   ├── tools/            # mouse, keyboard, apps, search, transfer, screen
│   │   ├── recall/           # long-term memory: store, retriever, embedder (see 15_RECALL_MEMORY.md)
│   │   └── context.py        # focused window, gestures, devices + history/memories → prompt
│   ├── transfer/
│   │   ├── localsend_bridge.py  # trigger LocalSend push/pull
│   │   ├── discovery.py      # mDNS / device discovery
│   │   └── gestures_throw.py    # throw/catch/drop detectors
│   └── config/               # user calibration profiles
├── hud/                      # Web frontend (transparent browser window)
│   ├── index.html
│   ├── js/ (three.js scenes, reticle, particles, chat)
│   └── css/ (glassmorphism, HUD styling)
├── models/                   # downloaded/custom MediaPipe + voice models
├── scripts/                  # installer, calibration, dev helpers (ensure-uv.ps1)
├── tests/
├── pyproject.toml            # deps + [tool.uv] config (uv-managed, cache off C:)
├── uv.lock                   # pinned dependency tree (commit it)
└── README.md
```

## Core Design Decisions

1. **Local-first:** inference runs on-device; control path never touches the cloud. Cloud only optional for hard reasoning.
2. **Transparent HUD via web tech:** one HTML page spans multiple monitors in a borderless always-on-top Chromium window; Three.js handles holographic visuals.
3. **OpenAI-compatible LLM endpoint:** swap Ollama ↔ LM Studio ↔ cloud API with zero code change.
4. **LocalSend as transfer backbone:** avoid building crypto/transfer from scratch; wrap it with a trigger API + gesture detection.
5. **Mode machine:** every mode defines which gestures are active, preventing accidental actions.
6. **Graceful degradation:** if LLM or tablet is offline, control and HUD still function.
