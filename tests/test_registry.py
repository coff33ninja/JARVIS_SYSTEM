"""Gesture binding registry (ADR-011, app/control/registry.py)."""

from __future__ import annotations

from app.control.registry import (
    DEFAULT_BINDINGS,
    GestureBinding,
    GestureRegistry,
)


def test_default_bindings_resolve():
    r = GestureRegistry(DEFAULT_BINDINGS)
    assert r.resolve("pinch", None) == "click.left"
    assert r.resolve("point", None) == "cursor.move"
    assert r.resolve("spread", None) == "mode.transfer_toggle"
    assert r.resolve("circle", None) == "attention"


def test_mode_specific_binding_beats_wildcard():
    r = GestureRegistry(DEFAULT_BINDINGS)
    # open_palm is mode-bound: catch in transfer, release in chat.
    assert r.resolve("open_palm", "transfer") == "catch"
    assert r.resolve("open_palm", "chat") == "release"
    # Unknown mode -> no wildcard binding for open_palm.
    assert r.resolve("open_palm", "idle") is None


def test_unbound_gesture_returns_none():
    r = GestureRegistry(DEFAULT_BINDINGS)
    assert r.resolve("thumbs_up", None) is None  # only bound in chat
    assert r.resolve("fist", "idle") == "drag.toggle"  # wildcard works in any mode


def test_add_rejects_duplicate_key():
    r = GestureRegistry()
    assert r.add(GestureBinding("click.left", "pinch")) is True
    assert r.add(GestureBinding("click.right", "pinch")) is False


def test_add_rejects_wildcard_vs_mode_conflict():
    r = GestureRegistry()
    assert r.add(GestureBinding("click.left", "pinch", mode=None)) is True
    assert r.add(GestureBinding("click.left", "pinch", mode="chat")) is False
    r2 = GestureRegistry()
    assert r2.add(GestureBinding("click.left", "pinch", mode="chat")) is True
    assert r2.add(GestureBinding("click.left", "pinch")) is False


def test_add_allows_same_gesture_in_different_modes():
    r = GestureRegistry()
    assert r.add(GestureBinding("a", "open_palm", mode="chat")) is True
    assert r.add(GestureBinding("b", "open_palm", mode="transfer")) is True


def test_unbind_removes_all_for_action():
    r = GestureRegistry()
    r.add(GestureBinding("a", "pinch"))
    r.add(GestureBinding("a", "fist", mode="chat"))
    assert r.unbind("a") == 2
    assert len(r) == 0
    assert r.unbind("a") == 0


def test_set_enabled_disables_resolution():
    r = GestureRegistry(DEFAULT_BINDINGS)
    assert r.set_enabled("click.left", False) is True
    assert r.resolve("pinch", None) is None
    assert r.set_enabled("click.left", True) is True
    assert r.resolve("pinch", None) == "click.left"


def test_set_enabled_unknown_action():
    r = GestureRegistry()
    assert r.set_enabled("nope", False) is False


def test_duplicate_register_with_disabled_is_allowed():
    # A disabled binding doesn't claim the key.
    r = GestureRegistry()
    r.add(GestureBinding("a", "pinch", enabled=False))
    assert r.add(GestureBinding("b", "pinch")) is True


def test_rebind_swaps_wildcard_action_and_preserves_enabled():
    r = GestureRegistry(DEFAULT_BINDINGS)
    ok, reason = r.rebind("pinch", "cancel")
    assert ok and reason == ""
    assert r.resolve("pinch", None) == "cancel"
    # Pinch bindings for other modes are untouched.
    assert r.resolve("pinch", "chat") == "cancel"  # wildcard covers it


def test_rebind_to_current_action_is_noop_success():
    r = GestureRegistry(DEFAULT_BINDINGS)
    ok, reason = r.rebind("pinch", "click.left")
    assert ok and reason == ""


def test_rebind_rejects_claimed_mode_key():
    r = GestureRegistry(DEFAULT_BINDINGS)
    # pinch already owns the wildcard; a mode-specific rebind onto a second
    # action must be refused so resolve() precedence stays unambiguous.
    ok, reason = r.rebind("pinch", "scroll.tick", mode="chat")
    assert not ok
    assert "already bound" in reason
    assert r.resolve("pinch", "chat") == "click.left"


def test_rebind_mints_binding_when_key_free():
    r = GestureRegistry(DEFAULT_BINDINGS)
    ok, reason = r.rebind("wave", "click.left")  # unbound gesture, key is free
    assert ok and reason == ""
    assert r.resolve("wave", None) == "click.left"
    assert len(r) == len(DEFAULT_BINDINGS) + 1


def test_set_gesture_enabled_flips_all_bindings_for_gesture():
    r = GestureRegistry(DEFAULT_BINDINGS)
    # open_palm binds per-mode (catch + release): both flip together.
    assert r.gesture_enabled("open_palm") is True
    assert r.set_gesture_enabled("open_palm", False) is True
    assert r.gesture_enabled("open_palm") is False
    assert r.resolve("open_palm", "transfer") is None
    assert r.resolve("open_palm", "chat") is None
    assert r.set_gesture_enabled("open_palm", True) is True
    assert r.resolve("open_palm", "transfer") == "catch"
    assert r.set_gesture_enabled("nope", True) is False  # unknown gesture


def test_by_gesture_lists_bindings():
    r = GestureRegistry(DEFAULT_BINDINGS)
    assert [b.action_id for b in r.by_gesture("open_palm")] == ["catch", "release"]
    assert r.by_gesture("nope") == []
