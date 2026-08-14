"""Webcam capture via OpenCV (cv2).

Thin wrapper over ``cv2.VideoCapture`` so the pipeline can open/release the
camera and degrade gracefully when the device is missing or stops delivering
frames (Graceful degradation principle: control keeps working when a webcam
slot fails).

Backend: the cv2 default is preferred (on Windows that is MSMF). If a backend
fails to open, DirectShow (``CAP_DSHOW``) and MSMF are tried as alternates —
some webcams only work on one of them.

Reopen attempts are throttled, bounded, and then backed off (slow periodic
retry) so a dead or temporarily-invalidated device degrades to a quiet "no
frames" state instead of busy-looping the read path, while still recovering
once the device is available again.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Self

import cv2

logger = logging.getLogger(__name__)

REOPEN_INTERVAL_S = 1.0  # minimum gap between rapid reopen attempts
MAX_REOPEN_ATTEMPTS = 3  # rapid attempts before backing off
BACKOFF_INTERVAL_S = 10.0  # slow retry cadence after the rapid attempts


class Camera:
    """OpenCV webcam with context-manager lifecycle and auto-reopen."""

    def __init__(
        self,
        index: int = 0,
        width: int = 640,
        height: int = 480,
        backend: int | None = None,
    ):
        self.index = index
        self.width = width
        self.height = height
        self.backend = backend
        self._cap: cv2.VideoCapture | None = None
        self._last_reopen = float("-inf")
        self._reopen_attempts = 0
        self._disabled = False

    @property
    def available(self) -> bool:
        return self._cap is not None

    def _backends(self) -> list[int | None]:
        """Candidate backends, most preferred first. None = cv2 default."""
        if self.backend is not None:
            return [self.backend]
        if os.name == "nt":
            candidates = [None]  # cv2 default (MSMF on Windows)
            for attr in ("CAP_DSHOW", "CAP_MSMF"):
                if hasattr(cv2, attr):
                    backend = getattr(cv2, attr)
                    if backend not in candidates:
                        candidates.append(backend)
            return candidates
        return [None]

    def open(self) -> bool:
        """Open the device and set resolution. False on failure (no raise)."""
        self.close()
        for backend in self._backends():
            try:
                cap = (
                    cv2.VideoCapture(self.index, backend)
                    if backend is not None
                    else cv2.VideoCapture(self.index)
                )
            except Exception as exc:  # pragma: no cover - driver dependent
                logger.warning(
                    "camera %d backend %s failed to open: %s",
                    self.index,
                    backend,
                    exc,
                )
                continue
            if not cap.isOpened():
                logger.warning(
                    "camera %d is not openable via backend %s",
                    self.index,
                    backend,
                )
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._cap = cap
            # A successful open re-arms an explicitly reopened camera, but the
            # consecutive-failure counter is reset only on a good frame (below)
            # so a device that opens but never delivers still exhausts the cap.
            self._disabled = False
            logger.info(
                "camera %d open at %dx%d (backend %s)",
                self.index,
                self.width,
                self.height,
                backend,
            )
            return True
        return False

    def read(self) -> tuple[bool, object]:
        """Return (ok, frame). ``frame`` is None on failure."""
        if self._cap is None:
            now = time.monotonic()
            if self._disabled:
                if now - self._last_reopen < BACKOFF_INTERVAL_S:
                    return (False, None)
                # Backoff elapsed: try a fresh open cycle.
                self._reopen_attempts = 0
                self._disabled = False
            elif now - self._last_reopen < REOPEN_INTERVAL_S and self._reopen_attempts:
                return (False, None)
            if self._reopen_attempts >= MAX_REOPEN_ATTEMPTS:
                self._disable()
                return (False, None)
            self._reopen_attempts += 1
            self._last_reopen = now
            if not self.open():
                return (False, None)
        ok, frame = self._cap.read()
        if not ok:
            return self._recover()
        self._reopen_attempts = 0
        return (True, frame)

    def _recover(self) -> tuple[bool, object]:
        """Bounded, throttled reopen after a failed read.

        ``_reopen_attempts`` counts consecutive failed reads. ``open()`` does
        not reset it, so a camera that opens but never delivers a frame still
        exhausts the cap instead of looping forever.
        """
        if self._reopen_attempts >= MAX_REOPEN_ATTEMPTS:
            self._disable()
            return (False, None)
        now = time.monotonic()
        if now - self._last_reopen < REOPEN_INTERVAL_S:
            return (False, None)
        self._reopen_attempts += 1
        self._last_reopen = now
        logger.warning(
            "camera %d read failed; attempting reopen (%d/%d)",
            self.index,
            self._reopen_attempts,
            MAX_REOPEN_ATTEMPTS,
        )
        if self.open():
            ok, frame = self._cap.read()
            if ok:
                self._reopen_attempts = 0
            return (ok, frame if ok else None)
        return (False, None)

    def _disable(self) -> None:
        """Back off: release the device and retry on the slow cadence."""
        if not self._disabled:
            logger.warning(
                "camera %d unavailable; retrying every %gs",
                self.index,
                BACKOFF_INTERVAL_S,
            )
        self._disabled = True
        self._last_reopen = time.monotonic()
        self.release()

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:  # pragma: no cover
                pass
            self._cap = None

    def close(self) -> None:
        self.release()

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.release()
