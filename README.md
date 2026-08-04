# JARVIS SYSTEM

A local-first, Iron-Man/JARVIS-style computer control system built on **MediaPipe** (vision), a transparent **multi-monitor HUD**, an **LLM agent** (brain), and **gesture-based cross-device file transfer** ("throw / catch").

This repo was scaffolded from a research conversation. Everything below is distilled from that chat into executable planning docs.

---

## The Vision

A system that:

- Overlays a smart HUD across your PC monitors
- Uses a webcam + MediaPipe to continuously track your hands, pose, and optionally face/gaze
- Lets you control the computer, interact with content, and talk to an intelligent agent purely through **gestures + voice**
- Seamlessly moves files, screenshots, text, or other content between your tablet and PC using natural **throw / catch / drop** gestures
- Feels cinematic, responsive, and private (local-first by default)

## Six Layers

| Layer | Purpose | Tech |
|---|---|---|
| A. Perception | Hand / pose / face / gaze tracking | MediaPipe Tasks (Hands, Gesture, Pose, Face) |
| B. Interaction & Control | Virtual mouse, keyboard, window/media control, modes | PyAutoGUI / pynput / Win32 |
| C. HUD / Overlay | Transparent always-on-top UI across monitors | Electron / Tauri or Python (PyQt / Dear PyGui) + web frontend |
| D. Intelligence | LLM agent, voice in/out, tool calling | Ollama / LM Studio + Faster-Whisper + Piper / Coqui TTS |
| E. Cross-Device Transfer | Throw / catch files between tablet ↔ PC | LocalSend (primary) + custom trigger |
| F. System & Infrastructure | Device discovery, calibration, privacy, logging | mDNS, WebSocket/HTTP, local network only |

## Documentation

| File | Contents |
|---|---|
| [docs/01_REFERENCES.md](docs/01_REFERENCES.md) | Every link/reference from the research chat, categorized (+ provenance) |
| [docs/02_PROJECT_PLAN.md](docs/02_PROJECT_PLAN.md) | Phased development roadmap (6 phases) |
| [docs/03_ARCHITECTURE.md](docs/03_ARCHITECTURE.md) | Tech stack decision + proposed folder structure |
| [docs/04_GESTURE_VOCABULARY.md](docs/04_GESTURE_VOCABULARY.md) | Gesture definitions, modes, throw/catch semantics, calibration procedure |
| [docs/05_FEATURE_BACKLOG.md](docs/05_FEATURE_BACKLOG.md) | Prioritized MVP + backlog features |
| [docs/06_DECISIONS.md](docs/06_DECISIONS.md) | Architecture Decision Records (why LocalSend, Python, Ollama, etc.) |
| [docs/07_SETUP.md](docs/07_SETUP.md) | Environment setup guide (uv + `pyproject.toml`, cache bypass) |
| [docs/08_ASSETS.md](docs/08_ASSETS.md) | Model / asset manifest (MediaPipe tasks, Whisper, TTS, LLM) |
| [docs/09_TESTING.md](docs/09_TESTING.md) | Test strategy (unit → integration → e2e → perf) |
| [docs/10_PERFORMANCE.md](docs/10_PERFORMANCE.md) | Per-layer latency budget + degradation ladder |
| [docs/11_PRIVACY.md](docs/11_PRIVACY.md) | Data inventory, threats, mitigations, cloud opt-in policy |
| [docs/12_VOICE.md](docs/12_VOICE.md) | Voice subsystem spec (wake word, STT, TTS, grammar) |
| [docs/13_MULTIMONITOR.md](docs/13_MULTIMONITOR.md) | Multi-monitor zone math + mixed-DPI handling |
| [docs/14_STARTER_COMBO.md](docs/14_STARTER_COMBO.md) | Which existing repos to borrow vs. build from scratch |
| [docs/15_RECALL_MEMORY.md](docs/15_RECALL_MEMORY.md) | Agent long-term memory: SQLite + FTS5 + optional Ollama embeddings, context builder |
| [docs/16_AGENT.md](docs/16_AGENT.md) | Phase 3 agent: LLM client, tool registry, agent loop, graceful degradation |

## Provenance

This project was scaffolded from a research conversation originally produced in a Grok chat titled *"MediaPipe Self-Hosted Edge Projects"*, pasted into this repo for dissection and planning. See [docs/01_REFERENCES.md](docs/01_REFERENCES.md) for the full catalog.

## Key Principles

- **Local-first and private by default** — no data leaves the LAN unless you opt in
- **Low latency** — target < 50–80 ms for gesture feedback
- **Graceful degradation** — still works if LLM or tablet is offline
- **Highly configurable** — gestures, sensitivity, monitor layout
- **Cinematic but useful** — holographic feel without sacrificing daily usability

## Getting Started

Phase 1 (hand tracking → virtual mouse → overlay) is implemented. Phase 2 additions (thumbs up/down in Chat, Alt+Tab swipe, on-screen keyboard toggle, media/volume hotkeys, multi-monitor cursor mapping, two-hand spread → Transfer mode) are in place and tested. Set up per `docs/07_SETUP.md`, then:

```sh
uv run python scripts/smoke_test_hands.py     # verify webcam + MediaPipe hand tracking
uv run python scripts/jarvis_control.py       # run the Phase 1 control loop (--no-hud to disable overlay)
uv run pytest -q                               # 242 tests
```

Controls: pinch = click, two-finger pinch = right click, fist = drag, V-sign = scroll, swipe = next/prev window, two-hand spread = Transfer mode (open palm = catch), F2 = idle/control toggle, F3 = presentation mode (V-sign/swipe = slide nav), F4 = on-screen keyboard, F5–F10 = media play/pause, next/prev, mute, volume down/up.

The HUD overlay (`hud/index.html`, served at the websocket port) draws the hand skeleton, cursor reticle, current mode/fps/gesture, and a monitor-layout map; skeleton/status broadcasts are throttled so the webcam loop stays fast.

Phase 2+ (see `docs/02_PROJECT_PLAN.md`): remaining full gesture set, mode system refinements. Calibration UI is live: with the HUD running, open `http://127.0.0.1:8766/` to edit sensitivity/control values (live-applied) and check the monitor layout.
