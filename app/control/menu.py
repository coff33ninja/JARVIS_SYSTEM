"""Fist-menu model (Phase 2 modifier hand, 04_GESTURE_VOCABULARY).

The secondary hand's fist (held >= ``menu_hold_ms``) opens a radial menu on
the HUD; the primary hand's reticle position drives the highlight, a pinch
confirms, an open palm cancels. This module is the pure state machine — the
trigger (pipeline) is wired; rendering (HUD) and the action execution
(registry) land in later slices.

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
    ang = math.degrees(math.atan2(dy, dx))        # -180..180, 0 = east
    angle_from_top = (ang + 90.0) % 360.0         # 0 = top, clockwise positive
    return int(angle_from_top / 360.0 * n) % n


class RadialMenu:
    """Two-layer radial menu: pick a category, then a leaf item."""

    MAX_ITEMS = 8  # research: breadth above 8 hurts accuracy (16_INTERACTION_RESEARCH)

    def __init__(self, categories: list[MenuCategory]):
        self.categories = categories
        self.state = MenuState.CLOSED
        self.category_idx = 0
        self.item_idx: int | None = None

    def open(self) -> bool:
        """Open the menu (cancels any previous CONFIRMED state)."""
        if self.state != MenuState.CLOSED:
            return False
        self.state = MenuState.OPEN
        self.category_idx = 0
        self.item_idx = None
        return True

    def close(self) -> None:
        self.state = MenuState.CLOSED
        self.item_idx = None

    @property
    def open_categories(self) -> list[MenuCategory]:
        """Categories with items; the menu hides empty slices."""
        return [c for c in self.categories if c.items]

    def select_category(self, dx: float, dy: float) -> int | None:
        """Highlight the category under the (dx, dy) reticle offset."""
        cats = self.open_categories
        if not cats:
            return None
        self.category_idx = pie_index(dx, dy, len(cats))
        self.item_idx = None
        return self.category_idx

    def select_item(self, dx: float, dy: float) -> int | None:
        """Highlight a leaf item inside the current category."""
        category = self.open_categories[self.category_idx]
        if not category.items:
            return None
        self.item_idx = pie_index(dx, dy, len(category.items))
        return self.item_idx

    def confirm(self) -> MenuItem | None:
        """Confirm the highlighted leaf; returns it and closes the menu."""
        if self.state != MenuState.OPEN or self.item_idx is None:
            return None
        category = self.open_categories[self.category_idx]
        if self.item_idx >= len(category.items):
            return None
        item = category.items[self.item_idx]
        self.state = MenuState.CONFIRMED
        return item

    def cancel(self) -> bool:
        """Cancel and close. True when a menu was actually open."""
        if self.state != MenuState.OPEN:
            return False
        self.state = MenuState.CLOSED
        self.item_idx = None
        return True
