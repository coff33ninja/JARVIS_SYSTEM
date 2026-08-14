"""Data-driven gesture bindings (ADR-011).

The gesture -> action mapping is a registry of stable action IDs bound to
gesture conditions, editable live from the HUD fist menu (04_GESTURE_VOCABULARY
"Gestures"). The registry enforces uniqueness — one enabled binding per
(gesture, mode) key — so collisions like the 5-finger select vs. spread are
resolvable at runtime instead of baked into code.

This is the data model plus the resolution `ControlPipeline` dispatch
consults (ADR-011): the seed bindings mirror today's hardcoded dispatch so
the registry can replace it without changing behavior. The Gestures menu
toggles a row on/off via ``set_gesture_enabled`` and rebinds a gesture to
another action via ``rebind``; classification thresholds tune in the
pipeline's Thresholds menu.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass
class GestureBinding:
    """One gesture condition bound to one action."""

    action_id: str  # stable action ID (e.g. "click.left")
    gesture: str  # pose / trajectory name (e.g. "pinch")
    mode: str | None = None  # None = any mode
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, str | None]:
        return (self.gesture, self.mode)


# Seed bindings mirroring the current hardcoded dispatch in pipeline.py.
# open_palm binds per-mode (catch in Transfer, release in Chat).
DEFAULT_BINDINGS: list[GestureBinding] = [
    GestureBinding("cursor.move", "point"),
    GestureBinding("click.left", "pinch"),
    GestureBinding("click.right", "two_finger_pinch"),
    GestureBinding("drag.toggle", "fist"),
    GestureBinding("scroll.tick", "v_sign"),
    GestureBinding("confirm", "thumbs_up", mode="chat"),
    GestureBinding("cancel", "thumbs_down", mode="chat"),
    GestureBinding("catch", "open_palm", mode="transfer"),
    GestureBinding("release", "open_palm", mode="chat"),
    GestureBinding("attention", "circle"),
    GestureBinding("mode.transfer_toggle", "spread"),
]


class GestureRegistry:
    """Ordered binding store with uniqueness enforcement per (gesture, mode)."""

    def __init__(self, bindings: list[GestureBinding] | None = None):
        # Copy, don't share: toggling a binding's enabled state must not leak
        # into another registry or the DEFAULT_BINDINGS module constant.
        self._bindings = [replace(b, params=dict(b.params)) for b in (bindings or [])]

    # ------------------------------------------------------------------ #
    # mutation
    # ------------------------------------------------------------------ #

    def add(self, binding: GestureBinding) -> bool:
        """Add a binding. False if its (gesture, mode) key is already claimed.

        A wildcard binding (mode=None) conflicts with any mode-specific
        binding of the same gesture, since resolve() precedence between them
        would be ambiguous.
        """
        for existing in self._bindings:
            if not existing.enabled:
                continue
            if existing.key == binding.key:
                return False
            if existing.gesture == binding.gesture and (
                existing.mode is None or binding.mode is None
            ):
                return False
        self._bindings.append(binding)
        return True

    def unbind(self, action_id: str) -> int:
        """Remove all bindings for an action ID. Returns count removed."""
        before = len(self._bindings)
        self._bindings = [b for b in self._bindings if b.action_id != action_id]
        return before - len(self._bindings)

    def set_enabled(self, action_id: str, enabled: bool) -> bool:
        """Toggle every binding for an action. False if the action is unknown."""
        found = False
        for binding in self._bindings:
            if binding.action_id == action_id:
                binding.enabled = enabled  # not frozen; ok
                found = True
        return found

    def set_gesture_enabled(self, gesture: str, enabled: bool) -> bool:
        """Toggle every binding for a gesture (Gestures menu row, ADR-011).

        False when the gesture is unknown, so a stale row can't silently no-op.
        """
        found = False
        for binding in self._bindings:
            if binding.gesture == gesture:
                binding.enabled = enabled
                found = True
        return found

    def gesture_enabled(self, gesture: str) -> bool:
        """True when any binding for the gesture is enabled."""
        return any(b.enabled for b in self._bindings if b.gesture == gesture)

    def rebind(
        self, gesture: str, action_id: str, mode: str | None = None
    ) -> tuple[bool, str]:
        """Point the ``(gesture, mode)`` binding at a new action.

        Returns ``(True, "")`` on success and ``(False, reason)`` when the key
        is already claimed by a different binding — the menu surfaces ``reason``
        as its in-menu collision warning. Rebinding to the current action is a
        no-op success. A missing binding is created (respecting the uniqueness
        invariant via ``add``), so a rebind can also mint a fresh gesture row.
        Enabled state and params are preserved when the binding already exists.
        """
        for binding in self._bindings:
            if binding.gesture != gesture or binding.mode != mode:
                continue
            if binding.action_id == action_id:
                return True, ""
            binding.action_id = action_id
            return True, ""
        ok = self.add(GestureBinding(action_id, gesture, mode=mode))
        if not ok:
            return False, f"'{gesture}' already bound in {mode or 'any mode'}"
        return True, ""

    # ------------------------------------------------------------------ #
    # query
    # ------------------------------------------------------------------ #

    def resolve(self, gesture: str, mode: str | None) -> str | None:
        """Action ID for a gesture in a mode, or None when unbound/disabled.

        Exact-mode bindings win over the mode=None wildcard for the same
        gesture. First match in insertion order wins.
        """
        wildcard: GestureBinding | None = None
        for binding in self._bindings:
            if binding.gesture != gesture or not binding.enabled:
                continue
            if binding.mode == mode:
                return binding.action_id
            if binding.mode is None and wildcard is None:
                wildcard = binding
        return wildcard.action_id if wildcard is not None else None

    def by_action(self, action_id: str) -> list[GestureBinding]:
        return [b for b in self._bindings if b.action_id == action_id]

    def by_gesture(self, gesture: str) -> list[GestureBinding]:
        return [b for b in self._bindings if b.gesture == gesture]

    def bindings(self) -> list[GestureBinding]:
        return list(self._bindings)

    def __len__(self) -> int:
        return len(self._bindings)
