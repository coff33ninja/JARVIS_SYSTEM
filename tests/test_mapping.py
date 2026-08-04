"""Normalized hand coordinate -> screen coordinate mapping."""

from __future__ import annotations

from app.perception.mapping import CursorMapper, MappingConfig


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
    import app.perception.mapping as mapping

    rect = mapping.detect_screen()
    assert len(rect) == 4 and rect[2] > 0 and rect[3] > 0
