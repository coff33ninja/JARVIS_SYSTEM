"""HUD event schema (app/hud/). Pure dataclasses -> JSON-safe dicts.

The core emits these over the websocket feed (hud_server.py); the frontend
draws them. Keeping the schema as plain dataclasses makes the contract
unit-testable (09_TESTING "HUD protocol") and language-agnostic.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SkeletonEvent:
    """Hand skeleton: per-hand list of 21 normalized (x, y, z) landmarks."""

    hands: list[list[tuple[float, float, float]]] = field(default_factory=list)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "skeleton", "ts": self.ts, "hands": self.hands}


@dataclass
class ReticleEvent:
    """Where the cursor is (screen px), for the on-screen reticle."""

    x: float
    y: float
    monitor: int = 0  # index of the monitor the point lands on (-1 = none)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "reticle", "x": self.x, "y": self.y,
                "monitor": self.monitor, "ts": self.ts}


@dataclass
class StatusEvent:
    """Pipeline health: mode, fps, detection flag."""

    mode: str = "idle"
    fps: float = 0.0
    detected: bool = False
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "status", "mode": self.mode, "fps": self.fps,
                "detected": self.detected, "ts": self.ts}


@dataclass
class MonitorsEvent:
    """Per-monitor layout (logical coords) for the overlay to draw zones."""

    monitors: list[tuple[int, int, int, int]] = field(default_factory=list)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "monitors", "monitors": self.monitors, "ts": self.ts}


def encode(event: SkeletonEvent | ReticleEvent | StatusEvent | MonitorsEvent) -> dict[str, Any]:
    """Normalise any HUD event to its wire dict (mirrors asdict for safety)."""
    return event.to_dict()
