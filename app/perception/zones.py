"""Screen zone classification (Phase 2 spatial awareness).

Pure geometry over the virtual desktop: which monitor a point is on, which
named region ("left screen", "right screen", "edge") it falls in, and which
lateral band a normalized camera coordinate belongs to. These feed the
modifier-hand screen switching (13_MULTIMONITOR.md) and the HUD zone display.

No OS calls here — callers pass monitor rects (mapping.detect_monitors) and
the virtual-screen union explicitly, so everything is unit-testable.
"""

from __future__ import annotations

from enum import Enum

ScreenRect = tuple[int, int, int, int]  # x, y, width, height

# Fraction of the normalized frame that splits LEFT / CENTER / RIGHT.
ZONE_SPLIT = 1.0 / 3.0

# Pixels from a monitor edge that still count as "edge" (below any real
# monitor -> seam or overshoot region).
EDGE_MARGIN_PX = 24


class LateralZone(Enum):
    """Lateral band of the secondary hand in the camera frame."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


def lateral_zone(nx: float) -> LateralZone:
    """Normalized x -> lateral band (LEFT | CENTER | RIGHT).

    The frame is split into thirds; the outer thirds are the target zones
    for the passive modifier-hand monitor selection, the middle third is a
    deadzone so small hand drift doesn't read as a selection.
    """
    if nx < ZONE_SPLIT:
        return LateralZone.LEFT
    if nx > 1.0 - ZONE_SPLIT:
        return LateralZone.RIGHT
    return LateralZone.CENTER


def monitor_at(x: int, y: int, monitors: list[ScreenRect]) -> int:
    """Index of the monitor containing (x, y), or -1 if on no monitor."""
    for i, (mx, my, mw, mh) in enumerate(monitors):
        if mx <= x < mx + mw and my <= y < my + mh:
            return i
    return -1


def zone_for(
    x: int, y: int, monitors: list[ScreenRect], screen: ScreenRect | None = None
) -> str:
    """Named zone for a screen point.

    Returns ``monitor_{i}`` when the point is inside a monitor; otherwise a
    descriptive region relative to the virtual-desktop union ("left_screen",
    "right_screen", or "edge" for points hugging a monitor border).
    """
    idx = monitor_at(x, y, monitors)
    if idx >= 0:
        return f"monitor_{idx}"
    if screen is None:
        return "outside"
    sx, _sy, sw, sh = screen
    if sw <= 0 or sh <= 0:
        return "outside"
    near_left = x - sx < EDGE_MARGIN_PX
    near_right = (sx + sw) - x < EDGE_MARGIN_PX
    if near_left or near_right:
        return "edge"
    if x < sx + sw / 2.0:
        return "left_screen"
    return "right_screen"
