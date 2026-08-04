"""Hand tracker: model download + graceful degradation (no MediaPipe runtime)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.perception.hand_tracker import (
    DEFAULT_MODEL_URL,
    HandLandmarkerTracker,
    HandTrackingResult,
    download_model,
)


def test_result_detected_flag():
    assert HandTrackingResult().detected is False
    assert HandTrackingResult(hands=[[(0.0, 0.0, 0.0)] * 21]).detected is True


def test_result_lands_on_none_when_empty():
    r = HandTrackingResult()
    assert r.hands is None
    assert r.handedness is None


def test_download_model_writes_file(tmp_path, monkeypatch):
    dest = tmp_path / "hand_landmarker.task"

    class _Resp:
        def __init__(self):
            self._done = False

        def read(self, n=-1):
            if not self._done:
                self._done = True
                return b"bytes"
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("urllib.request.urlopen", return_value=_Resp()) as urlopen:
        ok = download_model(DEFAULT_MODEL_URL, dest)

    assert ok
    assert dest.read_bytes() == b"bytes"
    urlopen.assert_called_once()


def test_download_model_failure_cleans_part(tmp_path):
    dest = tmp_path / "hand_landmarker.task"
    with patch("urllib.request.urlopen", side_effect=OSError("boom")):
        assert download_model(DEFAULT_MODEL_URL, dest) is False
    assert not dest.exists()
    assert not Path(str(dest) + ".part").exists()


def test_tracker_without_model_and_no_download_is_unavailable():
    t = HandLandmarkerTracker(model_path="missing.task", auto_download=False)
    assert t.available is False
    assert not t.ensure_model()


def test_tracker_with_existing_model_builds():
    import numpy as np
    from unittest.mock import Mock, patch

    t = HandLandmarkerTracker(model_path="fake.task", auto_download=False)
    landmarker = Mock()
    landmarker.detect_for_video.return_value = Mock(
        hand_landmarks=None, handedness=None)
    with patch("pathlib.Path.exists", return_value=True), \
            patch("mediapipe.tasks.python.BaseOptions"), \
            patch("mediapipe.tasks.python.vision.HandLandmarkerOptions"), \
            patch("mediapipe.tasks.python.vision.HandLandmarker"
                  ".create_from_options", return_value=landmarker):
        assert t.available is True
        result = t.process(np.zeros((10, 10, 3), dtype=np.uint8))
    assert result.detected is False
    t.close()


def test_ensure_model_downloads_when_missing(tmp_path, monkeypatch):
    dest = tmp_path / "hand_landmarker.task"
    t = HandLandmarkerTracker(model_path=dest, auto_download=True)
    with patch("app.perception.hand_tracker.download_model", return_value=True) as dl:
        assert t.ensure_model() is True
        dl.assert_called_once_with(dest=dest)
