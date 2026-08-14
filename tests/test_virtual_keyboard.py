"""Virtual keyboard (pyautogui + osk.exe mocked, no OS calls)."""

from __future__ import annotations

from unittest.mock import Mock, patch

from app.control.virtual_keyboard import VirtualKeyboard


def test_type_text():
    v = VirtualKeyboard()
    v._gui = Mock()
    v.type_text("hello")
    v._gui.write.assert_called_once_with("hello", interval=0.0)


def test_hotkey():
    v = VirtualKeyboard()
    v._gui = Mock()
    v.hotkey("ctrl", "c")
    v._gui.hotkey.assert_called_once_with("ctrl", "c")


def test_press():
    v = VirtualKeyboard()
    v._gui = Mock()
    v.press("enter")
    v._gui.press.assert_called_once_with("enter")


def test_osk_unavailable_off_windows():
    with patch("app.control.virtual_keyboard.platform.system", return_value="Linux"):
        v = VirtualKeyboard()
        assert v.osk_available is False
        assert v.toggle_osk() is False


def test_osk_toggle_show_and_hide(monkeypatch):
    monkeypatch.setattr(
        "app.control.virtual_keyboard.platform.system", lambda: "Windows"
    )
    monkeypatch.setattr("app.control.virtual_keyboard.OSK", "osk.exe")

    calls = {"list": [], "kill": [], "popen": []}

    def fake_run(argv, *a, **kw):
        if "taskkill" in argv:
            calls["kill"].append(1)
        else:
            calls["list"].append(1)
        return Mock(stdout="osk.exe")

    monkeypatch.setattr("app.control.virtual_keyboard.subprocess.run", fake_run)
    monkeypatch.setattr(
        "app.control.virtual_keyboard.subprocess.Popen",
        lambda *a, **kw: calls["popen"].append(1),
    )

    v = VirtualKeyboard()
    # Running -> toggle hides it.
    assert v.osk_running() is True
    assert v.toggle_osk() is False
    assert calls["kill"]
    # Not running -> toggle shows it.
    monkeypatch.setattr(
        "app.control.virtual_keyboard.subprocess.run",
        lambda argv, *a, **kw: Mock(stdout="nothing"),
    )
    assert v.osk_running() is False
    assert v.toggle_osk() is True
    assert calls["popen"]
