"""Webcam wrapper (cv2 mocked, no real camera)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import numpy as np
import pytest

from app.perception.camera import Camera


def _fake_cap(frame=None):
    cap = Mock()
    cap.isOpened.return_value = True
    cap.read.return_value = (True, frame if frame is not None
                             else np.zeros((480, 640, 3), dtype=np.uint8))
    return cap


def test_open_success_sets_resolution():
    with patch("cv2.VideoCapture", return_value=_fake_cap()) as vc:
        cam = Camera(0, 640, 480)
        assert cam.open() is True
        assert cam.available is True
    cap = vc.return_value
    cap.set.assert_any_call(cv2_cap_prop_width, 640)
    cap.set.assert_any_call(cv2_cap_prop_height, 480)


def test_open_failure():
    cap = Mock()
    cap.isOpened.return_value = False
    with patch("cv2.VideoCapture", return_value=cap):
        cam = Camera(0)
        assert cam.open() is False
        assert cam.available is False
    cap.release.assert_called_once()


def test_read_returns_frame():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    with patch("cv2.VideoCapture", return_value=_fake_cap(frame)):
        cam = Camera(0)
        cam.open()
        ok, got = cam.read()
    assert ok is True
    assert got is frame


def test_read_reopens_after_read_failure():
    cap = _fake_cap()
    cap.read.return_value = (False, None)
    with patch("cv2.VideoCapture", return_value=cap):
        cam = Camera(0)
        cam.open()
        # second open() call inside read() should work
        cap.isOpened.return_value = True
        cap.read.side_effect = [(False, None), (True, np.zeros((4, 4, 3)))]
        ok, frame = cam.read()
    assert ok is True
    assert frame.shape == (4, 4, 3)


def test_release_is_idempotent():
    with patch("cv2.VideoCapture", return_value=_fake_cap()):
        cam = Camera(0)
        cam.open()
        cam.release()
        cam.release()
    assert cam.available is False


def test_context_manager_opens_and_releases():
    with patch("cv2.VideoCapture", return_value=_fake_cap()):
        with Camera(0) as cam:
            assert cam.available is True
        assert cam.available is False


def test_read_without_open_attempts_open():
    cap = _fake_cap()
    with patch("cv2.VideoCapture", return_value=cap):
        cam = Camera(0)
        ok, _ = cam.read()
    assert ok is True


# cv2.CAP_PROP_* are int constants in real cv2; expose stable values for the
# mock-based assertions above.
cv2_cap_prop_width = 3
cv2_cap_prop_height = 4
