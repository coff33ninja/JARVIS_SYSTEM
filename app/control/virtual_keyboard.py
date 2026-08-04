"""On-screen keyboard + text-input primitives.

Typing is injected through PyAutoGUI (deferred import). The on-screen
keyboard toggle drives Windows' built-in ``osk.exe`` so a hand can flip a
visible keyboard without touching the physical one (Phase 2 "virtual keyboard
toggle"). Non-Windows hosts simply report the OSK as unavailable.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess

logger = logging.getLogger(__name__)

OSK = shutil.which("osk.exe")


class VirtualKeyboard:
    """Keyboard primitives: type text, key combos, and the OSK toggle."""

    def __init__(self):
        self._gui = None

    def _pg(self):
        if self._gui is None:
            import pyautogui

            pyautogui.PAUSE = 0.0
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

    def type_text(self, text: str, interval: float = 0.0) -> None:
        """Type ``text`` at the focused field."""
        self._pg().write(text, interval=interval)

    def hotkey(self, *keys: str) -> None:
        """Press a key combination, e.g. ``hotkey("ctrl", "c")``."""
        self._pg().hotkey(*keys)

    def press(self, *keys: str) -> None:
        """Tap one or more keys."""
        self._pg().press(*keys)

    # ------------------------------------------------------------------ #
    # On-screen keyboard (Windows osk.exe)
    # ------------------------------------------------------------------ #

    @property
    def osk_available(self) -> bool:
        return platform.system() == "Windows" and OSK is not None

    def osk_running(self) -> bool:
        if not self.osk_available:
            return False
        try:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq osk.exe"],
                capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.TimeoutExpired):  # pragma: no cover
            return False
        return "osk.exe" in out

    def toggle_osk(self) -> bool:
        """Show the on-screen keyboard, or hide it if already open.

        Returns True if the keyboard is now visible.
        """
        if not self.osk_available:
            return False
        if self.osk_running():
            try:
                subprocess.run(["taskkill", "/IM", "osk.exe", "/F"],
                               capture_output=True, timeout=5)
            except (OSError, subprocess.TimeoutExpired):  # pragma: no cover
                pass
            return False
        subprocess.Popen([OSK])
        return True
