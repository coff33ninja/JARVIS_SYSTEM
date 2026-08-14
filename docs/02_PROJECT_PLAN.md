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

- [x] Full gesture set (circle / index-trace attention added in `app/perception/pipeline.py::_circle`; grab/throw/catch are Phase 4)
- [x] Thumbs up/down: confirm / reject in Chat
- [x] Swipe (lateral point sweep): Alt+Tab next/prev window in Control
- [x] On-screen virtual keyboard toggle (F4 -> Windows osk.exe)
- [x] Multi-monitor awareness: cursor maps to correct screen; "point at a screen zone"
- [x] Media & volume control (F5 play/pause, F6 next, F7 previous, F8 mute, F9/F10 volume)
- [x] HUD overlay: skeleton, reticle, mode/fps/gesture status, monitor-layout map
- [x] FPS/stability: throttled HUD broadcasts (skeleton/status), hand-loss grace period
- [x] Two-hand detection + spread gesture: toggles Control ↔ Transfer mode
- [x] Two-hand pinch-apart zoom: both hands pinch, palms apart = Ctrl++ / together = Ctrl+- (Control, Transfer); 1 tick per `control.two_hand_zoom_threshold` of accumulated palm-center movement, re-arms on release/hand-loss
- [x] Open palm actions: catch (Transfer), release (Chat)
- [x] Presentation mode (F3): point = laser cursor, V-sign/swipe = PageUp/PageDown slides
- [x] Chat mode wiring (voice trigger) + calibration UI — voice→mode router (`app/control/mode_voice.py`) wired into `VoiceLoop.on_command`; end-to-end Idle→wake→Control→voice("chat mode")→Chat→voice→Control flow verified in `tests/test_chat_wiring.py`
- [x] **Exit criterion (latency):** < 80 ms gesture→action latency — measured by `scripts/bench_latency.py` (`uv run python scripts/bench_latency.py --paced`); ~67 ms estimated / ~63 ms paced at defaults, leaving ~13 ms headroom; `tests/test_latency.py` guards it in CI
- [ ] **Spatial mapping (camera → screen zones):** replace fixed-gain cursor mapping with a fitted projective homography (camera frame ↔ virtual desktop, 4-point, DLT, stored in config); add `zone_for()` named regions (per-monitor, left/right/center/edge) and an "active monitor" target so the cursor maps relative to one monitor's rect. See 13_MULTIMONITOR.md.
- [ ] **Auto-calibration ("spatial awareness"):** guided 4-corner pinch calibration (HUD reticle marks a corner, user pinches, system records index-tip) → fit + save homography; optional passive RANSAC refinement from observed hand→cursor pairs during normal use (off by default). Wired into the calibration UI (8766).
- [x] **Second-hand interaction (modifier hand):** three levels with no new detectors — (1) passive: secondary hand's lateral position selects the active monitor; (2) finger-count: 1–5 extended fingers on the secondary hand = monitor 1–5 (5-monitor cap); (3) fist-held radial menu on the HUD (Modes / Screens / Zoom / Tune / Gestures) where the primary hand points to highlight, pinch confirms, open palm cancels. Gated on two-hand presence; never collides with primary-hand fist=drag or V-sign scroll. Guards: passive zone requires `zone_hold_ms` in the same zone before switching active monitor (anti-thrash); 5-finger select is distinct from spread because spread = *both* palms open, finger-count inspects only the secondary hand. Menu geometry and interaction choices grounded in `16_INTERACTION_RESEARCH.md` (pie ≤8 items / 2 layers, screen-anchored menu, fist-as-clutch). Menu is sticky once open (closes on confirm/cancel/timeout/hand loss, not fist release) and owns the frame while open. ADR-011.
- [ ] **Dynamic gesture bindings (HUD menu "Gestures" category):** gesture→action mapping moves to a data-driven registry (stable action IDs ↔ gesture conditions), editable live from the fist menu — toggle any gesture level on/off, rebind a gesture to another action, tune thresholds. Registry enforces uniqueness (one action per pose/combination, with an in-menu warning on collisions). This is what makes the setup "dynamic to a point": new gesture variations are bindings, not code. ADR-011. **Status:** in-session toggle is implemented — `ControlPipeline._dispatch` resolves through `GestureRegistry`, the Gestures rows flip actions on/off with a live checkmark, and registries deep-copy their seed so toggles never leak. Rebind-to-another-action and threshold tuning remain (rebind needs per-gesture edge re-arm; `attention`/`mode.transfer_toggle` dispatch outside `_dispatch` and are intentionally not listed).
- [ ] **Exit criterion (reliability):** zero misfires in a 10-minute session.
  Guards in place to be verified live: pinch/two-finger-pinch re-arm on gesture
  change (previously a pinch only fired once per hand-detection), rest-pose
  suppression (two open palms no longer also fire catch/release on a spread
  frame), plus the existing `hold_frames=2` debounce and lost-hand grace.

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
