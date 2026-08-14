"""Mode machine: which gestures are active, and when.

Modes gate the control layer so gestures only act in the right context
(04_GESTURE_VOCABULARY "Mode System"). Phase 1 ships Idle/Control plus the
transition table; Chat/Transfer/Presentation arrive with their feature
layers but are already defined so the enum stays stable.
"""

from __future__ import annotations

from enum import Enum


class Mode(Enum):
    IDLE = "idle"
    CONTROL = "control"
    CHAT = "chat"
    TRANSFER = "transfer"
    PRESENTATION = "presentation"


# Triggers the system understands today. Voice/hotkey triggers wire into the
# same table in Phase 2; custom gestures can be added the same way.
WAKE = "wake"              # any tracked hand in Idle mode
HOTKEY = "hotkey"          # keyboard override
VOICE = "voice"            # "Jarvis, transfer mode"
TRANSFER_GESTURE = "transfer_gesture"      # Phase 2 two-hand spread
PRESENT_GESTURE = "present_gesture"        # Phase 2 presentation mode gesture

_TRANSITIONS: dict[tuple[Mode, str], Mode] = {
    (Mode.IDLE, WAKE): Mode.CONTROL,
    (Mode.CONTROL, HOTKEY): Mode.IDLE,
    (Mode.IDLE, HOTKEY): Mode.CONTROL,
    (Mode.CONTROL, VOICE): Mode.CHAT,
    (Mode.CHAT, VOICE): Mode.CONTROL,
    (Mode.CONTROL, TRANSFER_GESTURE): Mode.TRANSFER,
    (Mode.TRANSFER, TRANSFER_GESTURE): Mode.CONTROL,
    (Mode.CONTROL, PRESENT_GESTURE): Mode.PRESENTATION,
    (Mode.PRESENTATION, PRESENT_GESTURE): Mode.CONTROL,
}

# Every gesture the system can classify. "circle" is a trajectory gesture
# (index-trace attention) gated separately from mode posture — it acts in any
# mode, so it does not appear in the per-mode _ACTIVE table.
GESTURES = {
    "point", "pinch", "two_finger_pinch", "fist",
    "v_sign", "open_palm", "thumbs_up", "thumbs_down", "circle", "none",
}

# Which gestures act per mode. "none" is always inert.
_ACTIVE: dict[Mode, set[str]] = {
    Mode.IDLE: set(),
    Mode.CONTROL: {"point", "pinch", "two_finger_pinch", "fist", "v_sign"},
    Mode.CHAT: {"open_palm", "point", "thumbs_up", "thumbs_down"},
    Mode.TRANSFER: {"open_palm"},
    Mode.PRESENTATION: {"point", "v_sign"},
}


class ModeMachine:
    """Stateful mode holder with explicit, testable transitions."""

    def __init__(self, initial: Mode = Mode.IDLE):
        self.mode = initial

    def transition(self, trigger: str) -> Mode:
        """Apply a transition; unknown or invalid triggers are no-ops."""
        self.mode = _TRANSITIONS.get((self.mode, trigger), self.mode)
        return self.mode

    def goto(self, target: Mode) -> Mode:
        """Jump directly to a target mode (menu-driven), bypassing the table.

        Unlike ``transition`` this does not validate a trigger — used by the
        fist-menu Modes category where any mode is reachable from any mode.
        """
        if isinstance(target, Mode):
            self.mode = target
        return self.mode

    def active_gestures(self) -> set[str]:
        return _ACTIVE.get(self.mode, set())

    def allows(self, gesture: str) -> bool:
        """True if ``gesture`` may act in the current mode."""
        if gesture == "none":
            return False
        return gesture in self.active_gestures()

    def __repr__(self) -> str:
        return f"ModeMachine(mode={self.mode.value})"
