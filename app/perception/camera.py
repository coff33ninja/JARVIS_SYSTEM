"""Webcam capture via OpenCV (cv2).

Thin wrapper over ``cv2.VideoCapture`` so the pipeline can open/release the
camera and degrade gracefully when the device is missing (Graceful
degradation principle: control keeps working when a webcam slot fails).
"""

from __future__ import annotations

import logging

import cv2

logger = logging.getLogger(__name__)


class Camera:
    """OpenCV webcam with context-manager lifecycle and auto-reopen."""

    def __init__(self, index: int = 0, width: int = 640, height: int = 480):
        self.index = index
        self.width = width
        self.height = height
        self._cap: cv2.VideoCapture | None = None

    @property
    def available(self) -> bool:
        return self._cap is not None

    def open(self) -> bool:
        """Open the device and set resolution. False on failure (no raise)."""
        self.close()
        try:
            cap = cv2.VideoCapture(self.index)
        except Exception as exc:  # pragma: no cover - driver dependent
            logger.warning("camera %d failed to open: %s", self.index, exc)
            return False
        if not cap.isOpened():
            logger.warning("camera %d is not openable", self.index)
            cap.release()
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap
        logger.info("camera %d open at %dx%d", self.index, self.width, self.height)
        return True

    def read(self) -> tuple[bool, object]:
        """Return (ok, frame). ``frame`` is None on failure."""
        if self._cap is None and not self.open():
            return (False, None)
        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok:
            # Try a one-shot reopen; a detached USB camera comes back.
            logger.warning("camera %d read failed; attempting reopen", self.index)
            if self.open():
                ok, frame = self._cap.read()
        return (ok, frame if ok else None)

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:  # pragma: no cover
                pass
            self._cap = None

    def close(self) -> None:
        self.release()

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.release()
