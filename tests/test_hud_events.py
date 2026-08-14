"""HUD event schema (JSON-safe wire contract)."""

from __future__ import annotations

import json

from app.hud.events import (
    ReticleEvent,
    SkeletonEvent,
    StatusEvent,
    encode,
)


def test_skeleton_event_schema():
    e = SkeletonEvent(hands=[[(0.1, 0.2, 0.0)] * 21])
    d = e.to_dict()
    assert d["type"] == "skeleton"
    assert len(d["hands"]) == 1
    assert len(d["hands"][0]) == 21
    assert json.dumps(d)  # serializable


def test_reticle_event_schema():
    d = ReticleEvent(x=100.0, y=200.0).to_dict()
    assert d["type"] == "reticle"
    assert d["x"] == 100.0
    assert d["y"] == 200.0
    assert json.dumps(d)


def test_reticle_event_zone_field():
    d = ReticleEvent(x=100.0, y=200.0, monitor=0, zone="monitor_0").to_dict()
    assert d["zone"] == "monitor_0"
    assert d["monitor"] == 0
    # default zone is empty (backwards compatible)
    assert ReticleEvent(0, 0).to_dict()["zone"] == ""
    assert json.dumps(d)


def test_status_event_schema():
    d = StatusEvent(mode="control", fps=29.5, detected=True, gesture="point").to_dict()
    assert d["type"] == "status"
    assert d["mode"] == "control"
    assert d["fps"] == 29.5
    assert d["detected"] is True
    assert d["gesture"] == "point"
    assert json.dumps(d)


def test_encode_normalises_all_event_types():
    assert encode(SkeletonEvent())["type"] == "skeleton"
    assert encode(ReticleEvent(0, 0))["type"] == "reticle"
    assert encode(StatusEvent())["type"] == "status"


def test_timestamps_present():
    assert "ts" in SkeletonEvent().to_dict()
    assert "ts" in ReticleEvent(0, 0).to_dict()
    assert "ts" in StatusEvent().to_dict()


def test_monitors_event_active_monitor_field():
    from app.hud.events import MonitorsEvent

    d = MonitorsEvent(monitors=[(0, 0, 1000, 800)], active_monitor=1).to_dict()
    assert d["type"] == "monitors"
    assert d["active_monitor"] == 1
    # default is None (whole desktop) — backwards compatible
    assert MonitorsEvent().to_dict()["active_monitor"] is None
    assert json.dumps(d)
