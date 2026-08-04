"""Gesture geometry classification (pure math, no hardware)."""

from __future__ import annotations

import pytest

from app.perception.geometry import (
    GeometryConfig,
    INDEX_TIP,
    MIDDLE_TIP,
    THUMB_TIP,
    classify,
    distance,
    finger_extended,
    hand_size,
    palm_center,
    pinch_ratio,
    point_position,
)
from conftest import fist, make_hand, open_hand, pinch_hand, point_hand, two_pinch_hand, v_sign


def test_hand_size_positive():
    assert hand_size(open_hand()) > 0.0


def test_finger_extended_open_vs_curled():
    assert finger_extended(open_hand(), "index")
    assert finger_extended(open_hand(), "pinky")
    assert not finger_extended(fist(), "index")
    assert not finger_extended(fist(), "middle")


def test_palm_center_between_wrist_and_fingers():
    lm = open_hand()
    center = palm_center(lm)
    assert lm[0][1] < center[1] < 0.62  # wrist above, mcp below


def test_pinch_ratio_open_is_large():
    assert pinch_ratio(open_hand()) > 1.0


def test_pinch_ratio_pinch_is_small():
    assert pinch_ratio(pinch_hand()) < 0.01


@pytest.mark.parametrize(
    "hand,expected",
    [
        (open_hand, "open_palm"),
        (fist, "fist"),
        (v_sign, "v_sign"),
        (point_hand, "point"),
        (pinch_hand, "pinch"),
        (two_pinch_hand, "two_finger_pinch"),
    ],
)
def test_classify_named_gestures(hand, expected):
    assert classify(hand()).name == expected


def test_classify_pinch_precedence_over_point():
    # A pinch has the index extended too; it must classify as pinch.
    pose = classify(pinch_hand())
    assert pose.pinch
    assert pose.name == "pinch"


def test_classify_two_pinch_requires_thumb_at_middle():
    lm = two_pinch_hand()
    assert classify(lm).two_finger_pinch
    assert not classify(lm).pinch


def test_point_requires_other_fingers_curled():
    # Full open hand is open_palm, not point, even though index is extended.
    assert classify(open_hand()).name == "open_palm"
    assert classify(point_hand()).name == "point"


def test_pinch_respects_threshold():
    # Thumb a small gap away from the index tip: within the default threshold,
    # but above an ultra-strict one — proves the knob actually gates.
    lm = point_hand()
    tip = lm[INDEX_TIP]
    lm[THUMB_TIP] = (tip[0], tip[1] + 0.005, 0.0)
    assert classify(lm).pinch
    assert not classify(lm, GeometryConfig(pinch_threshold=1e-9)).pinch


def test_pinch_index_extension_gate():
    # Thumb near index tip but index curled -> not a pinch.
    lm = make_hand(fingers={"index": 0.0, "middle": 0.0,
                            "ring": 0.0, "pinky": 0.0})
    lm[THUMB_TIP] = lm[INDEX_TIP]
    assert not classify(lm).pinch


def test_point_position_clamped():
    lm = open_hand()
    lm[INDEX_TIP] = (-0.5, 1.5, 0.0)
    x, y = point_position(lm)
    assert 0.0 <= x <= 1.0
    assert 0.0 <= y <= 1.0


def test_degenerate_tiny_hand_does_not_throw():
    lm = [(0.5, 0.5, 0.0)] * 21
    pose = classify(lm)  # no exception
    assert pose.name == "none" or pose.name


def test_index_xy_tracks_index_tip():
    lm = point_hand()
    x, y = classify(lm).index_xy
    assert abs(x - lm[INDEX_TIP][0]) < 1e-6
    assert abs(y - lm[INDEX_TIP][1]) < 1e-6


def test_distance_metric():
    assert distance((0.0, 0.0, 0.0), (3.0, 4.0, 0.0)) == 5.0


def test_middle_tip_constant_sanity():
    assert MIDDLE_TIP == 12
    assert THUMB_TIP == 4
