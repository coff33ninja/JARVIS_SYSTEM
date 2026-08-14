"""Guided 4-corner pinch calibration (app/calibrate/session.py)."""

from __future__ import annotations

from app.calibrate.session import CalibrationController, CalibrationSession
from app.config import AppConfig
from app.perception.calibration import apply_homography, is_valid_homography
from app.perception.mapping import MappingConfig

SCREEN = (0, 0, 1000, 800)
PTS = [(0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.05, 0.95)]


# --------------------------------------------------------------------- #
# CalibrationSession (pure state machine)
# --------------------------------------------------------------------- #

def test_session_steps_through_corners_in_order():
    s = CalibrationSession(SCREEN)
    assert s.current.label == "top_left"
    assert s.current.pixel == (0, 0)
    s.capture(0.05, 0.05)
    assert s.current.label == "top_right"
    assert s.current.pixel == (1000, 0)
    s.capture(0.95, 0.05)
    s.capture(0.95, 0.95)
    assert s.current.label == "bottom_left"
    s.capture(0.05, 0.95)
    assert s.done and s.current is None


def test_session_fits_homography_mapping_corners_and_center():
    s = CalibrationSession(SCREEN)
    for nx, ny in PTS:
        s.capture(nx, ny)
    assert s.done
    assert is_valid_homography(s.homography)
    u, v = apply_homography(s.homography, 0.05, 0.05)
    assert abs(u - 0) < 60 and abs(v - 0) < 60
    u, v = apply_homography(s.homography, 0.5, 0.5)
    assert abs(u - 500) < 60 and abs(v - 400) < 60


def test_session_rejects_degenerate_and_resets_for_retry():
    s = CalibrationSession(SCREEN)
    for _ in range(4):  # all pinches at the same spot -> rank-deficient
        s.capture(0.1, 0.1)
    assert not s.done
    assert s.error
    assert s.captured_count == 0  # cleared so the user restarts distinct
    # Re-capturing 4 distinct corners completes the fit.
    for nx, ny in PTS:
        s.capture(nx, ny)
    assert s.done and s.homography and s.error is None


def test_session_cancel_resets():
    s = CalibrationSession(SCREEN)
    s.capture(0.05, 0.05)
    s.cancel()
    assert s.captured_count == 0
    assert s.current.label == "top_left"
    assert s.homography is None and not s.done


# --------------------------------------------------------------------- #
# CalibrationController (pipeline + config glue)
# --------------------------------------------------------------------- #

class _FakeMapper:
    def __init__(self):
        self.config = MappingConfig(screen=SCREEN,
                                    monitors=[(0, 0, 1000, 800)])


class _FakePipe:
    def __init__(self):
        self.mapper = _FakeMapper()
        self._calibration_armed = False
        self._calibration_capture = None

    def arm_calibration(self, capture):
        self._calibration_armed = True
        self._calibration_capture = capture

    def disarm_calibration(self):
        self._calibration_armed = False
        self._calibration_capture = None


def test_controller_start_arms_and_capture_drives_full_flow(tmp_path):
    cfg = AppConfig()
    pipe = _FakePipe()
    ctrl = CalibrationController(cfg, pipe, save_path=tmp_path / "jarvis.yaml")
    st = ctrl.start()
    assert st["active"] and st["armed"]
    assert st["corner"]["label"] == "top_left"
    # A real pipeline calls this on each pinch edge.
    for nx, ny in PTS:
        pipe._calibration_capture(nx, ny)
    st = ctrl.status()
    assert st["valid"] and not st["active"] and not st["armed"]
    # Applied live to the mapper and persisted to config + YAML.
    assert cfg.control.calibration == st["homography"]
    assert pipe.mapper.config.calibration == st["homography"]
    assert st["saved_calibration_valid"]
    assert "calibration:" in (tmp_path / "jarvis.yaml").read_text(encoding="utf-8")


def test_controller_start_replaces_previous_session(tmp_path):
    cfg = AppConfig()
    pipe = _FakePipe()
    ctrl = CalibrationController(cfg, pipe, save_path=tmp_path / "jarvis.yaml")
    ctrl.start()
    for nx, ny in PTS[:3]:
        ctrl.capture(nx, ny)
    ctrl.start()  # fresh session: earlier captures gone, still armed
    assert ctrl.status()["captured"] == 0
    assert ctrl.status()["active"] and ctrl.status()["armed"]


def test_controller_reset_disarms(tmp_path):
    cfg = AppConfig()
    pipe = _FakePipe()
    ctrl = CalibrationController(cfg, pipe, save_path=tmp_path / "jarvis.yaml")
    ctrl.start()
    assert pipe._calibration_armed
    st = ctrl.reset()
    assert not st["armed"] and not st["active"]
    assert not pipe._calibration_armed
    assert not pipe._calibration_capture


def test_controller_capture_without_session_errors(tmp_path):
    ctrl = CalibrationController(AppConfig(), save_path=tmp_path / "jarvis.yaml")
    st = ctrl.capture(0.1, 0.1)
    assert "error" in st


def test_controller_clear_drops_saved_homography(tmp_path):
    cfg = AppConfig()
    pipe = _FakePipe()
    ctrl = CalibrationController(cfg, pipe, save_path=tmp_path / "jarvis.yaml")
    ctrl.start()
    for nx, ny in PTS:
        ctrl.capture(nx, ny)
    st = ctrl.clear()
    assert not st["saved_calibration_valid"]
    assert cfg.control.calibration is None
    assert pipe.mapper.config.calibration is None
    assert "calibration: null" in (tmp_path / "jarvis.yaml").read_text(encoding="utf-8")
