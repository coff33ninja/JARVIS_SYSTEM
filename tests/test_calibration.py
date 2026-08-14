"""Homography calibration (app/perception/calibration.py)."""

from __future__ import annotations

from app.perception.calibration import (
    apply_homography,
    fit_homography,
    is_valid_homography,
)

CORNERS_SRC = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
CORNERS_DST = [(0.0, 0.0), (1000.0, 0.0), (1000.0, 800.0), (0.0, 800.0)]


def test_fit_and_apply_maps_corners_and_center():
    h = fit_homography(CORNERS_SRC, CORNERS_DST)
    assert h is not None and len(h) == 9
    u, v = apply_homography(h, 0.5, 0.5)
    assert abs(u - 500.0) < 1.0
    assert abs(v - 400.0) < 1.0
    u, v = apply_homography(h, 1.0, 0.0)
    assert abs(u - 1000.0) < 1.0


def test_fit_requires_four_points():
    assert fit_homography(CORNERS_SRC[:3], CORNERS_DST[:3]) is None
    assert fit_homography([], []) is None


def test_fit_rejects_mismatched_lengths():
    assert fit_homography(CORNERS_SRC, CORNERS_DST[:2]) is None


def test_fit_rejects_collinear_points():
    src = [(0.0, 0.0), (0.1, 0.0), (0.5, 0.0), (1.0, 0.0)]
    dst = [(0.0, 0.0), (100.0, 0.0), (500.0, 0.0), (1000.0, 0.0)]
    assert fit_homography(src, dst) is None


def test_fit_homography_is_normalized():
    h = fit_homography(CORNERS_SRC, CORNERS_DST)
    assert abs(h[8] - 1.0) < 1e-9


def test_is_valid_homography():
    assert is_valid_homography(None) is False
    assert is_valid_homography([]) is False
    assert is_valid_homography([1.0] * 8) is False  # wrong length
    assert is_valid_homography("garbage") is False
    assert is_valid_homography([1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0]) is True


def test_is_valid_homography_rejects_degenerate_scale():
    assert is_valid_homography([0.0] * 9) is False


def test_apply_homography_degenerate_w_returns_input():
    h = [1.0, 0, 0, 0, 1.0, 0, 0, 0, 0.0]  # w = 0 everywhere
    assert apply_homography(h, 0.3, 0.7) == (0.3, 0.7)
