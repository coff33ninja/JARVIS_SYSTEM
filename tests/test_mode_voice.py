"""Voice -> mode routing: phrase parsing and BFS transitions."""

from __future__ import annotations

from app.control.mode_voice import (
    handle_mode_command,
    parse_mode_command,
    route_to,
)
from app.control.modes import Mode, ModeMachine


def test_parse_mode_commands():
    assert parse_mode_command("chat mode") is Mode.CHAT
    assert parse_mode_command("open chat") is Mode.CHAT
    assert parse_mode_command("transfer mode") is Mode.TRANSFER
    assert parse_mode_command("presentation mode") is Mode.PRESENTATION
    assert parse_mode_command("present slides") is Mode.PRESENTATION
    assert parse_mode_command("control mode") is Mode.CONTROL
    assert parse_mode_command("go idle") is Mode.IDLE


def test_parse_ignores_non_mode_commands():
    assert parse_mode_command("open the project folder") is None
    assert parse_mode_command("what time is it") is None


def test_parse_case_insensitive():
    assert parse_mode_command("CHAT MODE") is Mode.CHAT


def test_presentation_wins_over_shorter_substrings():
    assert parse_mode_command("presentation mode") is Mode.PRESENTATION


def test_route_control_to_chat_and_back():
    m = ModeMachine(Mode.CONTROL)
    route_to(m, Mode.CHAT)
    assert m.mode is Mode.CHAT
    route_to(m, Mode.CONTROL)
    assert m.mode is Mode.CONTROL


def test_route_chat_requires_control_first():
    m = ModeMachine(Mode.TRANSFER)
    route_to(m, Mode.CHAT)
    assert m.mode is Mode.CHAT  # spread-toggle then voice-toggle


def test_route_from_idle_to_presentation():
    m = ModeMachine(Mode.IDLE)
    route_to(m, Mode.PRESENTATION)
    assert m.mode is Mode.PRESENTATION  # wake, then present-toggle


def test_route_is_idempotent():
    m = ModeMachine(Mode.CHAT)
    route_to(m, Mode.CHAT)
    assert m.mode is Mode.CHAT


def test_handle_mode_command_returns_confirmation():
    m = ModeMachine(Mode.CONTROL)
    reply = handle_mode_command("chat mode", m)
    assert reply == "Chat mode."
    assert m.mode is Mode.CHAT


def test_handle_mode_command_returns_none_for_non_mode():
    m = ModeMachine(Mode.CONTROL)
    assert handle_mode_command("open settings", m) is None
    assert m.mode is Mode.CONTROL  # untouched
