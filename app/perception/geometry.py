"""Hand-geometry gesture classification from the 21 MediaPipe landmarks.

Pure math over landmark tuples ``(x, y, z)`` normalized to [0, 1] — no
MediaPipe runtime needed, so every classifier is unit-testable with synthetic
landmark sets (09_TESTING "Gesture geometry" section).

Landmark index map (MediaPipe hand model):
  wrist=0  thumb=1..4  index=5..8  middle=9..12  ring=13..16  pinky=17..20
where ``*_MCP`` is the metacarpal base and ``*_TIP`` the fingertip.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Landmark indices (MediaPipe 21-point hand model).
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

# The four non-thumb fingers: (tip, dip, mcp).
FINGERS = {
    "index": (INDEX_TIP, INDEX_DIP, INDEX_MCP),
    "middle": (MIDDLE_TIP, MIDDLE_DIP, MIDDLE_MCP),
    "ring": (RING_TIP, RING_DIP, RING_MCP),
    "pinky": (PINKY_TIP, PINKY_DIP, PINKY_MCP),
}

Landmark = tuple[float, float, float]
Landmarks = list[Landmark] | tuple[Landmark, ...]


@dataclass
class GeometryConfig:
    """Gesture thresholds, normalized by hand size (scale invariant)."""

    pinch_threshold: float = 0.06
    two_finger_pinch_threshold: float = 0.06

    @classmethod
    def from_control(cls, cfg) -> "GeometryConfig":
        return cls(
            pinch_threshold=cfg.pinch_threshold,
            two_finger_pinch_threshold=cfg.two_finger_pinch_threshold,
        )


@dataclass
class HandPose:
    """Classified hand state for one frame."""

    index_xy: tuple[float, float] = (0.5, 0.5)
    index_extended: bool = False
    pinch: bool = False
    two_finger_pinch: bool = False
    fist: bool = False
    open_palm: bool = False
    v_sign: bool = False
    thumbs_up: bool = False
    thumbs_down: bool = False

    @property
    def name(self) -> str:
        if self.thumbs_down:
            return "thumbs_down"
        if self.thumbs_up:
            return "thumbs_up"
        if self.fist:
            return "fist"
        if self.two_finger_pinch:
            return "two_finger_pinch"
        if self.pinch:
            return "pinch"
        if self.v_sign:
            return "v_sign"
        if self.open_palm:
            return "open_palm"
        if self.index_extended:
            return "point"
        return "none"


def distance(a: Landmark, b: Landmark) -> float:
    """Euclidean distance between two landmarks (x, y, z)."""
    return math.dist(a, b)


def hand_size(lmks: Landmarks) -> float:
    """Normalization reference: wrist -> middle MCP distance.

    Falling back to ~0.1 keeps thresholds finite for degenerate input so
    classification never throws (callers treat tiny hands as "none").
    """
    d = distance(lmks[WRIST], lmks[MIDDLE_MCP])
    return d if d > 1e-6 else 0.1


def palm_center(lmks: Landmarks) -> Landmark:
    """Robust palm center: mean of wrist, index MCP, pinky MCP."""
    return tuple(
        (lmks[WRIST][i] + lmks[INDEX_MCP][i] + lmks[PINKY_MCP][i]) / 3.0
        for i in range(3)
    )


def two_hand_spread(lmks_a: Landmarks, lmks_b: Landmarks) -> float:
    """Normalized [0, 1] distance between the two hands' palm centers.

    Used for the two-hand spread gesture (both palms far apart) that toggles
    Transfer mode. Coordinates are already normalized to the frame, so the
    value reflects how far apart the hands sit in view.
    """
    return distance(palm_center(lmks_a), palm_center(lmks_b))


def finger_extended(lmks: Landmarks, name: str) -> bool:
    """True when a fingertip is pushed out past its DIP joint.

    Rotation-invariant: compares distance from the finger MCP base to the
    tip vs. to the DIP. Curled fingers pull the tip back inside the DIP.
    """
    tip, dip, mcp = FINGERS[name]
    return distance(lmks[tip], lmks[mcp]) > distance(lmks[dip], lmks[mcp])


def finger_tip(lmks: Landmarks, name: str) -> Landmark:
    tip, _, _ = FINGERS[name]
    return lmks[tip]


def thumb_extended(lmks: Landmarks) -> bool:
    """True when the thumb tip is pushed out past its IP joint (vs. wrist)."""
    return distance(lmks[THUMB_TIP], lmks[WRIST]) > \
        distance(lmks[THUMB_IP], lmks[WRIST])


def pinch_ratio(lmks: Landmarks, thumb: Landmark | None = None,
                finger_tip: Landmark | None = None) -> float:
    """Distance between thumb tip and a fingertip, normalized by hand size."""
    size = hand_size(lmks)
    a = thumb if thumb is not None else lmks[THUMB_TIP]
    b = finger_tip if finger_tip is not None else lmks[INDEX_TIP]
    return distance(a, b) / size


def point_position(lmks: Landmarks) -> tuple[float, float]:
    """Normalized [0,1] (x, y) of the index fingertip for cursor mapping."""
    lm = lmks[INDEX_TIP]
    return (max(0.0, min(1.0, lm[0])), max(0.0, min(1.0, lm[1])))


# --------------------------------------------------------------------------- #
# Circle / index-trace detection ("Jarvis" attention)
#
# A trajectory of normalized index-tip positions forms a circle when it stays
# roughly square in its bounding box, closes its loop, and sweeps a consistent
# angular path around its centroid. Pure math over (x, y) samples, so the
# detector is unit-testable without MediaPipe or a webcam.
# --------------------------------------------------------------------------- #

TracePoint = tuple[float, float]


def trace_signed_angle(points: list[TracePoint]) -> float:
    """Signed angular sweep (radians) of a 2D trajectory around its centroid.

    Consecutive centroid vectors are rotated and their wrapped angle deltas
    (normalized to (-pi, pi]) summed, so a tip circling the centroid
    accumulates ``|total| -> 2*pi`` while a back-and-forth wiggle cancels
    toward zero.
    """
    if len(points) < 2:
        return 0.0
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)

    def _angle(p: TracePoint) -> float:
        return math.atan2(p[1] - cy, p[0] - cx)

    total = 0.0
    prev = _angle(points[0])
    for p in points[1:]:
        cur = _angle(p)
        delta = cur - prev
        while delta > math.pi:
            delta -= 2.0 * math.pi
        while delta < -math.pi:
            delta += 2.0 * math.pi
        total += delta
        prev = cur
    return total


def trace_bbox(points: list[TracePoint]) -> tuple[float, float, float, float]:
    """Bounding box ``(x0, y0, x1, y1)`` of a 2D trajectory."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def is_circle_trace(points: list[TracePoint],
                    min_samples: int = 8,
                    min_sweep: float = 4.5,
                    max_aspect: float = 0.6,
                    endpoint_tol: float = 0.4) -> bool:
    """True when ``points`` (normalized index-tip trajectory) draws a circle.

    A circle requires: enough samples, a roughly square bounding box (a fast
    lateral swipe is a thin line and rejected), a closed loop (start near
    end), and a consistent angular sweep of at least ``min_sweep`` radians.
    Direction-agnostic: clockwise and counter-clockwise both count.
    """
    if len(points) < min_samples:
        return False
    x0, y0, x1, y1 = trace_bbox(points)
    w, h = x1 - x0, y1 - y0
    diag = math.hypot(w, h)
    if diag < 1e-6:
        return False
    aspect = min(w, h) / max(w, h) if w and h else 0.0
    if aspect < max_aspect:
        return False
    if math.hypot(points[0][0] - points[-1][0],
                  points[0][1] - points[-1][1]) > endpoint_tol * diag:
        return False
    return abs(trace_signed_angle(points)) >= min_sweep


def classify(lmks: Landmarks, cfg: GeometryConfig | None = None) -> HandPose:
    """Classify a 21-landmark hand into a gesture-usable HandPose.

    Gesture precedence (first match wins): thumbs-down > thumbs-up > fist >
    pinch > two-finger-pinch > open-palm > V-sign > point. This ordering keeps
    a fist with an extended thumb from being read as a drag, and an open palm
    from being mistaken for a point.
    """
    cfg = cfg or GeometryConfig()
    index_ext = finger_extended(lmks, "index")
    middle_ext = finger_extended(lmks, "middle")
    ring_ext = finger_extended(lmks, "ring")
    pinky_ext = finger_extended(lmks, "pinky")

    idx = finger_tip(lmks, "index")
    mid = finger_tip(lmks, "middle")
    pinch_ratio_ = pinch_ratio(lmks, lmks[THUMB_TIP], idx)
    two_pinch_ratio = pinch_ratio(lmks, lmks[THUMB_TIP], mid)

    any_ext = index_ext or middle_ext or ring_ext or pinky_ext
    thumb_ext = thumb_extended(lmks)

    # Thumbs up/down: thumb extended, all four fingers curled. Orientation is
    # read on the thumb's own vertical axis (tip above/below the MCP).
    thumbs_up = thumb_ext and not any_ext and lmks[THUMB_TIP][1] < lmks[THUMB_MCP][1]
    thumbs_down = thumb_ext and not any_ext and lmks[THUMB_TIP][1] > lmks[THUMB_MCP][1]

    return HandPose(
        index_xy=point_position(lmks),
        index_extended=index_ext,
        pinch=pinch_ratio_ < cfg.pinch_threshold and index_ext,
        two_finger_pinch=two_pinch_ratio < cfg.two_finger_pinch_threshold,
        fist=not any_ext and not thumbs_up and not thumbs_down,
        open_palm=index_ext and middle_ext and ring_ext and pinky_ext,
        v_sign=index_ext and middle_ext and not ring_ext and not pinky_ext,
        thumbs_up=thumbs_up,
        thumbs_down=thumbs_down,
    )
