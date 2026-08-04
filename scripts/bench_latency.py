"""Gesture->action latency harness for the Phase 2 exit criterion (<80 ms).

docs/02_PROJECT_PLAN.md exit criteria:
    "< 80 ms gesture->action latency; zero misfires in a 10-minute session"

This script measures the part JARVIS fully owns -- the in-process pipeline
overhead (tracker-agnostic: classify -> smooth -> map -> dispatch) -- and
models the hardware-dependent part (webcam capture + MediaPipe inference)
with a configurable simulated tracker delay. It then estimates the real
gesture->action latency and prints a PASS/FAIL verdict.

Gesture->action latency model
-----------------------------
A gesture must persist ``hold_frames`` consecutive frames before it fires.
With a per-frame cost of ``frame_ms`` (capture + inference + pipeline), the
conservative latency from gesture onset is::

    latency_ms = hold_frames * frame_ms

where ``frame_ms = tracker_ms + pipeline_p95``. The harness keeps the frame
cadence at the configured ``perception.fps`` so the pacing matches the real
loop (app/main.py runs as fast as capture+inference allow).

Usage:
    uv run python scripts/bench_latency.py [--frames 200] [--warmup 20]
        [--tracker-ms 25] [--budget-ms 80] [--paced]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))
from conftest import pinch_hand, point_hand  # noqa: E402

from app.config import AppConfig  # noqa: E402
from app.control.modes import Mode, ModeMachine  # noqa: E402
from app.perception.hand_tracker import HandTrackingResult  # noqa: E402
from app.perception.mapping import CursorMapper, MappingConfig  # noqa: E402
from app.perception.pipeline import ControlPipeline  # noqa: E402

FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


class _NoopTracker:
    def __init__(self):
        self.result = HandTrackingResult(hands=[point_hand()],
                                         handedness=["Right"])

    def process(self, frame):  # noqa: ARG002 - frame unused by design
        return self.result

    def close(self):
        pass


class _SleepTracker(_NoopTracker):
    """Simulates capture+MediaPipe cost with a fixed per-frame delay."""

    def __init__(self, delay_ms: float):
        super().__init__()
        self._delay_s = delay_ms / 1000.0

    def process(self, frame):
        time.sleep(self._delay_s)
        return super().process(frame)


class _FakeMouse:
    def __init__(self):
        self.calls = []

    def move(self, x, y):
        self.calls.append(("move", x, y))

    def click(self, button="left", clicks=1):
        self.calls.append(("click", button, clicks))


def _pipeline(tracker) -> ControlPipeline:
    cfg = AppConfig()
    return ControlPipeline(
        config=cfg,
        tracker=tracker,
        mouse=_FakeMouse(),
        mapper=CursorMapper(MappingConfig(screen=(0, 0, 1000, 800))),
        modes=ModeMachine(Mode.CONTROL),
    )


def _stats(samples: list[float]) -> dict[str, float]:
    s = sorted(samples)
    n = len(s)
    pct = lambda p: s[min(n - 1, int(p * (n - 1)))]  # noqa: E731
    return {
        "min": s[0],
        "mean": sum(s) / n,
        "p50": pct(0.50),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "max": s[-1],
    }


def bench_pipeline_overhead(frames: int, warmup: int) -> dict[str, float]:
    """Per-step() cost with a no-op tracker: pure software overhead."""
    pipe = _pipeline(_NoopTracker())
    for _ in range(warmup):
        pipe.step(FRAME)
    times: list[float] = []
    for _ in range(frames):
        t0 = time.perf_counter_ns()
        pipe.step(FRAME)
        times.append((time.perf_counter_ns() - t0) / 1e6)
    return _stats(times)


def bench_paced_gesture(fps: int, hold_frames: int, tracker_ms: float,
                        total: int = 300) -> float:
    """Full loop-paced gesture->action latency (point -> pinch -> left click).

    Runs a real cadence loop (one step per frame slot) and times from the
    moment the first pinch frame is offered to the moment the click action
    fires. The gesture persists hold_frames frames, so the click lands on
    the hold_frames-th pinch frame.
    """
    pipe = _pipeline(_SleepTracker(tracker_ms))
    frame_period = 1.0 / fps

    # Steady point frames to settle gesture state, then switch to pinch.
    gesture_onset: float | None = None
    action_at: float | None = None
    pinch_left = 0
    pinch_frames = hold_frames + 1
    for i in range(total):
        frame_start = time.monotonic()
        is_pinch = i >= total - pinch_frames
        if is_pinch:
            if pinch_left == 0:
                gesture_onset = frame_start
            pinch_left += 1
            pipe.tracker.result = HandTrackingResult(
                hands=[pinch_hand()], handedness=["Right"])
            pipe.step(FRAME)
        else:
            pipe.step(FRAME)
        if any(c[0] == "click" for c in pipe.mouse.calls) and action_at is None:
            action_at = time.monotonic()
            break
        elapsed = time.monotonic() - frame_start
        if elapsed < frame_period:
            time.sleep(frame_period - elapsed)
    assert gesture_onset is not None and action_at is not None, \
        "pinch sequence never produced a click"
    return (action_at - gesture_onset) * 1000.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--tracker-ms", type=float, default=25.0,
                    help="model webcam capture + MediaPipe inference per frame")
    ap.add_argument("--budget-ms", type=float, default=80.0)
    ap.add_argument("--paced", action="store_true",
                    help="also run the loop-paced gesture->action measurement")
    args = ap.parse_args()

    cfg = AppConfig()
    overhead = bench_pipeline_overhead(args.frames, args.warmup)

    # Per-frame cost is capped by the camera's native capture period: even if
    # inference is faster than 1/fps, the loop can't beat the sensor cadence.
    capture_ms = 1000.0 / cfg.perception.fps
    per_frame_ms = max(capture_ms, args.tracker_ms) + overhead["p95"]
    hold = cfg.control.hold_frames
    estimated_ms = hold * per_frame_ms

    print("Pipeline overhead (per step, tracker-agnostic):")
    print(f"  min {overhead['min']:.3f}ms  mean {overhead['mean']:.3f}ms  "
          f"p50 {overhead['p50']:.3f}ms  p95 {overhead['p95']:.3f}ms  "
          f"p99 {overhead['p99']:.3f}ms  max {overhead['max']:.3f}ms")
    print(f"\nTracker model: {args.tracker_ms:g}ms/frame (capture+inference); "
          f"sensor cadence {capture_ms:.0f}ms")
    print(f"Estimated gesture->action latency "
          f"({hold} hold frames): {estimated_ms:.1f}ms")

    if args.paced:
        paced = bench_paced_gesture(cfg.perception.fps, hold, args.tracker_ms)
        print(f"Paced end-to-end (real loop cadence): {paced:.1f}ms")
        verdict_ms = max(estimated_ms, paced)
    else:
        verdict_ms = estimated_ms

    ok = verdict_ms < args.budget_ms
    print(f"\nExit criterion < {args.budget_ms:g}ms: "
          f"{'PASS' if ok else 'FAIL'} ({verdict_ms:.1f}ms, "
          f"headroom {args.budget_ms - verdict_ms:.1f}ms)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
