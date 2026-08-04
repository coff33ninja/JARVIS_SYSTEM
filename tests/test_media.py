"""Media / volume key controller (pynput mocked, no OS calls)."""

from __future__ import annotations

from unittest.mock import Mock, patch

from app.control.virtual_keyboard import MediaController


def _controller():
    ctrl = MediaController()
    ctrl._controller = Mock()
    key_mod = Mock()
    key_mod.media_play_pause = "play"
    key_mod.media_next = "next"
    key_mod.media_previous = "prev"
    key_mod.media_volume_mute = "mute"
    key_mod.media_volume_up = "up"
    key_mod.media_volume_down = "down"
    ctrl._key = key_mod
    return ctrl


def test_action_taps_expected_key():
    ctrl = _controller()
    ctrl.action("play_pause")
    ctrl._controller.tap.assert_called_once_with("play")
    ctrl.action("next")
    ctrl._controller.tap.assert_called_with("next")
    ctrl.action("previous")
    ctrl._controller.tap.assert_called_with("prev")
    ctrl.action("volume_mute")
    ctrl._controller.tap.assert_called_with("mute")


def test_action_unknown_name_is_ignored():
    ctrl = _controller()
    ctrl.action("bogus")
    ctrl._controller.tap.assert_not_called()


def test_action_missing_key_attribute_is_ignored():
    ctrl = _controller()
    del ctrl._key.media_volume_up  # simulate a platform without this key
    ctrl.action("volume_up")
    ctrl._controller.tap.assert_not_called()


def test_available_when_pynput_ok(monkeypatch):
    ctrl = MediaController()
    ctrl._controller = Mock()
    assert ctrl.available is True


def test_available_when_pynput_fails(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "pynput.keyboard":
            raise ImportError("no pynput")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert MediaController().available is False


def test_all_media_actions_have_keys():
    from app.control.virtual_keyboard import MEDIA_KEYS

    assert set(MEDIA_KEYS) == {
        "play_pause", "next", "previous", "stop",
        "volume_up", "volume_down", "volume_mute",
    }
