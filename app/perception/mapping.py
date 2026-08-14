"""Map normalized hand coordinates to screen (cursor) coordinates.

The mapper uses an anchor-based linear mapping: normalized (0.5, 0.5) ->
screen center, and ``gain`` controls how many screen pixels a unit of hand
movement covers. ``invert_x`` mirrors the webcam selfie view so a rightward
hand movement moves the cursor right on screen.

Multi-monitor (13_MULTIMONITOR.md): the target "screen" is the **virtual
desktop** — the union of all monitors, including negative-origin left-of-
primary layouts. Mapping over the union means a left/right hand sweep lands
the cursor on the matching monitor; ``zone_for`` identifies which monitor a
point is on (HUD zones, Phase 4 throw direction).
"""

from __future__ import annotations

import ctypes
import logging
from dataclasses import dataclass, field

from .calibration import apply_homography, is_valid_homography
from .zones import zone_for as _zone_for

logger = logging.getLogger(__name__)

ScreenRect = tuple[int, int, int, int]  # x, y, width, height

# Windows SystemMetrics for the virtual-screen bounding box.
_SM_XVIRTUAL = 76
_SM_YVIRTUAL = 77
_SM_CXVIRTUAL = 78
_SM_CYVIRTUAL = 79

_MonitorEnumProc = ctypes.WINFUNCTYPE(
    ctypes.c_int,
    ctypes.c_ulong,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_long * 4),
    ctypes.c_double,
)


def _windows_virtual_screen() -> ScreenRect | None:
    """Virtual desktop union via Win32 SystemMetrics."""
    try:
        user32 = ctypes.windll.user32
        x = user32.GetSystemMetrics(_SM_XVIRTUAL)
        y = user32.GetSystemMetrics(_SM_YVIRTUAL)
        w = user32.GetSystemMetrics(_SM_CXVIRTUAL)
        h = user32.GetSystemMetrics(_SM_CYVIRTUAL)
        if w > 0 and h > 0:
            return (int(x), int(y), int(w), int(h))
    except Exception:  # pragma: no cover - non-Windows / restricted env
        pass
    return None


def detect_screen() -> ScreenRect:
    """Virtual desktop rect (union of all monitors); 1920x1080 fallback."""
    if _windows_virtual_screen() is not None:
        return _windows_virtual_screen()  # type: ignore[return-value]
    try:
        import pyautogui

        size = pyautogui.size()
        return (0, 0, int(size.width), int(size.height))
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("could not detect screen size: %s; using 1920x1080", exc)
        return (0, 0, 1920, 1080)


def detect_monitors() -> list[ScreenRect]:
    """Per-monitor rects in logical (virtual-desktop) coordinates."""
    rects: list[ScreenRect] = []
    try:
        user32 = ctypes.windll.user32

        def _cb(_hmon, _hdc, rect, _lparam) -> int:
            r = rect.contents
            rects.append((int(r[0]), int(r[1]), int(r[2] - r[0]), int(r[3] - r[1])))
            return 1

        proc = _MonitorEnumProc(_cb)
        if user32.EnumDisplayMonitors(0, 0, proc, 0) and rects:
            return rects
    except Exception:  # pragma: no cover - non-Windows / restricted env
        pass
    try:
        import pyautogui

        size = pyautogui.size()
        return [(0, 0, int(size.width), int(size.height))]
    except Exception:  # pragma: no cover - environment dependent
        return [(0, 0, 1920, 1080)]


def monitor_at(x: int, y: int, monitors: list[ScreenRect]) -> int:
    """Index of the monitor containing (x, y), or -1 if on no monitor.

    Points outside every monitor (rare, but possible at desktop seams or on
    mis-detected layouts) return -1 so callers can fall back gracefully.
    """
    for i, (mx, my, mw, mh) in enumerate(monitors):
        if mx <= x < mx + mw and my <= y < my + mh:
            return i
    return -1


@dataclass
class MappingConfig:
    gain_x: float = 3.2
    gain_y: float = 3.2
    invert_x: bool = True
    invert_y: bool = False
    screen: ScreenRect | None = None
    monitors: list[ScreenRect] = field(default_factory=list)
    # Spatial awareness (Phase 2): calibrated homography (row-major 9 floats)
    # replaces the gain/invert formula; active_monitor re-centers the cursor
    # on one monitor's rect.
    calibration: list[float] | None = None
    active_monitor: int | None = None

    @classmethod
    def from_control(cls, cfg, screen: ScreenRect | None = None) -> MappingConfig:
        return cls(
            gain_x=cfg.gain_x,
            gain_y=cfg.gain_y,
            invert_x=cfg.invert_x,
            invert_y=cfg.invert_y,
            screen=screen or (cfg.screen_x, cfg.screen_y, cfg.screen_w, cfg.screen_h),
            calibration=cfg.calibration,
            active_monitor=cfg.active_monitor,
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

    @property
    def monitors(self) -> list[ScreenRect]:
        return self.config.monitors or detect_monitors()

    @property
    def active_screen(self) -> ScreenRect:
        """Rect the cursor maps/clamps into: active monitor or full desktop."""
        idx = self.config.active_monitor
        monitors = self.monitors
        if idx is not None and 0 <= idx < len(monitors):
            return monitors[idx]
        return self.screen

    def set_active_monitor(self, idx: int | None) -> bool:
        """Select the monitor the cursor operates on (None = whole desktop).

        Returns False when the index is out of range; the setting is left
        unchanged in that case.
        """
        if idx is not None and not 0 <= idx < len(self.monitors):
            return False
        self.config.active_monitor = idx
        return True

    def to_screen(self, nx: float, ny: float) -> tuple[int, int]:
        """Map normalized (x, y) in [0,1] to (x, y) in screen pixels.

        Uses the calibrated homography when one is set and valid; otherwise
        falls back to the anchor + gain formula. The result is re-centered on
        and clamped to the active monitor (or the whole virtual desktop when
        none is selected).
        """
        x, y, w, h = self.active_screen
        if w <= 0 or h <= 0:
            logger.warning(
                "screen rect is degenerate (%r); skipping move", self.active_screen
            )
            return (x + w // 2, y + h // 2)

        if is_valid_homography(self.config.calibration):
            px, py = apply_homography(self.config.calibration, nx, ny)
        else:
            dx = (nx - 0.5) * self.config.gain_x
            dy = (ny - 0.5) * self.config.gain_y
            if self.config.invert_x:
                dx = -dx
            if self.config.invert_y:
                dy = -dy
            cx, cy = x + w / 2.0, y + h / 2.0
            px, py = cx + dx * w, cy + dy * h

        px = max(x, min(x + w - 1, px))
        py = max(y, min(y + h - 1, py))
        return (round(px), round(py))

    def zone_for(self, nx: float, ny: float) -> str:
        """Named zone string for a normalized hand position."""
        px, py = self.to_screen(nx, ny)
        return _zone_for(px, py, self.monitors, self.screen)

    def point_at_zone(self, nx: float, ny: float) -> tuple[tuple[int, int], int]:
        """Map a hand position to (screen point, monitor index it lands on).

        This is the "point at a screen zone" primitive: hand far left in the
        frame lands on the left monitor, far right on the right monitor.
        """
        px, py = self.to_screen(nx, ny)
        return (px, py), monitor_at(px, py, self.monitors)
