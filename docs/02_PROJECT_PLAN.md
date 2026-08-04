# 02 — Project Plan

Roadmap for the JARVIS-style multi-device gesture + LLM system. Each phase is a thin, shippable slice (build vertical, not horizontal). Phases 1–4 are the critical path; 5–6 are polish/advanced.

## Phase 1 — Foundation (MVP: "I can move the cursor")

**Goal:** A working proof-of-life: webcam hand tracking → virtual mouse → minimal transparent overlay.

- [ ] Install MediaPipe Tasks (`uv add mediapipe`), verify webcam Hand Landmarker pipeline
- [ ] Index-finger cursor control (finger tip → screen coordinates) with 1-Euro smoothing
- [ ] Pinch = click (left click); two-finger pinch = right click
- [ ] Fist = drag; index + middle extended = scroll
- [ ] Simple transparent overlay window showing hand skeleton + reticle
- [ ] **Exit criteria:** reliably move cursor and click for 5+ minutes without tracking loss

**Head start:** `ArdaGral06/hand-gesture-pc-control`, `songs66/AirGestureMouse`, `Sid-V5/GestureHud`.

## Phase 2 — Solid Control

**Goal:** A usable, low-latency control layer that doesn't fight the user.

- [ ] Full gesture set (see gesture vocabulary doc)
- [ ] Multi-monitor awareness: cursor maps to correct screen; "point at a screen zone"
- [ ] Mode system: Idle / Control / Chat / Transfer / Presentation
- [ ] Gesture confidence thresholds + debounce (avoid accidental triggers)
- [ ] On-screen virtual keyboard toggle
- [ ] Media & volume control (play/pause, next, mute)
- [ ] Calibration UI: camera position, sensitivity, per-monitor layout
- [ ] **Exit criteria:** < 80 ms gesture→action latency; zero misfires in a 10-minute session

**Head start:** `oleg-putseiko/gesture-control` (plugin architecture), `Ns81000/Vision-Mouse` (offline exe, hotkey toggle).

## Phase 3 — Intelligence (LLM brain)

**Goal:** "Jarvis" can hear you, think, and act.

- [ ] Local LLM via Ollama (or LM Studio) exposed as OpenAI-compatible endpoint
- [ ] Voice input: Faster-Whisper STT
- [ ] Voice output: Piper / Coqui TTS (JARVIS voice)
- [ ] Simple tool-using agent: open apps, switch windows, web search
- [ ] Context awareness: current focused window, recent gestures, connected devices
- [ ] Long-term recall memory: SQLite + FTS5 facts/episodes store (`app/agent/recall/`, see 15_RECALL_MEMORY.md)
- [ ] Semantic recall via Ollama embeddings (optional; keyword fallback when offline)
- [ ] Context builder: compose recent history + recalled memories into LLM prompts (`app/agent/context.py`)
- [ ] Overlay chat bubbles / transcript panel
- [ ] **Exit criteria:** say "Jarvis, open the project folder" and it opens; voice round-trip < 2 s

**Head start:** `OpenInterpreter/open-interpreter`, `continuedev/continue`, `aider`.

## Phase 4 — Throw / Catch Transfer

**Goal:** Content moves between tablet ↔ PC with gestures.

- [ ] Install LocalSend on PC + tablet; verify normal send/receive
- [ ] Detect reliable throw gesture on PC (fist → open hand with forward velocity, or flick)
- [ ] Trigger LocalSend push/pull of selected content via API/CLI/automation
- [ ] "Catch" gesture on PC to accept incoming
- [ ] HUD visual feedback: flying file icon, progress, success animation
- [ ] Bidirectional + multi-device (PC → tablet, tablet → PC, PC ↔ PC)
- [ ] Optional LLM confirmation voice: "Received the photo from your tablet."
- [ ] **Exit criteria:** select file on tablet → throw gesture → file lands on PC desktop

**Head start:** `MAliffadlan/magic_file_transfer`, `sachinlodhi/gesture_drop`, `localsend/localsend`.

## Phase 5 — Polish & Magic

- [ ] HUD refinements: holographic styling, glassmorphism, particle effects
- [ ] "What am I pointing at" — screen capture + vision-language model summarization
- [ ] Context-aware suggestions from the LLM
- [ ] Multi-device robustness (device discovery, reconnects)
- [ ] JARVIS personality / voice polish
- [ ] Privacy controls: camera kill switch, local-only mode

## Phase 6 — Advanced

- [ ] Gaze estimation (Face Landmarker) — knows which monitor you're looking at
- [ ] Dual-hand interactions (both hands tracked, left = modifier)
- [ ] Tablet-side companion gesture app
- [ ] Plugin system for third-party actions
- [ ] Optional Home Assistant / smart-home integration
- [ ] Multi-user profiles

## Key Principles Enforced At Every Phase

| Principle | How it's enforced |
|---|---|
| Local-first, private by default | All inference local; no data leaves LAN unless opt-in |
| Low latency (< 50–80 ms) | Smoothing filters, native input APIs, no heavy cloud hops on control path |
| Graceful degradation | Control works if LLM/tablet offline; modes degrade gracefully |
| Configurable | Every gesture + sensitivity value in a config file / calibration UI |
| Cinematic but useful | HUD effects never block daily usability |
