"""Calibration UI backend: a small local HTTP server (stdlib only).

Phase 2 "Calibration UI": a web form to tune camera / sensitivity /
smoothing / gesture thresholds / monitor layout without editing YAML by
hand. The server runs in its own thread (``http.server``) so the rest of
the app stays synchronous, mirroring the HUD server pattern.

Endpoints:
    GET  /api/config    -> current AppConfig as JSON
    POST /api/config    -> merge validated values, apply live, save YAML
    GET  /api/monitors  -> detected per-monitor layout + virtual desktop
    GET  /              -> the calibration form (hud/calibrate.html)

``live_pipeline`` is optional. When present, control changes are applied
in place (mapping gain/invert, smoothing rebuild, gesture thresholds) so
they take effect on the next frame; camera changes are reported as
"restart required" since the capture device can't be rebuilt mid-loop.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional

from ..config import AppConfig, CONFIG_FILE, update_config

logger = logging.getLogger(__name__)

CALIBRATE_HTML = Path(__file__).resolve().parent.parent.parent / "hud" / "calibrate.html"


@dataclass
class CalibrationConfig:
    host: str = "127.0.0.1"
    port: int = 8766


class CalibrationServer:
    """Expose the config API + calibration page on a local HTTP port."""

    def __init__(self, config: AppConfig, live_pipeline: Optional[object] = None,
                 server_config: Optional[CalibrationConfig] = None,
                 save_path: Optional[Path | str] = None):
        self.config = config
        self.pipeline = live_pipeline
        self._cfg = server_config or CalibrationConfig()
        self._save_path = Path(save_path) if save_path else CONFIG_FILE
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: Exception | None = None

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> bool:
        """Start the server thread. True if it bound successfully."""
        self._ready.clear()
        self._error = None

        def _serve() -> None:
            try:
                handler = _make_handler(self.config, self.pipeline,
                                        self._save_path)
                self._httpd = ThreadingHTTPServer(
                    (self._cfg.host, self._cfg.port), handler)
                self._ready.set()
                self._httpd.serve_forever()
            except Exception as exc:  # pragma: no cover - bind errors
                self._error = exc
                self._ready.set()

        self._thread = threading.Thread(target=_serve, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            logger.warning("calibration server did not become ready")
            return False
        if self._error is not None:
            logger.warning("calibration server failed to start: %s", self._error)
            return False
        logger.info("calibration UI on http://%s:%s",
                    self._cfg.host, self._cfg.port)
        return True

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._httpd = None


def _make_handler(config: AppConfig, pipeline: Optional[object],
                  save_path: Path):
    """Build a request handler bound to this server's config + pipeline."""
    import urllib.parse

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # quiet the default stderr spam
            return

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, body: bytes) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}

        def do_GET(self) -> None:
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/config":
                self._send_json(200, {"config": config.to_dict()})
            elif path == "/api/monitors":
                layout = _monitor_layout(pipeline)
                self._send_json(200, {
                    "monitors": layout["monitors"],
                    "screen": layout["screen"],
                })
            elif path in ("/", "/calibrate"):
                body = _read_page()
                self._send_html(body)
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = urllib.parse.urlparse(self.path).path
            if path != "/api/config":
                self._send_json(404, {"error": "not found"})
                return
            payload = self._read_json_body()
            restart_required = apply_config_update(config, pipeline, payload)
            config.save(save_path)
            self._send_json(200, {
                "config": config.to_dict(),
                "restart_required": restart_required,
            })

    return Handler


def _monitor_layout(pipeline: Optional[object]) -> dict[str, Any]:
    """Per-monitor rects + virtual desktop union for the calibration page."""
    from ..perception.mapping import detect_monitors, detect_screen

    mapper = getattr(pipeline, "mapper", None)
    if mapper is not None and mapper.config.screen is not None:
        screen_cfg = mapper.config.screen
        monitors = mapper.config.monitors or detect_monitors()
        screen = (list(screen_cfg) if all(v is not None for v in screen_cfg)
                  else list(detect_screen()))
    else:
        monitors = detect_monitors()
        screen = list(detect_screen())
    return {"monitors": [list(m) for m in monitors], "screen": screen}


def apply_config_update(cfg: AppConfig, pipeline: Optional[object],
                        payload: dict[str, Any]) -> list[str]:
    """Merge ``payload`` into ``cfg``, apply live where possible.

    Returns the list of changed settings that need an app restart (only
    camera device settings, which can't be rebuilt mid-loop).
    """
    before = {k: v for k, v in cfg.perception.__dict__.items()}
    update_config(cfg, payload)
    after = cfg.perception.__dict__

    restart: list[str] = []
    for name in ("camera_index", "width", "height", "fps"):
        if before.get(name) != after.get(name):
            restart.append(name)

    if pipeline is not None:
        _apply_live_control(cfg, pipeline)
    return restart


def _apply_live_control(cfg: AppConfig, pipeline: object) -> None:
    """Rebuild mapping + smoothing so control changes take effect now."""
    from ..perception.mapping import MappingConfig

    mapper = getattr(pipeline, "mapper", None)
    if mapper is not None:
        screen = list(mapper.config.screen) if mapper.config.screen else None
        monitors = mapper.config.monitors
        mapper.config = MappingConfig.from_control(cfg.control, screen=screen)
        mapper.config.monitors = monitors
    # Drop the filter so it is rebuilt with the new smoothing params.
    if hasattr(pipeline, "_smoothing"):
        pipeline._smoothing = None


def _read_page() -> bytes:
    if CALIBRATE_HTML.exists():
        return CALIBRATE_HTML.read_bytes()
    return b"<!doctype html><meta charset=utf-8><title>Calibration</title><p>calibrate.html missing</p>"
