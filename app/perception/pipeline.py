"""Phase 1 control pipeline: camera -> landmarks -> gestures -> mouse + HUD.

``ControlPipeline.step()`` processes one frame and returns the actions it
took. Every dependency is injectable, so tests drive it with synthetic
frames and fake camera/tracker/mouse/HUD (no webcam, no OS calls —
09_TESTING integration strategy).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..config import AppConfig
from ..control.modes import Mode, ModeMachine
from ..control.virtual_mouse import VirtualMouse
from ..hud.events import ReticleEvent, SkeletonEvent, StatusEvent
from .camera import Camera
from .geometry import classify
from .hand_tracker import HandLandmarkerTracker
from .mapping import CursorMapper

logger = logging.getLogger(__name__)

GESTURE_NONE = "none"


@dataclass
class PipelineAction:
    """One control action produced by a pipeline step."""

    name: str
    args: tuple = ()
    gesture: str = ""

    def __str__(self) -> str:
        if self.args:
            return f"{self.name}({', '.join(map(str, self.args))})"
        return self.name


@dataclass
class PipelineStats:
    frames: int = 0
    hands_seen: int = 0
    last_fps: float = 0.0
    started: float = field(default_factory=time.monotonic)

    @property
    def detection_rate(self) -> float:
        return self.hands_seen / self.frames if self.frames else 0.0


class ControlPipeline:
    """Wire camera -> tracker -> geometry -> smoothing -> mouse -> HUD."""

    def __init__(
        self,
        config: AppConfig | None = None,
        camera: Optional[Camera] = None,
        tracker: Optional[HandLandmarkerTracker] = None,
        mouse: Optional[VirtualMouse] = None,
        mapper: Optional[CursorMapper] = None,
        hud: Optional[object] = None,
        modes: Optional[ModeMachine] = None,
        frame_source: Optional[Callable[[], object]] = None,
    ):
        self.config = config or AppConfig()
        self.camera = camera or Camera(self.config.perception.camera_index,
                                       self.config.perception.width,
                                       self.config.perception.height)
        self.tracker = tracker or HandLandmarkerTracker(
            num_hands=self.config.perception.max_hands,
            min_hand_confidence=self.config.perception.min_hand_confidence,
            min_tracking_confidence=self.config.perception.min_tracking_confidence,
        )
        self.mouse = mouse or VirtualMouse()
        self.mapper = mapper or CursorMapper.from_control(self.config.control)
        self.hud = hud
        self.modes = modes or ModeMachine()
        self.frame_source = frame_source

        self.stats = PipelineStats()
        self._smoothing = None  # built lazily to keep imports light
        self._prev_pinch = False
        self._prev_two_pinch = False
        self._dragging = False
        self._gesture_frames = 0
        self._last_gesture: str | None = None
        self._v_sign_active = False
        self._scroll_accum = 0.0
        self._scroll_last = 0.0
        self._prev_scroll_y = 0.5
        self._window_start = time.monotonic()
        self._window_frames = 0

    # ------------------------------------------------------------------ #
    # main loop
    # ------------------------------------------------------------------ #

    def step(self, frame=None) -> list[PipelineAction]:
        """Process one frame and return the actions executed."""
        actions: list[PipelineAction] = []
        if frame is None:
            ok, frame = self.camera.read()
            if not ok:
                self._emit_status()
                return actions
        self.stats.frames += 1
        self._window_frames += 1

        result = self.tracker.process(frame)
        if not result.detected:
            if self._dragging:
                self.mouse.drag_end()
                self._dragging = False
                actions.append(PipelineAction("drag_end", gesture="fist"))
            self._on_hand_lost()
            self._emit(result, None)
            return actions

        self.stats.hands_seen += 1
        lmks = result.hands[0]

        pose = classify(lmks)
        self._emit(result, pose)
        actions.extend(self._dispatch(pose))
        self._tick_fps()
        return actions

    # ------------------------------------------------------------------ #
    # gesture dispatch
    # ------------------------------------------------------------------ #

    def _dispatch(self, pose) -> list[PipelineAction]:
        actions: list[PipelineAction] = []
        mode = self.modes.mode

        # Wake: any hand in Idle mode lifts us to Control.
        if mode == Mode.IDLE:
            self.modes.transition("wake")
            return actions

        gesture = pose.name
        if not self.modes.allows(gesture):
            self._on_disallowed(gesture)
            return actions
        if gesture != "v_sign":
            self._v_sign_active = False

        # Leaving "fist" releases an active drag (fist = hold, release = drop).
        if self._dragging and gesture != "fist":
            self.mouse.drag_end()
            self._dragging = False
            actions.append(PipelineAction("drag_end", gesture=gesture))

        # Debounce: require the gesture to persist for hold_frames.
        stable = self._hold_stable(gesture)
        if not stable:
            return actions

        if gesture == "point":
            self._move_cursor(pose.index_xy, actions)
        elif gesture == "pinch":
            actions.extend(self._pinch(pose.index_xy))
        elif gesture == "two_finger_pinch":
            actions.extend(self._two_finger_pinch(pose.index_xy))
        elif gesture == "fist":
            actions.extend(self._fist(pose.index_xy))
        elif gesture == "v_sign":
            self._scroll(pose, actions)
        return actions

    def _on_disallowed(self, gesture: str) -> None:
        """Clean up transient state when the current gesture can't act."""
        self._last_gesture = gesture
        self._gesture_frames = 0
        if gesture != "v_sign":
            self._v_sign_active = False

    def _hold_stable(self, gesture: str) -> bool:
        if gesture == self._last_gesture:
            self._gesture_frames += 1
        else:
            self._gesture_frames = 1
            self._last_gesture = gesture
        return self._gesture_frames >= self.config.control.hold_frames

    def _move_cursor(self, index_xy: tuple[float, float],
                     actions: list[PipelineAction]) -> None:
        sx, sy = self._smoothed_screen(index_xy)
        self.mouse.move(sx, sy)
        actions.append(PipelineAction("move", (sx, sy), gesture="point"))

    def _smoothed_screen(self, index_xy: tuple[float, float]) -> tuple[int, int]:
        """Apply 1-Euro smoothing in screen space, then map to pixels."""
        if self._smoothing is None:
            from .smoothing import OneEuroVectorFilter

            c = self.config.control
            self._smoothing = OneEuroVectorFilter(
                2, min_cutoff=c.min_cutoff, beta=c.beta, d_cutoff=c.d_cutoff)
        x, y = self._smoothing(index_xy)
        return self.mapper.to_screen(x, y)

    def _pinch(self, index_xy) -> list[PipelineAction]:
        actions: list[PipelineAction] = []
        if not self._prev_pinch:  # edge trigger: click once on gesture start
            self._move_cursor(index_xy, actions)
            self.mouse.click(button="left")
            actions.append(PipelineAction("left_click", gesture="pinch"))
        self._prev_pinch = True
        return actions

    def _two_finger_pinch(self, index_xy) -> list[PipelineAction]:
        actions: list[PipelineAction] = []
        if not self._prev_two_pinch:
            self._move_cursor(index_xy, actions)
            self.mouse.right_click()
            actions.append(PipelineAction("right_click", gesture="two_finger_pinch"))
        self._prev_two_pinch = True
        return actions

    def _fist(self, index_xy) -> list[PipelineAction]:
        actions: list[PipelineAction] = []
        if not self._dragging:
            self.mouse.drag_start(*self._smoothed_screen(index_xy))
            self._dragging = True
            actions.append(PipelineAction("drag_start", gesture="fist"))
        else:
            self._move_cursor(index_xy, actions)
        return actions

    def _scroll(self, pose, actions: list[PipelineAction]) -> None:
        """V-sign: scroll by vertical hand movement, debounced by hold time.

        Each ``scroll_threshold`` of upward normalized motion = 1 scroll tick
        up; downward motion ticks down. The first V-sign frame seeds the
        reference so entering the gesture never causes a jump-scroll.
        """
        now = time.monotonic()
        if now - self._scroll_last < self.config.control.scroll_hold_ms / 1000.0:
            return
        _, ny = pose.index_xy
        if not self._v_sign_active:
            self._prev_scroll_y = ny
            self._v_sign_active = True
        self._scroll_accum += (self._prev_scroll_y - ny)
        self._prev_scroll_y = ny
        ticks = int(self._scroll_accum / self.config.control.scroll_threshold)
        if ticks:
            self._scroll_accum -= ticks * self.config.control.scroll_threshold
            self._scroll_last = now
            self.mouse.scroll(ticks)
            actions.append(PipelineAction("scroll", (ticks,), gesture="v_sign"))

    def _on_hand_lost(self) -> None:
        self._smoothing = None
        self._prev_pinch = False
        self._prev_two_pinch = False
        self._last_gesture = None
        self._gesture_frames = 0
        self._v_sign_active = False
        self._scroll_accum = 0.0
        self._prev_scroll_y = 0.5

    # ------------------------------------------------------------------ #
    # HUD + stats
    # ------------------------------------------------------------------ #

    def _emit(self, result, pose) -> None:
        if self.hud is None:
            return
        self.hud.broadcast(SkeletonEvent(hands=result.hands or []))
        if pose is not None and pose.index_extended:
            sx, sy = self.mapper.to_screen(*pose.index_xy)
            self.hud.broadcast(ReticleEvent(x=sx, y=sy))
        self._emit_status()

    def _emit_status(self) -> None:
        if self.hud is None:
            return
        self.hud.broadcast(StatusEvent(
            mode=self.modes.mode.value,
            fps=self.stats.last_fps,
            detected=self.stats.hands_seen >= self.stats.frames - 1,
        ))

    def _tick_fps(self) -> None:
        now = time.monotonic()
        elapsed = now - self._window_start
        if elapsed >= 1.0:
            self.stats.last_fps = self._window_frames / elapsed
            self._window_frames = 0
            self._window_start = now

    def close(self) -> None:
        if self._dragging:
            self.mouse.drag_end()
            self._dragging = False
        self.tracker.close()
        self.camera.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()
