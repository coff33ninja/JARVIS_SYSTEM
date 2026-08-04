# 10 — Performance Budget

Target end-to-end: **< 80 ms gesture → action**, tracked at p95. Budget table is the contract; every layer gets measured (`tests/perf/`).

## Per-layer budget (single frame, desktop webcam @ 640x480)

| Layer | Budget (ms) | Notes |
|---|---|---|
| Camera capture | 5 | use pre-allocated buffers, avoid resizing |
| MediaPipe Hands inference | 10–15 | CPU; GPU path optional later |
| Gesture logic + smoothing | 2 | 1-Euro filter is cheap |
| Control dispatch (mouse/click) | 3 | direct Win32 / pynput |
| HUD emit (JSON over WebSocket) | 3 | fire-and-forget, non-blocking |
| **Total control path** | **~25** | comfortably under 80 ms |
| Voice wake detection (always-on) | 5–15 | separate thread, poll-based |
| STT (Phase 3, on utterance) | 100–500 | async; user waits for this, not budgeted in gesture path |
| LLM round-trip (Phase 3) | 1 000–10 000 | async + streaming; shown as "thinking" on HUD |
| LocalSend transfer start (Phase 4) | < 50 after gesture | handshake + dialog |

## Budgets as gates

- **p95 gesture→action < 80 ms** — hard gate, checked in CI perf tests.
- **Tracking FPS ≥ 30** (60 ideal) — if inference exceeds budget, drop to a smaller input frame or enable GPU delegate before touching smoothing.
- **HUD render ≥ 30 FPS** — the HUD window must not block the core loop.

## Threading model

```
Main thread:   camera → tracker → gestures → control dispatch
HUD thread:    WebSocket server emitting events (non-blocking)
Voice thread:  wake word + STT (queued)
Agent thread:  LLM calls (async, streamed; cancelable)
Transfer thread: LocalSend triggers + status callbacks
```

No inference on the HUD/agent threads; keep the camera loop hot.

## Measuring

- `scripts/profile_layers.py` — per-layer timer, prints p50/p95 table (added Phase 1).
- Soak: 1 h @ 30 FPS, no memory growth > 10%, no frame drops after warmup.
- Record baseline numbers into `docs/PERF_BASELINE.md` (created on first run) so regressions are visible in git history.

## Degradation ladder (keep 80 ms goal even when weak)

1. Full quality: 640x480, 60 FPS target.
2. Reduce capture resolution to 480x360 (keeps > 80 ms easily).
3. Enable GPU delegate for MediaPipe.
4. Skip face/pose trackers (hands only).
5. Reduce HUD update rate (30 → 15 FPS) — HUD is cosmetic, control is not.
