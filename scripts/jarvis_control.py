"""Phase 1 live control: move the cursor with your index finger.

Exit criteria driver for Phase 1 (02_PROJECT_PLAN): "reliably move cursor
and click for 5+ minutes without tracking loss".

Gestures (Control mode, matches 04_GESTURE_VOCABULARY):
    point            index finger extended -> cursor follows index tip
    pinch            thumb + index tip     -> left click
    two-finger pinch thumb + middle tip    -> right click
    fist             all fingers curled    -> drag (hold = drag, release = drop)
    V-sign           index + middle        -> scroll (move hand up/down)

Usage:
    uv run python scripts/jarvis_control.py [--no-hud]

Exit: press ESC or q (or Ctrl+C).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import main as run_main

if __name__ == "__main__":
    sys.exit(run_main())
