"""Screen zone classification (app/perception/zones.py)."""

from __future__ import annotations

from app.perception.zones import (
    LateralZone,
    lateral_zone,
    monitor_at,
    zone_for,
)

MONITORS = [(-1920, 0, 1920, 1080), (0, 0, 1920, 1080)]
SCREEN = (-1920, 0, 3840, 1080)


def test_lateral_zone_thirds():
    assert lateral_zone(0.0) is LateralZone.LEFT
    assert lateral_zone(0.2) is LateralZone.LEFT
    assert lateral_zone(1 / 3) is LateralZone.CENTER  # boundary not < split
    assert lateral_zone(0.5) is LateralZone.CENTER
    assert lateral_zone(2 / 3) is LateralZone.CENTER  # boundary not > 2/3
    assert lateral_zone(0.9) is LateralZone.RIGHT
    assert lateral_zone(1.0) is LateralZone.RIGHT


def test_monitor_at_containing_monitor():
    assert monitor_at(-1000, 540, MONITORS) == 0
    assert monitor_at(1000, 540, MONITORS) == 1


def test_monitor_at_missing():
    assert monitor_at(1000, 2000, MONITORS) == -1


def test_zone_for_inside_monitor():
    assert zone_for(-1000, 540, MONITORS, SCREEN) == "monitor_0"
    assert zone_for(1000, 540, MONITORS, SCREEN) == "monitor_1"


def test_zone_for_left_of_seam_is_left_screen():
    # Seam between monitors at x in [1000, 1200); left half -> left_screen.
    gap_monitors = [(0, 0, 1000, 800), (1200, 0, 900, 800)]
    assert zone_for(1040, 400, gap_monitors, (0, 0, 2100, 800)) == "left_screen"


def test_zone_for_right_of_seam_is_right_screen():
    gap_monitors = [(0, 0, 1000, 800), (1200, 0, 900, 800)]
    assert zone_for(1090, 400, gap_monitors, (0, 0, 2100, 800)) == "right_screen"


def test_zone_for_near_union_edge():
    # Just outside a monitor but within EDGE_MARGIN of the union edges.
    assert zone_for(-1925, 540, MONITORS, SCREEN) == "edge"
    assert zone_for(1925, 540, MONITORS, SCREEN) == "edge"


def test_zone_for_outside_without_screen():
    assert zone_for(-5000, 540, MONITORS) == "outside"
