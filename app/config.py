"""Central configuration: defaults, YAML load/save, and env overrides.

Phase 1 keeps everything in one place so calibration knobs (camera, gain,
smoothing, gesture thresholds, screen mapping) can be tuned without touching
code. Loaded by ``app.main`` (Phase 1 entrypoint) and the smoke scripts.

Values are plain dataclasses with sensible defaults; every field is
bounds-checked on load (see 09_TESTING "Config" unit tests).
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CONFIG_DIR = Path("config")
CONFIG_FILE = CONFIG_DIR / "jarvis.yaml"


@dataclass
class PerceptionConfig:
    """Webcam + hand-tracking settings (app/perception/)."""

    camera_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    max_hands: int = 1
    min_hand_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    min_presence_confidence: float = 0.5


@dataclass
class ControlConfig:
    """Cursor mapping, smoothing, and gesture thresholds (app/control/)."""

    # Cursor gain: how many screen pixels per normalized hand unit.
    gain_x: float = 3.2
    gain_y: float = 3.2
    invert_x: bool = True   # selfie mirror: moving right appears left in frame
    invert_y: bool = False

    # 1-Euro filter parameters (04_GESTURE_VOCABULARY recommended defaults).
    min_cutoff: float = 1.0
    beta: float = 0.007
    d_cutoff: float = 1.0

    # Gesture thresholds (normalized by hand size, see geometry.py).
    pinch_threshold: float = 0.06       # thumb-index tip distance -> click
    two_finger_pinch_threshold: float = 0.06  # thumb-middle tip -> right click
    scroll_threshold: float = 0.02      # V-sign vertical delta -> scroll tick
    scroll_hold_ms: int = 150           # min time between scroll ticks

    # Debounce: consecutive frames a gesture must hold before it fires.
    hold_frames: int = 2

    # PyAutoGUI corner fail-safe. Off for gesture control: corners are
    # legitimate cursor targets and the loop has its own abort (ESC/q).
    failsafe: bool = False

    # Screen mapping target (virtual desktop origin/size). Auto-detected
    # from pyautogui at runtime unless explicitly overridden.
    screen_x: int | None = None
    screen_y: int | None = None
    screen_w: int | None = None
    screen_h: int | None = None


@dataclass
class HudConfig:
    """Minimal overlay (app/hud/): host/port for the websocket event feed."""

    host: str = "127.0.0.1"
    port: int = 8765
    enabled: bool = True


@dataclass
class AppConfig:
    perception: PerceptionConfig = field(default_factory=PerceptionConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    hud: HudConfig = field(default_factory=HudConfig)

    # ------------------------------------------------------------------ #
    # load / save
    # ------------------------------------------------------------------ #

    @classmethod
    def load(cls, path: str | Path = CONFIG_FILE) -> "AppConfig":
        """Load from YAML. Missing file -> defaults (never raises).

        Unknown keys are ignored; invalid values fall back to the field
        default and log a warning. This keeps a stale or hand-edited config
        from bricking the app.
        """
        cfg = cls()
        path = Path(path) if path is not None else Path(CONFIG_FILE)
        if not path.exists():
            return cfg
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, OSError) as exc:
            logger.warning("could not read config %s: %s; using defaults", path, exc)
            return cfg
        for section in ("perception", "control", "hud"):
            target = getattr(cfg, section)
            raw = data.get(section)
            if not isinstance(raw, dict):
                continue
            _apply_section(target, raw)
        return cfg

    def save(self, path: str | Path = CONFIG_FILE) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(asdict(self), sort_keys=False),
                        encoding="utf-8")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def defaults(cls) -> "AppConfig":
        return cls()


def _apply_section(target: Any, raw: dict[str, Any]) -> None:
    """Apply validated values from a raw dict onto a dataclass section."""
    for f in fields(target):
        if f.name not in raw:
            continue
        try:
            value = _coerce(f.type, raw[f.name])
        except (TypeError, ValueError):
            logger.warning("config value %s=%r invalid; using default %r",
                           f.name, raw[f.name], getattr(target, f.name))
            continue
        setattr(target, f.name, value)


def _coerce(annotation: Any, value: Any) -> Any:
    """Coerce a raw value to a field's (simple) annotation type."""
    if annotation is float or annotation == "float":
        return float(value)
    if annotation is int or annotation == "int":
        return int(value)
    if annotation is bool or annotation == "bool":
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if annotation is str or annotation == "str":
        return str(value)
    return value
