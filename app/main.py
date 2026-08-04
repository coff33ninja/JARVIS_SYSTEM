"""JARVIS Phase 1 entrypoint: run the live hand-tracking control loop.

Usage:
    uv run python app/main.py            # run with defaults + overlay
    uv run python app/main.py --smoke    # webcam skeleton window only

Controls:
    ESC  exit
    q    exit
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from app.config import AppConfig
from app.control.virtual_keyboard import VirtualKeyboard
from app.control.virtual_mouse import VirtualMouse
from app.hud.hud_server import HUDConfig, HUDServer
from app.perception.camera import Camera
from app.perception.hand_tracker import HandLandmarkerTracker
from app.perception.pipeline import ControlPipeline

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("jarvis.main")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="JARVIS Phase 1 control loop")
    p.add_argument("--smoke", action="store_true",
                   help="webcam skeleton window only (no mouse control)")
    p.add_argument("--no-hud", action="store_true",
                   help="disable the overlay websocket server")
    p.add_argument("--config", default=None, help="path to jarvis.yaml")
    return p.parse_args(argv)


def build_pipeline(args: argparse.Namespace, cfg: AppConfig) -> ControlPipeline:
    hud = None
    if not args.no_hud and cfg.hud.enabled:
        server = HUDServer(HUDConfig(host=cfg.hud.host, port=cfg.hud.port))
        if server.start():
            hud = server
    return ControlPipeline(config=cfg, hud=hud)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = AppConfig.load(args.config)

    if args.smoke:
        return _smoke(cfg)

    pipeline = build_pipeline(args, cfg)
    keyboard = VirtualKeyboard()
    stop = _StopKey(
        on_mode_toggle=lambda: pipeline.modes.transition("hotkey"),
        on_keyboard_toggle=keyboard.toggle_osk,
    )
    logger.info("JARVIS Phase 1 running (ESC/q to quit). "
                "Pinch = click, two-finger pinch = right click, "
                "fist = drag, V-sign = scroll, swipe = next/prev window. "
                "F2 = idle/control toggle, F4 = on-screen keyboard.")
    try:
        _loop(pipeline, stop)
    except KeyboardInterrupt:
        pass
    finally:
        stop.close()
        pipeline.close()
    return 0


def _loop(pipeline: ControlPipeline, stop: "_StopKey") -> None:
    last = time.monotonic()
    while not stop.triggered:
        pipeline.step()
        now = time.monotonic()
        if now - last >= 5.0:
            last = now
            s = pipeline.stats
            logger.info("frames=%d detected=%.0f%% fps=%.1f mode=%s",
                        s.frames, s.detection_rate * 100, s.last_fps,
                        pipeline.modes.mode.value)
        stop.wait(0.01)


class _StopKey:
    """Background key listener: ESC/q quit, F2 mode toggle, F4 OSK."""

    def __init__(self, on_mode_toggle=None, on_keyboard_toggle=None):
        import threading

        self._event = threading.Event()
        self._on_mode_toggle = on_mode_toggle
        self._on_keyboard_toggle = on_keyboard_toggle
        try:
            from pynput import keyboard

            self._listener = keyboard.Listener(on_press=self._on_press)
            self._listener.start()
        except Exception as exc:  # pragma: no cover - input env dependent
            logger.warning("keyboard listener unavailable: %s", exc)
            self._listener = None

    def _on_press(self, key) -> None:
        try:
            name = key.char if hasattr(key, "char") else str(key)
        except Exception:  # pragma: no cover
            name = str(key)
        if name in ("\x1b", "q", "Key.esc"):
            self._event.set()
        elif name == "Key.f2" and self._on_mode_toggle:
            self._on_mode_toggle()
        elif name == "Key.f4" and self._on_keyboard_toggle:
            self._on_keyboard_toggle()

    @property
    def triggered(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float) -> None:
        self._event.wait(timeout)

    def close(self) -> None:
        if self._listener is not None:
            self._listener.stop()


def _smoke(cfg: AppConfig) -> int:
    """Webcam window with hand-skeleton overlay (07_SETUP verification)."""
    cam = Camera(cfg.perception.camera_index,
                 cfg.perception.width, cfg.perception.height)
    tracker = HandLandmarkerTracker(
        num_hands=cfg.perception.max_hands,
        min_hand_confidence=cfg.perception.min_hand_confidence,
        min_tracking_confidence=cfg.perception.min_tracking_confidence)
    if not tracker.available:
        logger.error("hand tracker unavailable (model missing?). "
                     "Run `uv run python scripts/smoke_test_hands.py`.")
        return 1
    print("JARVIS smoke test — press ESC to quit.")
    with cam:
        while True:
            ok, frame = cam.read()
            if not ok:
                time.sleep(0.05)
                continue
            result = tracker.process(frame)
            for lmks in result.hands or []:
                for x, y, _ in lmks:
                    cv2.circle(frame, (int(x * frame.shape[1]),
                                       int(y * frame.shape[0])), 3,
                               (0, 255, 0), -1)
            cv2.imshow("JARVIS hand tracking", frame)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
