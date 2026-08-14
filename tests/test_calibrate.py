"""Calibration UI: config merge, live-apply, and HTTP API endpoints."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from app.calibrate.server import (
    CalibrationConfig,
    CalibrationServer,
    apply_config_update,
)
from app.config import AppConfig, update_config
from app.perception.mapping import MappingConfig

# --------------------------------------------------------------------- #
# config merge (update_config)
# --------------------------------------------------------------------- #


def test_update_config_applies_valid_values():
    cfg = AppConfig()
    update_config(cfg, {"control": {"gain_x": "5.0", "preferred_hand": "Left"}})
    assert cfg.control.gain_x == 5.0
    assert cfg.control.preferred_hand == "Left"


def test_update_config_ignores_unknown_and_invalid():
    cfg = AppConfig()
    update_config(
        cfg,
        {
            "control": {"pinch_threshold": "not-a-number", "nope": 1},
            "bogus_section": {"x": 1},
        },
    )
    assert cfg.control.pinch_threshold == 0.06  # invalid -> default kept
    assert not hasattr(cfg.control, "nope")  # unknown field never set


def test_update_config_coerces_bool():
    cfg = AppConfig()
    update_config(cfg, {"control": {"invert_y": "true"}})
    assert cfg.control.invert_y is True


# --------------------------------------------------------------------- #
# live apply
# --------------------------------------------------------------------- #


class _FakeMapper:
    def __init__(self):
        self.config = MappingConfig(
            screen=(0, 0, 1000, 800), monitors=[(0, 0, 1000, 800)]
        )


class _FakePipe:
    mapper = _FakeMapper()
    _smoothing = object()


def test_apply_live_control_rebuilds_mapper_and_smoothing():
    cfg = AppConfig()
    pipe = _FakePipe()
    restart = apply_config_update(cfg, pipe, {"control": {"gain_x": 5.0}})
    assert restart == []
    assert cfg.control.gain_x == 5.0
    assert pipe.mapper.config.gain_x == 5.0
    assert pipe._smoothing is None  # rebuilt next frame with new params
    assert pipe.mapper.config.monitors == [(0, 0, 1000, 800)]  # preserved


def test_camera_change_reports_restart_required():
    cfg = AppConfig()
    restart = apply_config_update(cfg, None, {"perception": {"width": 1280}})
    assert restart == ["width"]


# --------------------------------------------------------------------- #
# HTTP API
# --------------------------------------------------------------------- #


def _start(tmp_path: Path, pipeline=None):
    server = CalibrationServer(
        config=AppConfig(),
        live_pipeline=pipeline,
        server_config=CalibrationConfig(host="127.0.0.1", port=0),
        save_path=tmp_path / "jarvis.yaml",
    )
    assert server.start()
    return server


def _get(server, path: str):
    port = server._httpd.server_address[1]
    url = f"http://127.0.0.1:{port}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def _post(server, path: str, payload: dict):
    port = server._httpd.server_address[1]
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_config_endpoint_returns_sections(tmp_path):
    server = _start(tmp_path)
    try:
        status, body = _get(server, "/api/config")
        assert status == 200
        data = json.loads(body)
        assert {"perception", "control", "hud"} <= set(data["config"])
        assert data["config"]["control"]["gain_x"] == 3.2
    finally:
        server.stop()


def test_post_config_saves_yaml_and_applies_live(tmp_path):
    server = _start(tmp_path, pipeline=_FakePipe())
    try:
        status, data = _post(server, "/api/config", {"control": {"gain_x": 4.5}})
        assert status == 200
        assert data["restart_required"] == []
        assert data["config"]["control"]["gain_x"] == 4.5
        saved = (tmp_path / "jarvis.yaml").read_text(encoding="utf-8")
        assert "gain_x: 4.5" in saved
    finally:
        server.stop()


def test_post_config_reports_restart_for_camera(tmp_path):
    server = _start(tmp_path)
    try:
        _, data = _post(server, "/api/config", {"perception": {"camera_index": 1}})
        assert data["restart_required"] == ["camera_index"]
    finally:
        server.stop()


def test_monitors_endpoint_returns_layout(tmp_path):
    server = _start(tmp_path, pipeline=_FakePipe())
    try:
        status, body = _get(server, "/api/monitors")
        assert status == 200
        data = json.loads(body)
        assert data["monitors"] == [[0, 0, 1000, 800]]
        assert data["screen"] == [0, 0, 1000, 800]
    finally:
        server.stop()


def test_root_serves_calibration_page(tmp_path):
    server = _start(tmp_path)
    try:
        status, body = _get(server, "/")
        assert status == 200
        assert "Calibration" in body
        assert "/api/config" in body
    finally:
        server.stop()


def test_unknown_path_404(tmp_path):
    server = _start(tmp_path)
    try:
        status, body = _get(server, "/nope")
        assert status == 404
        assert "error" in body
    finally:
        server.stop()


# --------------------------------------------------------------------- #
# guided 4-corner calibration (app/calibrate/session.py)
# --------------------------------------------------------------------- #

PTS = [(0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.05, 0.95)]


class _CalibMapper:
    def __init__(self):
        self.config = MappingConfig(
            screen=(0, 0, 1000, 800), monitors=[(0, 0, 1000, 800)]
        )


class _CalibPipe:
    def __init__(self):
        self.mapper = _CalibMapper()
        self._calibration_armed = False
        self._calibration_capture = None

    def arm_calibration(self, capture):
        self._calibration_armed = True
        self._calibration_capture = capture

    def disarm_calibration(self):
        self._calibration_armed = False
        self._calibration_capture = None


def test_calibration_api_full_flow(tmp_path):
    pipe = _CalibPipe()
    server = _start(tmp_path, pipeline=pipe)
    try:
        # Initial state: idle, no calibration saved.
        status, body = _get(server, "/api/calibration")
        data = json.loads(body)
        assert status == 200
        assert not data["active"] and not data["saved_calibration_valid"]

        status, data = _post(server, "/api/calibration/start", {})
        assert status == 200
        assert data["active"] and data["armed"]
        assert data["corner"]["label"] == "top_left"
        assert pipe._calibration_armed

        for nx, ny in PTS:
            _, data = _post(server, "/api/calibration/capture", {"nx": nx, "ny": ny})
        assert not data["active"] and data["valid"]
        assert not data["armed"] and not pipe._calibration_armed
        saved = (tmp_path / "jarvis.yaml").read_text(encoding="utf-8")
        assert "calibration:" in saved

        # Clearing returns to the gain/invert fallback.
        _, data = _post(server, "/api/calibration/clear", {})
        assert not data["saved_calibration_valid"]
    finally:
        server.stop()


def test_calibration_api_reset_disarms(tmp_path):
    pipe = _CalibPipe()
    server = _start(tmp_path, pipeline=pipe)
    try:
        _post(server, "/api/calibration/start", {})
        _, data = _post(server, "/api/calibration/reset", {})
        assert not data["armed"] and not data["active"]
        assert not pipe._calibration_armed
    finally:
        server.stop()


def test_calibration_api_capture_requires_numbers(tmp_path):
    server = _start(tmp_path)
    try:
        status, _ = _post(server, "/api/calibration/capture", {})
        assert status == 400
        status, _ = _post(server, "/api/calibration/capture", {"nx": "a", "ny": 0})
        assert status == 400
    finally:
        server.stop()
