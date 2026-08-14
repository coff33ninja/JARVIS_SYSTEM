"""Projective homography calibration (Phase 2 spatial awareness).

Fits a 3x3 homography mapping normalized camera coordinates -> virtual
desktop pixels (13_MULTIMONITOR.md "Calibration"). The guided calibration
flow records the index-tip position at each of 4 screen corners and fits the
matrix here; the matrix is stored row-major in ``control.calibration`` and
applied by ``CursorMapper.to_screen``.

Pure math over numpy — no OS calls, so the fit/apply/validation paths are
fully unit-testable.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

Point = tuple[float, float]
Homography = list[float]  # 3x3, row-major (9 floats)

_MIN_POINTS = 4
# Relative threshold below which the smallest singular value marks a
# degenerate fit (collinear / duplicate points, n < 4).
_DEGENERATE_RATIO = 1e-8


def fit_homography(src: list[Point], dst: list[Point]) -> Homography | None:
    """Fit H such that H * (x, y, 1) ~ (u, v, 1) for each correspondence.

    ``src`` = normalized camera positions, ``dst`` = screen pixel positions.
    Uses the direct linear transform (DLT) solved via SVD. Returns the
    row-major 9-float matrix, or ``None`` when the correspondence set is
    degenerate (fewer than 4 points, or points collinear/duplicated).
    """
    if len(src) != len(dst) or len(src) < _MIN_POINTS:
        return None
    rows: list[list[float]] = []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([-x, -y, -1.0, 0.0, 0.0, 0.0, u * x, u * y, u])
        rows.append([0.0, 0.0, 0.0, -x, -y, -1.0, v * x, v * y, v])
    a = np.asarray(rows, dtype=np.float64)
    _, singular, vt = np.linalg.svd(a)
    if singular[-1] <= _DEGENERATE_RATIO * singular[0]:
        logger.warning("homography fit is degenerate (collinear/duplicate "
                       "points, n=%d)", len(src))
        return None
    h = vt[-1].reshape((3, 3))
    if abs(h[2, 2]) < 1e-12:
        return None
    h = h / h[2, 2]
    return h.reshape(-1).tolist()


def apply_homography(h: Homography, x: float, y: float) -> Point:
    """Map (x, y) through a row-major homography -> (u, v).

    Returns the input point unchanged when the matrix is degenerate at the
    query location (w ~ 0), so a point outside the camera plane degrades
    gracefully instead of exploding.
    """
    w = h[6] * x + h[7] * y + h[8]
    if abs(w) < 1e-12:
        return (x, y)
    u = (h[0] * x + h[1] * y + h[2]) / w
    v = (h[3] * x + h[4] * y + h[5]) / w
    return (u, v)


def is_valid_homography(h: Homography | None) -> bool:
    """True when ``h`` is a plausible row-major homography.

    Checks shape, finiteness, and a non-degenerate scale so a corrupted or
    hand-edited config matrix falls back to the gain mapping instead of
    producing garbage cursor positions.
    """
    if h is None or not isinstance(h, (list, tuple)) or len(h) != 9:
        return False
    try:
        matrix = np.asarray(h, dtype=np.float64).reshape((3, 3))
    except (TypeError, ValueError):
        return False
    if not np.all(np.isfinite(matrix)):
        return False
    det = np.linalg.det(matrix)
    return bool(np.isfinite(det) and abs(det) > 1e-9 and abs(det) < 1e9)
