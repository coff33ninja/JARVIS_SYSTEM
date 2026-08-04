"""Hotkey routing for the live control loop (_StopKey in app/main.py)."""

from __future__ import annotations


class _FakeKey:
    """Stand-in for a pynput Key.

    Special keys (Key.esc, Key.f3) have no ``char`` attribute — accessing it
    raises AttributeError, so ``hasattr(key, "char")`` is False. Character
    keys expose ``char`` (e.g. "q").
    """

    _NO_CHAR = object()

    def __init__(self, name: str, char: object = _NO_CHAR):
        self._name = name
        self._char = char

    @property
    def char(self):
        if self._char is _FakeKey._NO_CHAR:
            raise AttributeError("char")
        return self._char

    def __str__(self) -> str:
        return self._name


def make_stop(**callbacks):
    from app.main import _StopKey

    stop = _StopKey(**callbacks)
    stop._listener = None  # never touch the real OS listener in tests
    return stop


def test_esc_quits():
    stop = make_stop()
    stop._on_press(_FakeKey("Key.esc"))
    assert stop.triggered


def test_q_quits():
    stop = make_stop()
    stop._on_press(_FakeKey("q", char="q"))
    assert stop.triggered


def test_f2_toggles_idle_control():
    calls = []
    stop = make_stop(on_mode_toggle=lambda: calls.append("toggle"))
    stop._on_press(_FakeKey("Key.f2"))
    assert calls == ["toggle"]
    assert not stop.triggered


def test_f3_toggles_presentation():
    calls = []
    stop = make_stop(on_present_toggle=lambda: calls.append("present"))
    stop._on_press(_FakeKey("Key.f3"))
    assert calls == ["present"]


def test_f4_toggles_keyboard():
    calls = []
    stop = make_stop(on_keyboard_toggle=lambda: calls.append("osk"))
    stop._on_press(_FakeKey("Key.f4"))
    assert calls == ["osk"]


def test_f5_to_f10_route_media():
    calls = []
    stop = make_stop(on_media=calls.append)
    for key, name in [("Key.f5", "play_pause"), ("Key.f6", "next"),
                      ("Key.f7", "previous"), ("Key.f8", "volume_mute"),
                      ("Key.f9", "volume_down"), ("Key.f10", "volume_up")]:
        stop._on_press(_FakeKey(key))
    assert calls == ["play_pause", "next", "previous", "volume_mute",
                     "volume_down", "volume_up"]


def test_unmapped_key_is_inert():
    stop = make_stop()
    stop._on_press(_FakeKey("Key.home"))
    assert not stop.triggered
