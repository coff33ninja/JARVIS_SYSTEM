"""Phase 1 webcam smoke test: hand-skeleton overlay window.

Verifies the MediaPipe Hand Landmarker pipeline end-to-end with a live
webcam (07_SETUP "Verify MediaPipe + webcam"). No mouse control here — this
only proves the perception layer works.

Usage:
    uv run python scripts/smoke_test_hands.py [--index 0]

Exit: press ESC or q in the window.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from app.config import AppConfig
from app.perception.camera import Camera
from app.perception.hand_tracker import HandLandmarkerTracker


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="JARVIS hand-tracking smoke test")
    p.add_argument("--index", type=int, default=None,
                   help="camera index (default: from config, usually 0)")
    p.add_argument("--seconds", type=int, default=0,
                   help="auto-exit after N seconds (0 = run until ESC)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = AppConfig.load()
    idx = args.index if args.index is not None else cfg.perception.camera_index

    cam = Camera(idx, cfg.perception.width, cfg.perception.height)
    tracker = HandLandmarkerTracker(
        num_hands=cfg.perception.max_hands,
        min_hand_confidence=cfg.perception.min_hand_confidence,
        min_tracking_confidence=cfg.perception.min_tracking_confidence)
    if not tracker.available:
        print("ERROR: hand tracker unavailable (model missing or mediapipe "
              "failed). See docs/08_ASSETS.md.")
        return 1
    if not cam.open():
        print(f"ERROR: camera {idx} could not be opened. Try --index 1.")
        return 1

    print("JARVIS smoke test — show your hand to the camera. ESC/q to quit.")
    start = time.monotonic()
    frames = detected = 0
    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                time.sleep(0.05)
                continue
            frames += 1
            result = tracker.process(frame)
            if result.detected:
                detected += 1
                for lmks in result.hands:
                    _draw_landmarks(frame, lmks)
            _draw_hud(frame, result.detected)
            cv2.imshow("JARVIS hand tracking", frame)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break
            if args.seconds and time.monotonic() - start >= args.seconds:
                print("time limit reached")
                break
    finally:
        cam.release()
        tracker.close()
        cv2.destroyAllWindows()

    rate = detected / frames * 100 if frames else 0.0
    print(f"frames={frames} hand-detected={rate:.0f}%")
    return 0 if rate >= 80 else 2


def _draw_landmarks(frame, lmks) -> None:
    h, w = frame.shape[:2]
    for x, y, _ in lmks:
        cv2.circle(frame, (int(x * w), int(y * h)), 3, (0, 255, 0), -1)


def _draw_hud(frame, detected: bool) -> None:
    color = (0, 255, 0) if detected else (0, 0, 255)
    cv2.putText(frame, "HAND TRACKED" if detected else "NO HAND",
                (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)


if __name__ == "__main__":
    sys.exit(main())
