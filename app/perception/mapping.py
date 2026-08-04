"""Map normalized hand coordinates to screen (cursor) coordinates.

Phase 1 uses an anchor-based linear mapping: normalized (0.5, 0.5) -> screen
center, and ``gain`` controls how many screen pixels a unit of hand movement
covers. ``invert_x`` mirrors the webcam selfie view so a rightward hand
movement moves the cursor right on screen.

Multi-monitor + homography calibration replace this in Phase 2
(13_MULTIMONITOR.md) — the mapper interface stays the same.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ScreenRect = tuple[int, int, int, int]  # x, y, width, height


def detect_screen() -> ScreenRect:
    """Virtual desktop rect from pyautogui (falls back to 1920x1080)."""
    try:
        import pyautogui

        size = pyautogui.size()
        return (0, 0, int(size.width), int(size.height))
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("could not detect screen size: %s; using 1920x1080", exc)
        return (0, 0, 1920, 1080)


@dataclass
class MappingConfig:
    gain_x: float = 3.2
    gain_y: float = 3.2
    invert_x: bool = True
    invert_y: bool = False
    screen: ScreenRect | None = None

    @classmethod
    def from_control(cls, cfg, screen: ScreenRect | None = None) -> "MappingConfig":
        return cls(
            gain_x=cfg.gain_x,
            gain_y=cfg.gain_y,
            invert_x=cfg.invert_x,
            invert_y=cfg.invert_y,
            screen=screen or (cfg.screen_x, cfg.screen_y,
                              cfg.screen_w, cfg.screen_h),
        )


class CursorMapper:
    """Translate a normalized hand position to a clamped screen position."""

    def __init__(self, config: MappingConfig | None = None):
        self.config = config or MappingConfig()

    @property
    def screen(self) -> ScreenRect:
        s = self.config.screen
        if s is not None and all(v is not None for v in s):
            return s  # type: ignore[return-value]
        return detect_screen()

    def to_screen(self, nx: float, ny: float) -> tuple[int, int]:
        """Map normalized (x, y) in [0,1] to (x, y) in screen pixels."""
        x, y, w, h = self.screen
        if w <= 0 or h <= 0:
            logger.warning("screen rect is degenerate (%r); skipping move", self.screen)
            return (x + w // 2, y + h // 2)

        dx = (nx - 0.5) * self.config.gain_x
        dy = (ny - 0.5) * self.config.gain_y
        if self.config.invert_x:
            dx = -dx
        if self.config.invert_y:
            dy = -dy

        cx, cy = x + w / 2.0, y + h / 2.0
        px = cx + dx * w
        py = cy + dy * h

        px = max(x, min(x + w - 1, px))
        py = max(y, min(y + h - 1, py))
        return (int(round(px)), int(round(py)))
