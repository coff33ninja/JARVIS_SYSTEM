"""Webcam wrapper (cv2 mocked, no real camera)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import numpy as np
import pytest

from app.perception.camera import MAX_REOPEN_ATTEMPTS, Camera


def _fake_cap(frame=None):
    cap = Mock()
    cap.isOpened.return_value = True
    cap.read.return_value = (
        True,
        frame if frame is not None else np.zeros((480, 640, 3), dtype=np.uint8),
    )
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
    cap.release.assert_called()  # once per candidate backend


@pytest.mark.parametrize("shape", [(10, 10, 3), (4, 4, 3), (640, 480, 3)])
def test_read_returns_frame(shape):
    frame = np.zeros(shape, dtype=np.uint8)
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


def test_read_gives_up_after_repeated_failures():
    cap = _fake_cap()
    cap.read.return_value = (False, None)
    with patch("cv2.VideoCapture", return_value=cap) as vc:
        cam = Camera(0)
        cam.open()
        ok, frame = None, None
        for _ in range(MAX_REOPEN_ATTEMPTS + 1):
            cam._last_reopen = float("-inf")  # bypass throttle
            ok, frame = cam.read()
        assert ok is False
        assert frame is None
        # reopen attempts are capped; the device is released after give-up
        assert cam._reopen_attempts == MAX_REOPEN_ATTEMPTS
        assert cam.available is False
        assert vc.call_count == 1 + MAX_REOPEN_ATTEMPTS


def test_read_backs_off_and_retries_after_give_up():
    import time as _time

    from app.perception.camera import BACKOFF_INTERVAL_S

    cap = _fake_cap()
    cap.read.return_value = (False, None)
    with patch("cv2.VideoCapture", return_value=cap) as vc:
        cam = Camera(0)
        cam.open()
        for _ in range(MAX_REOPEN_ATTEMPTS + 1):
            cam._last_reopen = float("-inf")  # bypass throttle
            cam.read()
        assert cam._disabled is True
        calls_before = vc.call_count
        # within backoff window: no reopen attempts
        cam._last_reopen = _time.monotonic()
        cam.read()
        assert vc.call_count == calls_before
        # after backoff elapses: a fresh open cycle is attempted
        cam._last_reopen = _time.monotonic() - BACKOFF_INTERVAL_S - 1
        ok, _ = cam.read()
        assert vc.call_count == calls_before + 1
        assert cam._disabled is False
        assert ok is False  # still failing, but it tried again


def test_read_throttles_reopen_attempts():
    cap = _fake_cap()
    cap.read.return_value = (False, None)
    with patch("cv2.VideoCapture", return_value=cap) as vc:
        cam = Camera(0)
        cam.open()
        cam._last_reopen = float("-inf")
        cam.read()
        first_reopens = vc.call_count
        cam.read()  # within REOPEN_INTERVAL_S -> skipped
    assert vc.call_count == first_reopens


def test_open_falls_back_to_next_backend():
    dead = Mock()
    dead.isOpened.return_value = False
    cap = _fake_cap()
    with patch("cv2.VideoCapture", side_effect=[dead, cap]):
        cam = Camera(0)
        assert cam.open() is True
    cap.set.assert_any_call(3, 640)
    cap.set.assert_any_call(4, 480)


def test_read_after_clean_open_uses_buffersize_one():
    cap = _fake_cap()
    with patch("cv2.VideoCapture", return_value=cap):
        cam = Camera(0)
        cam.open()
    cap.set.assert_any_call(38, 1)  # CAP_PROP_BUFFERSIZE


# cv2.CAP_PROP_* are int constants in real cv2; expose stable values for the
# mock-based assertions above.
cv2_cap_prop_width = 3
cv2_cap_prop_height = 4
