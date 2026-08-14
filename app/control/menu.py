"""Fist-menu model (Phase 2 modifier hand, 04_GESTURE_VOCABULARY).

The secondary hand's fist (held >= ``menu_hold_ms``) opens a radial menu on
the HUD; the primary hand's reticle position drives the highlight, a pinch
confirms, an open palm cancels. This module is the pure state machine — the
trigger (pipeline), rendering (MenuEvent -> ``hud/index.html``), and the
Gestures rows (ADR-011 toggle via the registry) are wired.

Menu geometry follows 16_INTERACTION_RESEARCH.md: radial/pie layout, capped
at 8 items per layer, two layers (categories -> items).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class MenuState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    CONFIRMED = "confirmed"


@dataclass
class MenuItem:
    """One selectable item (leaf) inside a category."""

    id: str
    label: str
    action_id: str | None = None
    params: dict = field(default_factory=dict)
    checked: bool = False  # toggle rows (Gestures) render a checkmark
    submenu: list[MenuItem] | None = None  # confirming this item pushes it (3rd layer)


@dataclass
class MenuCategory:
    """First-level pie slice holding leaf items."""

    id: str
    label: str
    items: list[MenuItem] = field(default_factory=list)


def pie_index(dx: float, dy: float, n: int) -> int:
    """Index of the pie sector containing the (dx, dy) offset from center.

    Sector 0 is at the top, numbering clockwise; ``n`` slices cover 360
    degrees. Guards n <= 0 (returns 0) and n == 1 (single item).
    """
    if n <= 1:
        return 0
    ang = math.degrees(math.atan2(dy, dx))  # -180..180, 0 = east
    angle_from_top = (ang + 90.0) % 360.0  # 0 = top, clockwise positive
    return int(angle_from_top / 360.0 * n) % n


class RadialMenu:
    """Two-layer radial menu with optional item submenus (3rd layer).

    Categories are the first layer; their leaf items are the second. Any item
    may carry a ``submenu`` — confirming it ``push()``es that list as the new
    inner ring (ADR-011 rebind / threshold pickers) and ``back()`` pops it.
    While a submenu is active the category ring is hidden; the inner ring
    shows the submenu items plus a "Back" item supplied by the builder.
    """

    MAX_ITEMS = 8  # research: breadth above 8 hurts accuracy (16_INTERACTION_RESEARCH)

    def __init__(self, categories: list[MenuCategory]):
        self.categories = categories
        self.state = MenuState.CLOSED
        self.category_idx = 0
        self.item_idx: int | None = None
        self._stack: list[list[MenuItem]] = []  # active submenus, outer -> inner

    @property
    def in_submenu(self) -> bool:
        return bool(self._stack)

    def open(self) -> bool:
        """Open the menu (cancels any previous CONFIRMED state)."""
        if self.state != MenuState.CLOSED:
            return False
        self.state = MenuState.OPEN
        self.category_idx = 0
        self.item_idx = None
        self._stack = []
        return True

    def close(self) -> None:
        self.state = MenuState.CLOSED
        self.item_idx = None
        self._stack = []

    @property
    def open_categories(self) -> list[MenuCategory]:
        """Categories with items; the menu hides empty slices."""
        return [c for c in self.categories if c.items]

    def select_category(self, dx: float, dy: float) -> int | None:
        """Highlight the category under the (dx, dy) reticle offset.

        Ignored while a submenu is active — only the inner ring is live then.
        """
        if self.in_submenu:
            return None
        cats = self.open_categories
        if not cats:
            return None
        self.category_idx = pie_index(dx, dy, len(cats))
        self.item_idx = None
        return self.category_idx

    def select_item(self, dx: float, dy: float) -> int | None:
        """Highlight a leaf item: the active submenu, else the current category."""
        if self.in_submenu:
            items = self._stack[-1]
            if not items:
                return None
            self.item_idx = pie_index(dx, dy, len(items))
            return self.item_idx
        category = self.open_categories[self.category_idx]
        if not category.items:
            return None
        self.item_idx = pie_index(dx, dy, len(category.items))
        return self.item_idx

    def active_items(self) -> list[MenuItem]:
        """Items currently selectable (active submenu, else highlighted category)."""
        if self.in_submenu:
            return self._stack[-1]
        cats = self.open_categories
        if not cats or not 0 <= self.category_idx < len(cats):
            return []
        return cats[self.category_idx].items

    def confirm(self) -> MenuItem | None:
        """Confirm the highlighted leaf (submenu-aware). Caller routes the item."""
        if self.state != MenuState.OPEN or self.item_idx is None:
            return None
        if self.in_submenu:
            items = self._stack[-1]
            if not 0 <= self.item_idx < len(items):
                return None
            item = items[self.item_idx]
            self.state = MenuState.CONFIRMED
            return item
        category = self.open_categories[self.category_idx]
        if not 0 <= self.item_idx < len(category.items):
            return None
        item = category.items[self.item_idx]
        self.state = MenuState.CONFIRMED
        return item

    def push(self, items: list[MenuItem]) -> bool:
        """Enter a submenu (or deepen an existing one). Requires an open menu."""
        if self.state == MenuState.CLOSED:
            return False
        if not items:
            return False
        self._stack.append(list(items))
        self.state = MenuState.OPEN
        self.item_idx = None
        return True

    def back(self) -> bool:
        """Pop one submenu level. False when already at the category layer."""
        if not self.in_submenu:
            return False
        self._stack.pop()
        self.state = MenuState.OPEN
        self.item_idx = None
        return True

    def reopen(self) -> None:
        """Return to OPEN after a CONFIRMED flash (stay-open confirm routes).

        ``confirm`` marks the menu CONFIRMED so ordinary leaf clicks can close
        and flash; submenu/threshold routes call this to keep interacting.
        """
        if self.state == MenuState.CONFIRMED:
            self.state = MenuState.OPEN

    def cancel(self) -> bool:
        """Cancel and close. True when a menu was actually open."""
        if self.state != MenuState.OPEN:
            return False
        self.state = MenuState.CLOSED
        self.item_idx = None
        self._stack = []
        return True
