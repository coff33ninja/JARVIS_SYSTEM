# 09 — Testing Strategy

Test pyramid adapted to a real-time gesture + agent system. Default tool: pytest. All latency-sensitive tests include timing assertions against the budget in `10_PERFORMANCE.md`.

## 1. Unit tests (fast, no webcam / no OS calls)

- **Gesture geometry:** given synthetic 21-landmark sets, assert gesture classification (pinch open/closed, fist curl, V-sign, throw flick velocity).
- **Smoothing:** 1-Euro filter on synthetic noisy trajectories — assert jitter reduction and bounded lag.
- **Config:** load/validate config files, bounds-check every calibration parameter.
- **Mode machine:** transition table tests — every (mode, gesture) pair yields expected action or rejection.
- **Threat of regression:** these run in CI on every change. Target < 2 s each.

## 2. Integration tests (real webcam, mock input)

- **Camera → landmarks:** run the tracker on N live frames; assert landmarks detected > threshold % of frames, FPS > target.
- **Virtual mouse mapping:** verify hand-frame → screen-coordinate mapping math against the multi-monitor layout (13_MULTIMONITOR.md) without injecting real clicks.
- **HUD protocol:** assert the JSON event schema the core emits matches the frontend contract.
- **Agent tool calls (Phase 3):** mock the LLM endpoint, assert tool dispatch (open app, search) hits the right handler.

## 3. End-to-end / manual acceptance

| Scenario | Pass criteria |
|---|---|
| Cursor follows index finger | 5 min continuous tracking, no drift > 2 cm on screen |
| Pinch clicks | 20/20 clicks land at the intended point |
| Misfire guard | 10 min normal typing/movement → 0 accidental actions |
| Multi-monitor | Cursor maps correctly on each monitor incl. mixed DPI |
| Throw/catch (Phase 4) | Select file on tablet → throw → file lands on PC (and reverse) |
| Voice loop (Phase 3) | "Jarvis, open X" → X opens; round-trip < 2 s |

## 4. Performance tests

- Per-layer timing capture (see 10_PERFORMANCE.md): camera, inference, smoothing, control dispatch, HUD emit.
- Latency gate in CI: fail if p95 exceeds the budget.
- Long-run soak: 1 h at 30 FPS, assert no memory growth > 10% and no frame drops after warmup.

## 4.5 Recall memory tests (Phase 3)

- `tests/test_recall_store.py` — persistence, FTS + LIKE fallback, updates/deletes, embeddings round-trip.
- `tests/test_recall_retriever.py` — keyword/semantic/hybrid ranking, graceful degradation when the embedder dies, index backfill.
- `tests/test_embedder.py` — client build/availability, single + batch embed, endpoint-down handling.
- `tests/test_context.py` — `build_context` composition and prompt formatting.

All run without a webcam, network, or Ollama (fake embedders, tmp SQLite). End-to-end check: `uv run python scripts/recall_smoke.py`.

## 5. Regression playbook

1. Reproduce the bug with a captured frame or recorded gesture (replay harness in `scripts/replay_frames.py`).
2. Write the failing test first (RED).
3. Fix (GREEN).
4. Run the full unit + integration suite + latency gate before merging.
5. Update `04_GESTURE_VOCABULARY.md` if a threshold changed.

## Test layout

```
tests/
├── unit/           # geometry, smoothing, config, modes
├── integration/    # tracker on live camera, mapping, HUD schema, agent dispatch
├── e2e/            # manual-ish scripted scenarios (opt-in, need webcam + display)
└── perf/           # latency gates, soak
```
