"""Virtual mouse wrapper (pyautogui mocked, no OS calls)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.control.virtual_mouse import VirtualMouse


def test_move():
    v = VirtualMouse()
    v._gui = Mock()
    v.move(10, 20)
    v._gui.moveTo.assert_called_once_with(10, 20, duration=0.0)


def test_click_button_default():
    v = VirtualMouse()
    v._gui = Mock()
    v.click()
    v._gui.click.assert_called_once_with(button="left", clicks=1)


def test_right_click():
    v = VirtualMouse()
    v._gui = Mock()
    v.right_click()
    v._gui.click.assert_called_once_with(button="right", clicks=1)


def test_drag_sequence():
    v = VirtualMouse()
    v._gui = Mock()
    v.drag_start(1, 2)
    v._gui.mouseDown.assert_called_once_with(x=1, y=2, button="left")
    v.drag_to(3, 4)
    v._gui.moveTo.assert_called_once_with(3, 4, duration=0.0)
    v.drag_end()
    v._gui.mouseUp.assert_called_once_with(button="left")


def test_scroll():
    v = VirtualMouse()
    v._gui = Mock()
    v.scroll(-3)
    v._gui.scroll.assert_called_once_with(-3)


def test_hotkey():
    v = VirtualMouse()
    v._gui = Mock()
    v.hotkey("alt", "tab")
    v._gui.hotkey.assert_called_once_with("alt", "tab")


def test_position():
    v = VirtualMouse()
    v._gui = Mock()
    v._gui.position.return_value = (5, 6)
    assert v.position() == (5, 6)


def test_available_when_import_fails(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "pyautogui":
            raise ImportError("pyautogui not importable")
        return real_import(name, *a, **kw)

    with patch("builtins.__import__", fake_import):
        v = VirtualMouse()
        assert v.available is False


def test_available_when_ok():
    v = VirtualMouse()
    v._gui = Mock()
    assert v.available is True


@pytest.mark.parametrize("duration", [0.0, 0.1, 0.5])
def test_move_duration_configurable(duration):
    v = VirtualMouse(move_duration=duration)
    v._gui = Mock()
    v.move(0, 0)
    v._gui.moveTo.assert_called_once_with(0, 0, duration=duration)


def test_failsafe_and_pause_set_on_init():
    import pyautogui

    original_pause = pyautogui.PAUSE
    original_failsafe = pyautogui.FAILSAFE
    try:
        v = VirtualMouse(failsafe=False)
        v._pg()
        assert pyautogui.PAUSE == 0.0
        assert pyautogui.FAILSAFE is False
    finally:
        pyautogui.PAUSE = original_pause
        pyautogui.FAILSAFE = original_failsafe
