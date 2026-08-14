"""Guided 4-corner pinch calibration (docs/13_MULTIMONITOR.md).

The user is shown each of the 4 virtual-desktop corners in turn, points an
extended index finger at it, and pinches. Each pinch records the normalized
index-tip position as the source point for that corner; after the 4th pinch
the homography is fit (DLT, see app/perception/calibration.py), applied live
to the mapper, and saved to the config file.

Two layers:

* ``CalibrationSession`` — a pure state machine over the 4 corners. Fits and
  reports the homography; degenerate fits (duplicate / collinear points) are
  rejected and the offending corner is cleared so the user can re-pinch it.
* ``CalibrationController`` — the side-effectful glue the HTTP server uses:
  owns the session, arms/disarms the live pipeline's pinch capture
  (``ControlPipeline.arm_calibration``), applies a finished homography to the
  mapper + config, and persists it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ..config import AppConfig, CONFIG_FILE
from ..perception.calibration import fit_homography, is_valid_homography

CORNER_LABELS = ("top_left", "top_right", "bottom_right", "bottom_left")


@dataclass
class Corner:
    index: int
    label: str
    pixel: tuple[int, int]
    captured: tuple[float, float] | None = None


class CalibrationSession:
    """Record the 4 corner correspondences and fit a homography."""

    def __init__(self, screen: tuple[int, int, int, int]):
        x, y, w, h = screen
        self.screen = tuple(screen)
        self.corners = [
            Corner(0, "top_left", (x, y)),
            Corner(1, "top_right", (x + w, y)),
            Corner(2, "bottom_right", (x + w, y + h)),
            Corner(3, "bottom_left", (x, y + h)),
        ]
        self.done = False
        self.homography: list[float] | None = None
        self.error: str | None = None

    @property
    def current(self) -> Corner | None:
        """The next corner still missing a capture, or None when done."""
        if self.done:
            return None
        for corner in self.corners:
            if corner.captured is None:
                return corner
        return None

    @property
    def captured_count(self) -> int:
        return sum(1 for c in self.corners if c.captured is not None)

    def capture(self, nx: float, ny: float) -> tuple[Corner | None, bool]:
        """Record a pinch for the current corner. Returns (corner, finished)."""
        corner = self.current
        if corner is None:
            return None, self.done
        corner.captured = (float(nx), float(ny))
        if self.captured_count < len(self.corners):
            return corner, False
        return corner, self.finish()

    def finish(self) -> bool:
        """Fit the homography from the 4 recorded points.

        On a degenerate fit (duplicate / collinear corners) all captures are
        cleared so the user restarts with 4 distinct points; ``error`` explains
        why. Clearing everything rather than one corner keeps recovery
        guaranteed — a single retried point can stay degenerate.
        """
        src = [c.captured for c in self.corners]
        dst = [c.pixel for c in self.corners]
        h = fit_homography(src, dst)  # type: ignore[arg-type]
        if h is None:
            self.cancel()
            self.error = ("degenerate corners — pinch at 4 distinct screen "
                          "corners and try again")
            return False
        self.homography = h
        self.done = True
        self.error = None
        return True

    def cancel(self) -> None:
        for corner in self.corners:
            corner.captured = None
        self.done = False
        self.homography = None
        self.error = None

    def status(self) -> dict[str, Any]:
        corner = self.current
        return {
            "active": not self.done,
            "captured": self.captured_count,
            "total": len(self.corners),
            "corner": None if corner is None else {
                "index": corner.index,
                "label": corner.label,
                "pixel": list(corner.pixel),
            },
            "homography": self.homography,
            "valid": is_valid_homography(self.homography),
            "error": self.error,
        }


class CalibrationController:
    """Session + live pipeline + config persistence glue for the HTTP API."""

    def __init__(self, config: AppConfig, pipeline: Optional[object] = None,
                 save_path: Optional[Path | str] = None):
        self.config = config
        self.pipeline = pipeline
        self._save_path = Path(save_path) if save_path else CONFIG_FILE
        self.session: CalibrationSession | None = None

    @property
    def armed(self) -> bool:
        return bool(getattr(self.pipeline, "_calibration_armed", False))

    def start(self) -> dict[str, Any]:
        """Begin a fresh 4-corner session over the virtual desktop."""
        self._disarm()
        screen = self._screen_rect()
        self.session = CalibrationSession(screen)
        self._arm()
        return self.status()

    def reset(self) -> dict[str, Any]:
        """Discard the in-progress session and disarm the pipeline."""
        self._disarm()
        self.session = None
        return self.status()

    def clear(self) -> dict[str, Any]:
        """Drop the saved homography and fall back to gain/invert mapping."""
        self.config.control.calibration = None
        mapper = getattr(self.pipeline, "mapper", None)
        if mapper is not None:
            mapper.config.calibration = None
        self.config.save(self._save_path)
        return self.status()

    def capture(self, nx: float, ny: float) -> dict[str, Any]:
        """Record a corner point (from a pinch or an explicit request)."""
        if self.session is None:
            return {"error": "no active calibration session — start one first"}
        corner, finished = self.session.capture(nx, ny)
        if finished and self.session.homography is not None:
            self._apply_homography(self.session.homography)
            self._disarm()
        return self.status()

    def status(self) -> dict[str, Any]:
        sess = (self.session.status() if self.session is not None else {
            "active": False, "captured": 0, "total": len(CORNER_LABELS),
            "corner": None, "homography": None, "valid": False, "error": None,
        })
        sess["armed"] = self.armed
        sess["saved_calibration_valid"] = is_valid_homography(
            self.config.control.calibration)
        return sess

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _on_capture(self, nx: float, ny: float) -> None:
        """Pipeline pinch callback: record and finish/apply when done."""
        self.capture(nx, ny)

    def _screen_rect(self) -> tuple[int, int, int, int]:
        mapper = getattr(self.pipeline, "mapper", None)
        screen = getattr(mapper.config, "screen", None) if mapper is not None else None
        if screen is not None and all(v is not None for v in screen):
            return tuple(screen)  # type: ignore[return-value]
        from ..perception.mapping import detect_screen

        return tuple(detect_screen())  # type: ignore[return-value]

    def _apply_homography(self, h: list[float]) -> None:
        self.config.control.calibration = h
        mapper = getattr(self.pipeline, "mapper", None)
        if mapper is not None:
            mapper.config.calibration = h
        self.config.save(self._save_path)

    def _arm(self) -> None:
        if self.pipeline is None or not hasattr(self.pipeline, "arm_calibration"):
            return
        self.pipeline.arm_calibration(self._on_capture)

    def _disarm(self) -> None:
        if self.pipeline is None or not hasattr(self.pipeline, "disarm_calibration"):
            return
        self.pipeline.disarm_calibration()
