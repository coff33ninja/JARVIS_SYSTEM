# 05 — Feature Backlog

Prioritized list. **P0 = MVP** (must ship before calling the project "usable"), **P1 = soon after**, **P2 = backlog / stretch**.

## P0 — MVP (Phase 1–2)

- [ ] Webcam hand tracking (MediaPipe Hands) with smoothing
- [ ] Virtual mouse: cursor, left/right click, drag, scroll
- [ ] On-screen virtual keyboard
- [ ] Mode system (Idle / Control / Chat / Transfer / Presentation)
- [ ] Transparent multi-monitor HUD (skeleton + reticle + status)
- [ ] Calibration UI (camera, sensitivity, monitor layout)
- [ ] Config file with all tunable parameters
- [ ] Misfire prevention (confidence + hold + debounce)

## P1 — Intelligence & Transfer (Phase 3–4)

- [ ] Local LLM agent (Ollama) with tool calling
- [ ] Voice input (Faster-Whisper) + TTS (Piper/Coqui)
- [ ] Agent tools: open apps, switch windows, web search, media control
- [ ] Focused-window context awareness
- [ ] HUD chat bubbles / transcript
- [ ] LocalSend integration
- [ ] Throw / catch / drop gesture detection with direction sensing
- [ ] Transfer visual effects (flying icon, progress, success)
- [ ] Bidirectional tablet ↔ PC transfer
- [ ] Device discovery (mDNS)
- [ ] LLM voice confirmation of transfers

## P2 — Polish & Advanced (Phase 5–6)

- [ ] Holographic HUD polish (Three.js particles, glassmorphism)
- [ ] "What am I pointing at" — screen capture + vision model (LLaVA / Qwen-VL / GPT-4o)
- [ ] Gaze estimation (Face Landmarker) for monitor focus
- [ ] Dual-hand interactions (left hand = modifier)
- [ ] Tablet-side companion gesture app
- [ ] Plugin system for third-party actions
- [ ] Home Assistant / smart-home integration
- [ ] Multi-user profiles
- [ ] JARVIS personality + custom voice
- [ ] Privacy controls: camera kill switch, local-only mode
- [ ] Logging, crash recovery, remote diagnostics
- [ ] Graceful degradation matrix (LLM offline, tablet offline, no webcam)

## Non-Functional Requirements

| Requirement | Target |
|---|---|
| Gesture → action latency | < 50–80 ms |
| Tracking FPS | 30+ (60 ideal) |
| Privacy | 100% local by default; cloud opt-in only |
| Configurability | All gestures + sensitivities configurable |
| Platforms | Windows first; tablet = Android/iOS via LocalSend |
