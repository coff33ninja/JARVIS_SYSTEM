"""Shared test fixtures for the recall memory subsystem."""

from __future__ import annotations

import numpy as np
import pytest

from app.agent.recall.config import EmbedderConfig
from app.agent.recall.store import MemoryStore
from app.perception.geometry import (  # noqa: F401  (landmark indices for helpers)
    INDEX_TIP,
    MIDDLE_TIP,
    THUMB_IP,
    THUMB_TIP,
)


@pytest.fixture
def store(tmp_path):
    with MemoryStore(tmp_path / "test_memory.db") as ms:
        yield ms


CONCEPT_SYNONYMS = {
    "file": ("file", "transfer", "throw", "catch", "send", "tablet"),
    "gesture": ("gesture", "hand", "wave", "flick", "cursor"),
    "voice": ("voice", "speak", "speech", "audio", "command"),
    "jarvis": ("jarvis", "assistant", "agent"),
}


class FakeEmbedder:
    """Duck-typed embedder: concept bag-of-words vectors, no network.

    Synonyms decouple semantic similarity from literal keyword overlap so
    tests can exercise semantic-only and hybrid paths.
    """

    def __init__(self):
        self.config = EmbedderConfig(enabled=True, model="fake-embed")
        self.vocab = tuple(CONCEPT_SYNONYMS)

    @property
    def available(self) -> bool:
        return True

    def embed(self, texts):
        single = isinstance(texts, str)
        inputs = [texts] if single else list(texts)
        out = [self._vector(t) for t in inputs]
        return out[0] if single else out

    def _vector(self, text: str) -> list[float]:
        text = text.lower()
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        for i, concept in enumerate(self.vocab):
            if any(syn in text for syn in CONCEPT_SYNONYMS[concept]):
                vec[i] = 1.0
        return vec.tolist()


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


# --------------------------------------------------------------------------- #
# Synthetic 21-landmark hands (Phase 1 geometry tests)
# --------------------------------------------------------------------------- #
#
# Landmarks are (x, y, z) normalized to [0,1], built from a simple skeleton:
# wrist at origin-ish, four fingers raycast upward, thumb on the +x side.
# `ext` controls how far each fingertip reaches (1.0 = extended, 0.0 = curled).

_WRIST = (0.50, 0.50, 0.0)

_MCP = {
    "index": (0.58, 0.60, 0.0),
    "middle": (0.50, 0.62, 0.0),
    "ring": (0.42, 0.60, 0.0),
    "pinky": (0.35, 0.57, 0.0),
}
_DIR = {
    "index": (-0.10, -1.0),
    "middle": (0.00, -1.0),
    "ring": (0.05, -1.0),
    "pinky": (0.10, -1.0),
}
_LEN = {"index": 0.10, "middle": 0.11, "ring": 0.10, "pinky": 0.09}
_THUMB = {"cmc": (0.62, 0.54, 0.0), "mcp": (0.66, 0.50, 0.0),
          "ip": (0.70, 0.46, 0.0), "tip": (0.73, 0.43, 0.0)}


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def make_hand(fingers=None, pinch="none", thumb_tip=None):
    """Build a synthetic 21-landmark hand.

    fingers: dict of finger -> ext in [0,1] (default: all extended).
    pinch:   "none" | "index" | "middle" — draws the thumb to that fingertip.
    """
    fingers = fingers or {"index": 1.0, "middle": 1.0, "ring": 1.0, "pinky": 1.0}
    lm = [_WRIST]
    # thumb joints (base positions, may be overwritten by pinch below)
    lm.append(_THUMB["cmc"])
    lm.append(_THUMB["mcp"])
    lm.append(_THUMB["ip"])
    lm.append(_THUMB["tip"])
    for name in ("index", "middle", "ring", "pinky"):
        mcp = _MCP[name]
        dx, dy = _DIR[name]
        ext = max(0.0, min(1.0, fingers.get(name, 1.0)))
        tip = (mcp[0] + dx * _LEN[name] * ext,
               mcp[1] + dy * _LEN[name] * ext, 0.0)
        pip = _lerp(mcp, tip, 0.35)
        dip = _lerp(mcp, tip, 0.62)
        lm.extend((mcp, pip, dip, tip))
    if pinch == "index":
        lm[THUMB_TIP] = lm[INDEX_TIP]
        lm[THUMB_IP] = _lerp(lm[THUMB_TIP], _THUMB["mcp"], 0.6)
    elif pinch == "middle":
        lm[THUMB_TIP] = lm[MIDDLE_TIP]
        lm[THUMB_IP] = _lerp(lm[THUMB_TIP], _THUMB["mcp"], 0.6)
    if thumb_tip is not None:
        lm[THUMB_TIP] = thumb_tip
    return lm


def open_hand():
    return make_hand()


def fist():
    # A real fist tucks the thumb across the palm, so the thumb reads as
    # curled too (otherwise it would classify as thumbs_up).
    return make_hand({"index": 0.0, "middle": 0.0, "ring": 0.0, "pinky": 0.0},
                     thumb_tip=(0.53, 0.52, 0.0))


def thumb_up_hand():
    # Thumb extended above the MCP (base fixture thumb already points up),
    # all four fingers curled.
    return make_hand({"index": 0.0, "middle": 0.0, "ring": 0.0, "pinky": 0.0})


def thumb_down_hand():
    # Thumb extended below the MCP (tip y > mcp y in screen space).
    return make_hand({"index": 0.0, "middle": 0.0, "ring": 0.0, "pinky": 0.0},
                     thumb_tip=(0.73, 0.58, 0.0))


def v_sign():
    return make_hand({"index": 1.0, "middle": 1.0, "ring": 0.0, "pinky": 0.0})


def point_hand():
    return make_hand({"index": 1.0, "middle": 0.0, "ring": 0.0, "pinky": 0.0})


def pinch_hand():
    return make_hand(fingers={"index": 1.0, "middle": 0.0, "ring": 0.0,
                              "pinky": 0.0}, pinch="index")


def two_pinch_hand():
    return make_hand(fingers={"index": 0.0, "middle": 1.0, "ring": 0.0,
                              "pinky": 0.0}, pinch="middle")
