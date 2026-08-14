"""MediaPipe Hand Landmarker wrapper + on-demand model download.

The ``hand_landmarker.task`` model (~10 MB) is fetched to ``models/`` on
first run if missing — same auto-install pattern as STT/TTS/LLM in Phase 3
(08_ASSETS.md management rule 1: models are never committed).

The tracker runs in VIDEO mode so MediaPipe can use temporal tracking across
frames, which steadies landmarks for gesture work. Output is normalised to a
plain dataclass (list of 21 ``(x, y, z)`` tuples per hand) so downstream
geometry/cursor code never touches MediaPipe types — swap-friendly and
unit-testable.
"""

from __future__ import annotations

import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
DEFAULT_MODEL_PATH = Path("models") / "hand_landmarker.task"


@dataclass
class HandTrackingResult:
    """Normalized hand landmarks for one frame.

    ``hands`` is a list of hand records (one per detected hand); each record
    has 21 ``(x, y, z)`` landmarks normalized to [0, 1].
    """

    hands: list[list[tuple[float, float, float]]] | None = None
    handedness: list[str] | None = None

    @property
    def detected(self) -> bool:
        return bool(self.hands)


def download_model(
    url: str = DEFAULT_MODEL_URL, dest: str | Path = DEFAULT_MODEL_PATH
) -> bool:
    """Stream the task model to ``dest``. True on success (no raise)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as out:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
        tmp.replace(dest)
        logger.info("downloaded hand landmarker model -> %s", dest)
        return True
    except Exception as exc:
        logger.warning("model download failed: %s", exc)
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return False


class HandLandmarkerTracker:
    """Lazy MediaPipe Hand Landmarker over a webcam feed.

    Construction never touches MediaPipe; the runtime is built on first
    ``process()`` call, so missing hardware/models fail gracefully instead of
    crashing the app (Graceful degradation principle).
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        num_hands: int = 1,
        min_hand_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        auto_download: bool = True,
    ):
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.num_hands = num_hands
        self.min_hand_confidence = min_hand_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.min_presence_confidence = min_presence_confidence
        self.auto_download = auto_download
        self._landmarker = None
        self._mp = None
        self._ts = 0

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #

    def ensure_model(self) -> bool:
        """Make sure the task model exists, downloading if allowed."""
        if self.model_path.exists():
            return True
        if self.auto_download:
            return download_model(dest=self.model_path)
        return False

    def _build(self):
        if self._landmarker is not None:
            return self._landmarker
        if not self.ensure_model():
            logger.warning("hand landmarker model missing; tracking disabled")
            return None
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError:  # pragma: no cover - dep declared in pyproject
            logger.warning("mediapipe not installed; tracking disabled")
            return None
        try:
            base = mp_python.BaseOptions(
                model_asset_path=str(self.model_path.resolve())
            )
            options = vision.HandLandmarkerOptions(
                base_options=base,
                running_mode=vision.RunningMode.VIDEO,
                num_hands=self.num_hands,
                min_hand_detection_confidence=self.min_hand_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                min_hand_presence_confidence=self.min_presence_confidence,
            )
            self._landmarker = vision.HandLandmarker.create_from_options(options)
        except Exception as exc:  # pragma: no cover - runtime/model dependent
            logger.warning("failed to create HandLandmarker: %s", exc)
            return None
        self._mp = mp
        return self._landmarker

    @property
    def available(self) -> bool:
        return self._build() is not None

    def process(self, frame_bgr) -> HandTrackingResult:
        """Run one frame (BGR numpy array). Returns landmarks or empty result."""
        landmarker = self._build()
        if landmarker is None or frame_bgr is None:
            return HandTrackingResult()
        mp = self._mp
        try:
            rgb = frame_bgr[:, :, ::-1]  # BGR -> RGB
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            self._ts += 33  # ~30fps nominal timestamp; monotonic increments
            result = landmarker.detect_for_video(img, self._ts)
        except Exception as exc:  # pragma: no cover - runtime dependent
            logger.warning("hand tracking failed on frame: %s", exc)
            return HandTrackingResult()

        hands: list[list[tuple[float, float, float]]] = []
        for lmks in result.hand_landmarks or []:
            hands.append([(lm.x, lm.y, lm.z) for lm in lmks])
        handedness = [
            c.category_name for hand in (result.handedness or []) for c in hand
        ]
        return HandTrackingResult(hands=hands or None, handedness=handedness)

    def close(self) -> None:
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:  # pragma: no cover
                pass
            self._landmarker = None

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()
