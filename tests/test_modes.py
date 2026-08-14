"""Mode machine transitions and gesture gating."""

from __future__ import annotations

import pytest

from app.control.modes import (
    GESTURES,
    HOTKEY,
    PRESENT_GESTURE,
    TRANSFER_GESTURE,
    VOICE,
    WAKE,
    Mode,
    ModeMachine,
)


def test_initial_idle():
    assert ModeMachine().mode == Mode.IDLE


def test_wake_from_idle():
    m = ModeMachine()
    assert m.transition(WAKE) == Mode.CONTROL


def test_hotkey_toggle():
    m = ModeMachine(Mode.CONTROL)
    assert m.transition(HOTKEY) == Mode.IDLE
    assert m.transition(HOTKEY) == Mode.CONTROL


def test_voice_cycle():
    m = ModeMachine(Mode.CONTROL)
    assert m.transition(VOICE) == Mode.CHAT
    assert m.transition(VOICE) == Mode.CONTROL


def test_transfer_cycle():
    m = ModeMachine(Mode.CONTROL)
    assert m.transition(TRANSFER_GESTURE) == Mode.TRANSFER
    assert m.transition(TRANSFER_GESTURE) == Mode.CONTROL


def test_present_cycle():
    m = ModeMachine(Mode.CONTROL)
    assert m.transition(PRESENT_GESTURE) == Mode.PRESENTATION
    assert m.transition(PRESENT_GESTURE) == Mode.CONTROL


def test_unknown_trigger_is_noop():
    m = ModeMachine()
    assert m.transition("bogus") == Mode.IDLE


def test_invalid_transition_is_noop():
    # Chat has no hotkey rule; it stays in chat.
    m = ModeMachine(Mode.CHAT)
    assert m.transition(HOTKEY) == Mode.CHAT


def test_idle_allows_nothing():
    m = ModeMachine()
    assert m.allows("point") is False
    assert m.active_gestures() == set()


@pytest.mark.parametrize(
    "mode,allowed,denied",
    [
        (Mode.CONTROL, ["point", "pinch", "two_finger_pinch", "fist", "v_sign"],
         ["open_palm"]),
        (Mode.CHAT, ["open_palm", "point"], ["fist", "pinch"]),
        (Mode.TRANSFER, ["open_palm"], ["point", "fist"]),
        (Mode.PRESENTATION, ["point", "v_sign"], ["pinch", "fist"]),
    ],
)
def test_mode_gesture_gating(mode, allowed, denied):
    m = ModeMachine(mode)
    for g in allowed:
        assert m.allows(g), f"{mode} should allow {g}"
    for g in denied:
        assert not m.allows(g), f"{mode} should deny {g}"


def test_none_never_allowed():
    m = ModeMachine(Mode.CONTROL)
    assert not m.allows("none")


def test_all_gestures_known():
    assert {"point", "pinch", "two_finger_pinch", "fist", "v_sign",
            "open_palm", "thumbs_up", "thumbs_down", "circle", "none"} == GESTURES


def test_known_gestures_subset_of_mode_table():
    # Every gesture used by at least one mode must be defined.
    from app.control.modes import _ACTIVE

    used = {g for gs in _ACTIVE.values() for g in gs}
    assert used <= GESTURES


def test_repr():
    assert "control" in repr(ModeMachine(Mode.CONTROL))
