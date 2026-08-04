# 02 — Project Plan

Roadmap for the JARVIS-style multi-device gesture + LLM system. Each phase is a thin, shippable slice (build vertical, not horizontal). Phases 1–4 are the critical path; 5–6 are polish/advanced.

## Phase 1 — Foundation (MVP: "I can move the cursor")

**Goal:** A working proof-of-life: webcam hand tracking → virtual mouse → minimal transparent overlay.

- [x] Install MediaPipe Tasks (`uv add mediapipe`), verify webcam Hand Landmarker pipeline
- [x] Index-finger cursor control (finger tip → screen coordinates) with 1-Euro smoothing
- [x] Pinch = click (left click); two-finger pinch = right click
- [x] Fist = drag; index + middle extended = scroll
- [x] Simple transparent overlay window showing hand skeleton + reticle
- [x] **Exit criteria:** reliably move cursor and click for 5+ minutes without tracking loss

**Head start:** `ArdaGral06/hand-gesture-pc-control`, `songs66/AirGestureMouse`, `Sid-V5/GestureHud`.

## Phase 2 — Solid Control

**Goal:** A usable, low-latency control layer that doesn't fight the user.

- [ ] Full gesture set (see gesture vocabulary doc)
- [x] Thumbs up/down: confirm / reject in Chat
- [x] Swipe (lateral point sweep): Alt+Tab next/prev window in Control
- [x] On-screen virtual keyboard toggle (F4 -> Windows osk.exe)
- [x] Multi-monitor awareness: cursor maps to correct screen; "point at a screen zone"
- [x] Media & volume control (F5 play/pause, F6 next, F7 previous, F8 mute, F9/F10 volume)
- [x] HUD overlay: skeleton, reticle, mode/fps/gesture status, monitor-layout map
- [x] FPS/stability: throttled HUD broadcasts (skeleton/status), hand-loss grace period
- [x] Two-hand detection + spread gesture: toggles Control ↔ Transfer mode
- [x] Open palm actions: catch (Transfer), release (Chat)
- [x] Presentation mode (F3): point = laser cursor, V-sign/swipe = PageUp/PageDown slides
- [x] Chat mode wiring (voice trigger) + calibration UI
- [ ] **Exit criteria:** < 80 ms gesture→action latency; zero misfires in a 10-minute session

**Head start:** `oleg-putseiko/gesture-control` (plugin architecture), `Ns81000/Vision-Mouse` (offline exe, hotkey toggle).

## Phase 3 — Intelligence (LLM brain)

**Goal:** "Jarvis" can hear you, think, and act.

- [x] Local LLM via Ollama (or LM Studio) exposed as OpenAI-compatible endpoint (`app/agent/llm.py`)
- [x] Voice input: Faster-Whisper STT (`app/agent/stt.py` — `STTEngine`; model auto-downloads on first run, see 08_ASSETS.md)
- [x] Voice output: TTS (`app/agent/tts.py` — `TTSEngine`, Windows SAPI default, optional Piper voice)
- [x] Simple tool-using agent: open apps, switch windows, web search (`app/agent/agent.py` + `tools/`)
- [ ] Context awareness: current focused window (done), recent gestures, connected devices
- [x] Long-term recall memory: SQLite + FTS5 facts/episodes store (`app/agent/recall/`, see 15_RECALL_MEMORY.md)
- [x] Semantic recall via Ollama embeddings (optional; keyword fallback when offline)
- [x] Context builder: compose recent history + recalled memories into LLM prompts (`app/agent/context.py`)
- [x] Voice pipeline: mic capture → wake word → STT → agent → TTS (`app/agent/audio.py` + `app/agent/voice.py` — `VoiceLoop`)
- [ ] Overlay chat bubbles / transcript panel (data layer done via `Agent.transcript()`; HUD rendering comes with the overlay layer)
- [ ] **Exit criteria:** say "Jarvis, open the project folder" and it opens; voice round-trip < 2 s (needs a tool-capable LLM model + STT model download + mic)

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
