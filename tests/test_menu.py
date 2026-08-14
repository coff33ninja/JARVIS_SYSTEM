"""Radial fist-menu state machine (app/control/menu.py)."""

from __future__ import annotations

from app.control.menu import (
    MenuCategory,
    MenuItem,
    MenuState,
    RadialMenu,
    pie_index,
)


def sample_menu() -> RadialMenu:
    return RadialMenu([
        MenuCategory("screens", "Screens", items=[
            MenuItem("monitor_1", "Monitor 1", action_id="screen.1"),
            MenuItem("monitor_2", "Monitor 2", action_id="screen.2"),
        ]),
        MenuCategory("modes", "Modes", items=[
            MenuItem("control", "Control", action_id="mode.control"),
            MenuItem("chat", "Chat", action_id="mode.chat"),
        ]),
        MenuCategory("empty", "Empty"),  # hidden (no items)
    ])


def test_pie_index_top_is_zero_clockwise():
    assert pie_index(0.0, -1.0, 4) == 0  # north = top
    assert pie_index(1.0, 0.0, 4) == 1   # east
    assert pie_index(0.0, 1.0, 4) == 2   # south
    assert pie_index(-1.0, 0.0, 4) == 3  # west


def test_pie_index_guards():
    assert pie_index(0.5, 0.5, 0) == 0
    assert pie_index(0.5, 0.5, 1) == 0


def test_menu_opens_closed_only():
    menu = sample_menu()
    assert menu.open() is True
    assert menu.open() is False  # already open
    assert menu.state is MenuState.OPEN


def test_open_categories_hide_empty():
    menu = sample_menu()
    assert [c.id for c in menu.open_categories] == ["screens", "modes"]


def test_select_and_confirm_category_item():
    menu = sample_menu()
    menu.open()
    assert menu.select_category(0.0, -1.0) == 0
    assert menu.item_idx is None
    assert menu.select_item(0.0, 1.0) == 1  # second leaf south (2 slices: top/bottom)
    item = menu.confirm()
    assert item is not None and item.id == "monitor_2"
    assert menu.state is MenuState.CONFIRMED


def test_confirm_requires_open_and_selection():
    menu = sample_menu()
    assert menu.confirm() is None  # closed
    menu.open()
    assert menu.confirm() is None  # open but nothing selected


def test_cancel_closes_only_when_open():
    menu = sample_menu()
    assert menu.cancel() is False  # closed
    menu.open()
    assert menu.cancel() is True
    assert menu.state is MenuState.CLOSED


def test_confirm_closes_and_resets():
    menu = sample_menu()
    menu.open()
    menu.select_category(0.0, -1.0)
    menu.select_item(0.0, 1.0)
    menu.confirm()
    assert menu.open() is False  # CONFIRMED blocks reopening until close()
    menu.close()
    assert menu.open() is True


def test_item_count_capped_at_research_limit():
    # 16_INTERACTION_RESEARCH: radial breadth above 8 hurts accuracy.
    assert RadialMenu.MAX_ITEMS == 8
