"""Exit-criteria latency tests: prove gesture->action stays under 80 ms.

These tests measure wall-clock, so the bounds are deliberately generous
(~100-1000x the observed values) to stay CI-safe on slow/loaded machines
while still catching a real regression that would blow the Phase 2 budget.
The precise numbers come from ``scripts/bench_latency.py``.
"""

from __future__ import annotations

import scripts.bench_latency as bl


def test_pipeline_step_overhead_tiny():
    """Per-step software cost (no tracker) must be a rounding error.

    Observed p95 ~0.03ms; a regression past 5ms would put the whole budget
    at risk once multiplied across hold_frames and the sensor cadence.
    """
    stats = bl.bench_pipeline_overhead(frames=200, warmup=20)
    assert stats["p95"] < 5.0, f"p95 step overhead {stats['p95']:.2f}ms"


def test_estimated_latency_under_exit_budget():
    """hold_frames x (sensor cadence capped frame time) must stay < 80ms.

    Defaults: 30fps sensor -> 33.3ms cadence, 25ms MediaPipe model, 2 hold
    frames. Estimated ~67ms, headroom ~13ms.
    """
    cfg = bl.AppConfig()
    overhead = bl.bench_pipeline_overhead(frames=200, warmup=20)
    capture_ms = 1000.0 / cfg.perception.fps
    per_frame_ms = max(capture_ms, 25.0) + overhead["p95"]
    estimated = cfg.control.hold_frames * per_frame_ms
    assert estimated < 80.0, f"estimated latency {estimated:.1f}ms >= 80ms"


def test_paced_gesture_to_action_under_exit_budget():
    """End-to-end point->pinch->click through a real cadence loop.

    Fast config (120fps cadence, 5ms simulated tracker) keeps the test under
    a second while exercising the full path: debounce, classify, dispatch.
    Observed ~15ms; anything >= 80ms is a real regression.
    """
    latency = bl.bench_paced_gesture(fps=120, hold_frames=2, tracker_ms=5.0, total=30)
    assert latency < 80.0, f"gesture->action latency {latency:.1f}ms >= 80ms"
