"""PyAutoGUI-based virtual mouse.

Thin, testable wrapper around the input-injection library. Importing
PyAutoGUI is deferred until first use so the rest of the app (and unit
tests) never depend on it being importable (e.g. headless CI).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class VirtualMouse:
    """Cursor + click + drag + scroll primitives backed by PyAutoGUI."""

    def __init__(self, move_duration: float = 0.0, failsafe: bool = True):
        self.move_duration = move_duration
        self.failsafe = failsafe
        self._gui = None

    def _pg(self):
        if self._gui is None:
            import pyautogui

            pyautogui.PAUSE = 0.0
            pyautogui.FAILSAFE = self.failsafe
            self._gui = pyautogui
        return self._gui

    @property
    def available(self) -> bool:
        try:
            self._pg()
            return True
        except Exception as exc:  # pragma: no cover - env dependent
            logger.warning("pyautogui unavailable: %s", exc)
            return False

    def move(self, x: int, y: int) -> None:
        """Instant cursor move to screen (x, y)."""
        self._pg().moveTo(x, y, duration=self.move_duration)

    def position(self) -> tuple[int, int]:
        return self._pg().position()

    def click(self, button: str = "left", clicks: int = 1) -> None:
        self._pg().click(button=button, clicks=clicks)

    def right_click(self) -> None:
        self.click(button="right")

    def drag_start(self, x: int, y: int) -> None:
        """Move to (x, y) with the primary button held down (drag begin)."""
        self._pg().mouseDown(x=x, y=y, button="left")

    def drag_to(self, x: int, y: int) -> None:
        """Continue a drag to (x, y) (button already held)."""
        self._pg().moveTo(x, y, duration=self.move_duration)

    def drag_end(self) -> None:
        """Release the primary button (drag end / drop)."""
        self._pg().mouseUp(button="left")

    def scroll(self, clicks: int) -> None:
        """Scroll vertically; positive = up, negative = down."""
        self._pg().scroll(clicks)

    def hotkey(self, *keys: str) -> None:
        """Press a key combination, e.g. ``hotkey("alt", "tab")``."""
        self._pg().hotkey(*keys)
