"""Normalized hand coordinate -> screen coordinate mapping."""

from __future__ import annotations

from app.perception.calibration import fit_homography
from app.perception.mapping import CursorMapper, MappingConfig, monitor_at


def mapper(**overrides):
    cfg = MappingConfig(screen=(0, 0, 1000, 800), **overrides)
    return CursorMapper(cfg)


def test_center_maps_to_screen_center():
    x, y = mapper().to_screen(0.5, 0.5)
    assert (x, y) == (500, 400)


def test_invert_x_mirrors_selfie_view():
    m = mapper()
    left, _ = m.to_screen(0.2, 0.5)
    right, _ = m.to_screen(0.8, 0.5)
    # inverted: hand right (0.8) -> cursor left of center
    assert right < left


def test_no_invert_x_keeps_direction():
    m = mapper(invert_x=False)
    left, _ = m.to_screen(0.2, 0.5)
    right, _ = m.to_screen(0.8, 0.5)
    assert right > left


def test_output_clamped_to_screen():
    m = mapper()
    for nx in (-1.0, 0.0, 0.5, 1.0, 2.0):
        for ny in (-1.0, 0.0, 0.5, 1.0, 2.0):
            x, y = m.to_screen(nx, ny)
            assert 0 <= x <= 999
            assert 0 <= y <= 799


def test_gain_scales_movement():
    low = mapper(gain_y=1.0)
    high = mapper(gain_y=3.0)
    _, ly = low.to_screen(0.5, 0.7)
    _, hy = high.to_screen(0.5, 0.7)
    assert hy > ly  # higher gain -> further from screen center (y grows downward)


def test_gain_grows_distance_from_center():
    m1 = mapper(gain_x=1.0)
    m2 = mapper(gain_x=3.0)
    x1, _ = m1.to_screen(0.9, 0.5)
    x2, _ = m2.to_screen(0.9, 0.5)
    assert abs(x2 - 500) > abs(x1 - 500)


def test_negative_origin_screen():
    # multi-monitor: left-of-primary layout with negative origin (13_MULTIMONITOR)
    m = CursorMapper(MappingConfig(screen=(-1920, 0, 1920, 1080)))
    x, y = m.to_screen(0.5, 0.5)
    assert x == -960
    assert y == 540


def test_degenerate_screen_does_not_crash():
    m = CursorMapper(MappingConfig(screen=(0, 0, 0, 0)))
    x, y = m.to_screen(0.5, 0.5)
    assert (x, y) == (0, 0)


def test_detect_screen_fallback():
    from app.perception import mapping

    rect = mapping.detect_screen()
    assert len(rect) == 4 and rect[2] > 0 and rect[3] > 0


# ------------------------------------------------------------------ #
# Multi-monitor (13_MULTIMONITOR.md)
# ------------------------------------------------------------------ #

MONITORS = [(-1920, 0, 1920, 1080), (0, 0, 1920, 1080)]


def test_monitor_at_finds_containing_monitor():
    assert monitor_at(-1000, 540, MONITORS) == 0
    assert monitor_at(1000, 540, MONITORS) == 1


def test_monitor_at_missing_returns_minus_one():
    # Above both monitors (negative-origin layout, y=0..1080).
    assert monitor_at(1000, 2000, MONITORS) == -1


def test_union_desktop_reaches_second_monitor():
    # Left-of-primary layout: virtual desktop spans x in [-1920, 1920).
    m = CursorMapper(MappingConfig(screen=(-1920, 0, 3840, 1080), monitors=MONITORS))
    # Selfie mirror: hand right in frame (0.9) -> cursor far LEFT -> left
    # monitor; hand left (0.1) -> cursor far right -> right monitor.
    (x, _), zone = m.point_at_zone(0.9, 0.5)
    assert zone == 0
    assert x < 0
    (x2, _), zone2 = m.point_at_zone(0.1, 0.5)
    assert zone2 == 1
    assert x2 > 0


def test_point_at_zone_invert_keeps_hand_direction():
    m = CursorMapper(
        MappingConfig(screen=(-1920, 0, 3840, 1080), monitors=MONITORS, invert_x=False)
    )
    (x_left, _), _ = m.point_at_zone(0.1, 0.5)
    (x_right, _), _ = m.point_at_zone(0.9, 0.5)
    assert x_right > x_left  # non-inverted: hand right -> cursor right


def test_point_at_zone_with_synthetic_monitors_config():
    # monitors come from config when present (no OS call).
    m = CursorMapper(
        MappingConfig(
            screen=(0, 0, 3000, 1000),
            monitors=[(0, 0, 1500, 1000), (1500, 0, 1500, 1000)],
            invert_x=False,
        )
    )
    (_, _), zone = m.point_at_zone(0.99, 0.5)
    assert zone == 1


# ------------------------------------------------------------------ #
# Spatial awareness (Phase 2): active monitor + homography + zones
# ------------------------------------------------------------------ #


def test_active_monitor_centers_on_selected_monitor():
    m = CursorMapper(
        MappingConfig(
            screen=(0, 0, 2000, 800), monitors=[(0, 0, 1000, 800), (1000, 0, 1000, 800)]
        )
    )
    assert m.set_active_monitor(1) is True
    assert m.config.active_monitor == 1
    x, y = m.to_screen(0.5, 0.5)
    assert x == 1500  # center of monitor 1, not the 1000-px union center
    assert y == 400


def test_active_monitor_clamps_to_monitor():
    m = CursorMapper(
        MappingConfig(
            screen=(0, 0, 2000, 800), monitors=[(0, 0, 1000, 800), (1000, 0, 1000, 800)]
        )
    )
    m.set_active_monitor(0)
    x, _ = m.to_screen(0.95, 0.5)  # inverted: would push far right on union
    assert x <= 999


def test_set_active_monitor_rejects_bad_index():
    m = CursorMapper(MappingConfig(screen=(0, 0, 1000, 800)))
    assert m.set_active_monitor(5) is False
    assert m.config.active_monitor is None
    assert m.set_active_monitor(None) is True  # reset to whole desktop


def test_active_monitor_none_uses_union():
    m = CursorMapper(
        MappingConfig(
            screen=(0, 0, 2000, 800), monitors=[(0, 0, 1000, 800), (1000, 0, 1000, 800)]
        )
    )
    x, _ = m.to_screen(0.5, 0.5)
    assert x == 1000  # union center (no active monitor)


def test_homography_path_overrides_gain():
    cal = fit_homography(
        [(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 0), (1000, 0), (1000, 800), (0, 800)]
    )
    # invert_x=True would put hand-right (0.9) far LEFT with the gain formula.
    m = CursorMapper(MappingConfig(screen=(0, 0, 1000, 800), calibration=cal))
    x, y = m.to_screen(0.9, 0.5)
    assert abs(x - 900.0) < 2.0
    assert abs(y - 400.0) < 2.0


def test_invalid_calibration_falls_back_to_gain():
    m = CursorMapper(MappingConfig(screen=(0, 0, 1000, 800), calibration=[1.0] * 8))
    x, y = m.to_screen(0.5, 0.5)
    assert (x, y) == (500, 400)  # gain path (calibration ignored)


def test_homography_clamps_to_screen():
    cal = fit_homography(
        [(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 0), (1000, 0), (1000, 800), (0, 800)]
    )
    m = CursorMapper(MappingConfig(screen=(0, 0, 1000, 800), calibration=cal))
    x, _ = m.to_screen(1.5, 0.5)
    assert x <= 999


def test_zone_for_names_monitor_and_gap():
    m = CursorMapper(
        MappingConfig(
            screen=(0, 0, 2000, 800),
            monitors=[(0, 0, 1000, 800), (1000, 0, 1000, 800)],
            invert_x=False,
        )
    )
    assert m.zone_for(0.1, 0.5) == "monitor_0"
    assert m.zone_for(0.9, 0.5) == "monitor_1"
