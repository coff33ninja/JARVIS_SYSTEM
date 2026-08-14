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
from ..hud.events import MonitorsEvent, ReticleEvent, SkeletonEvent, StatusEvent
from .camera import Camera
from .geometry import classify, is_circle_trace, two_hand_spread
from .hand_tracker import HandLandmarkerTracker
from .mapping import CursorMapper, MappingConfig

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
        on_attention: Optional[Callable[[], None]] = None,
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
        self.mouse = mouse or VirtualMouse(
            failsafe=self.config.control.failsafe)
        self.mapper = mapper or CursorMapper(
            config=MappingConfig.from_control(self.config.control))
        self.hud = hud
        self.modes = modes or ModeMachine()
        self.frame_source = frame_source
        self.on_attention = on_attention or (lambda: None)

        self.stats = PipelineStats()
        self._smoothing = None  # built lazily to keep imports light
        self._prev_pinch = False
        self._prev_two_pinch = False
        self._prev_thumbs_up = False
        self._prev_thumbs_down = False
        self._prev_open_palm = False
        self._spread_active = False
        self._spread_frames = 0
        self._zoom_ref: float | None = None
        self._zoom_accum = 0.0
        self._dragging = False
        self._last_gesture = ""
        self._gesture_frames = 0
        self._trace: list[tuple[float, float]] = []
        self._trace_last = 0.0
        self._v_sign_active = False
        self._prev_scroll_y = 0.5
        self._scroll_accum = 0.0
        self._scroll_last = 0.0
        self._prev_move_sx: int | None = None
        self._swipe_accum = 0.0
        self._swipe_last = 0.0
        self._window_start = time.monotonic()
        self._window_frames = 0
        self._monitors_sent = False
        self._lost_frames = 0
        self._last_skeleton_ts = 0.0
        self._last_status_ts = 0.0
        self._status_gesture = ""

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
        self._tick_fps()

        result = self.tracker.process(frame)
        if not result.detected:
            if self._dragging:
                self.mouse.drag_end()
                self._dragging = False
                actions.append(PipelineAction("drag_end", gesture="fist"))
            self._lost_frames += 1
            # Grace: brief detection flickers keep the smoothing filter so the
            # cursor doesn't jump; a sustained loss resets it fully.
            if self._lost_frames > self.config.control.lost_grace_frames:
                self._on_hand_lost()
            self._emit(result, None)
            return actions

        self._lost_frames = 0
        self.stats.hands_seen += 1
        lmks = self._primary_hand(result)
        if lmks is None:
            self._emit(result, None)
            return actions

        self._spread(result)
        self._two_hand_zoom(result, actions)
        pose = classify(lmks)
        self._emit(result, pose)
        # Misfire guard: with both hands up in a resting pose (e.g. a two-hand
        # spread), the spread handler owns the frame — don't also let the
        # primary open palm fire catch/release.
        if not self._rest_pose(result, pose):
            actions.extend(self._dispatch(pose))
        actions.extend(self._circle(pose))
        return actions

    # ------------------------------------------------------------------ #
    # two-hand selection + spread trigger
    # ------------------------------------------------------------------ #

    def _primary_hand(self, result) -> list | None:
        """Pick which hand drives the cursor when multiple are present.

        Prefers the configured handedness (e.g. "Right"); falls back to the
        first detected hand. Returns ``None`` only when nothing is tracked.
        """
        hands = result.hands or []
        if not hands:
            return None
        if len(hands) > 1 and result.handedness:
            preferred = self.config.control.preferred_hand
            for lmks, hand in zip(hands, result.handedness):
                if hand == preferred:
                    return lmks
        return hands[0]

    def _spread(self, result) -> None:
        """Edge-trigger the two-hand spread: toggles Control <-> Transfer.

        Both hands apart (palm-center distance past the threshold) for
        ``hold_frames`` arms the trigger; releasing the spread re-arms it.
        """
        hands = result.hands or []
        if len(hands) < 2:
            self._spread_active = False
            self._spread_frames = 0
            return
        spread = (two_hand_spread(hands[0], hands[1])
                  >= self.config.control.two_hand_spread_threshold)
        if spread:
            self._spread_frames += 1
            if (self._spread_frames >= self.config.control.hold_frames
                    and not self._spread_active):
                self._spread_active = True
                self.modes.transition("transfer_gesture")
        else:
            self._spread_frames = 0
            self._spread_active = False

    def _two_hand_zoom(self, result, actions: list[PipelineAction]) -> None:
        """Two-hand pinch-apart zoom (Control / Transfer).

        While both hands pinch, accumulated palm-center distance change drives
        zoom ticks: palms apart -> ``zoom_in`` (Ctrl++), together ->
        ``zoom_out`` (Ctrl+-). One tick per ``two_hand_zoom_threshold`` of
        movement; releasing either pinch re-arms the reference so the next
        spread starts from a fresh distance.
        """
        hands = result.hands or []
        if (len(hands) < 2
                or self.modes.mode not in (Mode.CONTROL, Mode.TRANSFER)):
            self._zoom_ref = None
            self._zoom_accum = 0.0
            return
        if not (classify(hands[0]).pinch and classify(hands[1]).pinch):
            self._zoom_ref = None
            self._zoom_accum = 0.0
            return
        spread = two_hand_spread(hands[0], hands[1])
        if self._zoom_ref is None:
            self._zoom_ref = spread
            return
        self._zoom_accum += spread - self._zoom_ref
        self._zoom_ref = spread
        threshold = self.config.control.two_hand_zoom_threshold
        eps = 1e-9
        while abs(self._zoom_accum) + eps >= threshold:
            if self._zoom_accum > 0:
                self.mouse.hotkey("ctrl", "+")
                actions.append(PipelineAction("zoom_in", gesture="two_hand_pinch"))
                self._zoom_accum -= threshold
            else:
                self.mouse.hotkey("ctrl", "-")
                actions.append(PipelineAction("zoom_out", gesture="two_hand_pinch"))
                self._zoom_accum += threshold

    # ------------------------------------------------------------------ #
    # misfire guards + attention gesture
    # ------------------------------------------------------------------ #

    def _rest_pose(self, result, pose) -> bool:
        """True when both hands are up in a resting / non-deliberate pose.

        Two open palms (or an open palm beside an unclassified hand) read as
        the two-hand spread / rest posture; the spread handler owns it, so a
        spread frame must not also fire catch/release from the primary open
        palm. A deliberate single-hand open palm still acts.
        """
        hands = result.hands or []
        if len(hands) < 2 or pose.name not in ("open_palm", "none"):
            return False
        return classify(hands[1]).name in ("open_palm", "none")

    def _circle(self, pose) -> list[PipelineAction]:
        """Index-trace circle -> attention ("Jarvis"). Works in any mode.

        Accumulates the index tip while the hand is in a trace pose (index
        extended, not pinching, not an open palm) and fires once when the
        recent trajectory closes into a circular sweep (04_GESTURE_VOCABULARY
        "Circle / index trace"). Cooldown suppresses repeat triggers.
        """
        cfg = self.config.control
        now = time.monotonic()
        if pose.index_extended and not pose.pinch and not pose.open_palm:
            self._trace.append(pose.index_xy)
            if len(self._trace) > cfg.circle_max_samples:
                self._trace = self._trace[-cfg.circle_max_samples:]
        else:
            self._trace = []
        if len(self._trace) < cfg.circle_min_samples:
            return []
        if now - self._trace_last < cfg.circle_cooldown_ms / 1000.0:
            return []
        if not is_circle_trace(
                self._trace,
                min_samples=cfg.circle_min_samples,
                min_sweep=cfg.circle_min_sweep,
                max_aspect=cfg.circle_max_aspect,
                endpoint_tol=cfg.circle_endpoint_tol):
            return []
        self._trace = []
        self._trace_last = now
        self.on_attention()
        return [PipelineAction("attention", gesture="circle")]

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
        # Edge-trigger the thumb gestures: arm them only while off.
        if gesture != "thumbs_up":
            self._prev_thumbs_up = False
        if gesture != "thumbs_down":
            self._prev_thumbs_down = False
        if gesture != "open_palm":
            self._prev_open_palm = False
        # Same re-arm for the pinch clicks: leaving the pinch (even briefly)
        # must re-arm it so the next pinch clicks again.
        if gesture != "pinch":
            self._prev_pinch = False
        if gesture != "two_finger_pinch":
            self._prev_two_pinch = False

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
            sx, sy = self._move_cursor(pose.index_xy, actions)
            self._swipe(sx, actions)
        elif gesture == "pinch":
            actions.extend(self._pinch(pose.index_xy))
        elif gesture == "two_finger_pinch":
            actions.extend(self._two_finger_pinch(pose.index_xy))
        elif gesture == "fist":
            actions.extend(self._fist(pose.index_xy))
        elif gesture == "v_sign":
            self._scroll(pose, actions)
        elif gesture == "thumbs_up":
            if not self._prev_thumbs_up:
                actions.append(PipelineAction("confirm", gesture="thumbs_up"))
            self._prev_thumbs_up = True
        elif gesture == "thumbs_down":
            if not self._prev_thumbs_down:
                actions.append(PipelineAction("cancel", gesture="thumbs_down"))
            self._prev_thumbs_down = True
        elif gesture == "open_palm":
            # Transfer: open palm = "catch". Chat: open palm = "release".
            if not self._prev_open_palm:
                if self.modes.mode == Mode.TRANSFER:
                    actions.append(PipelineAction("catch", gesture="open_palm"))
                elif self.modes.mode == Mode.CHAT:
                    actions.append(PipelineAction("release", gesture="open_palm"))
            self._prev_open_palm = True
        return actions

    def _on_disallowed(self, gesture: str) -> None:
        """Clean up transient state when the current gesture can't act."""
        self._last_gesture = gesture
        self._gesture_frames = 0
        if gesture != "v_sign":
            self._v_sign_active = False
        if gesture != "thumbs_up":
            self._prev_thumbs_up = False
        if gesture != "thumbs_down":
            self._prev_thumbs_down = False
        if gesture != "open_palm":
            self._prev_open_palm = False
        if gesture != "pinch":
            self._prev_pinch = False
        if gesture != "two_finger_pinch":
            self._prev_two_pinch = False

    def _hold_stable(self, gesture: str) -> bool:
        if gesture == self._last_gesture:
            self._gesture_frames += 1
        else:
            self._gesture_frames = 1
            self._last_gesture = gesture
        return self._gesture_frames >= self.config.control.hold_frames

    def _move_cursor(self, index_xy: tuple[float, float],
                     actions: list[PipelineAction]) -> tuple[int, int]:
        sx, sy = self._smoothed_screen(index_xy)
        self.mouse.move(sx, sy)
        actions.append(PipelineAction("move", (sx, sy), gesture="point"))
        return sx, sy

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

    def _swipe(self, sx: int, actions: list[PipelineAction]) -> None:
        """Swipe detection: accumulate one-direction screen-x motion.

        A fast lateral sweep of the pointing hand past ``swipe_threshold_px``
        fires swipe_left / swipe_right (Alt+Tab window switching). A change of
        direction resets the accumulator; a cooldown prevents double-fires.
        """
        cfg = self.config.control
        now = time.monotonic()
        if self._prev_move_sx is None:
            self._prev_move_sx = sx
            return
        dx = sx - self._prev_move_sx
        self._prev_move_sx = sx
        if now - self._swipe_last < cfg.swipe_cooldown_ms / 1000.0:
            return
        if dx * self._swipe_accum < 0:  # direction flipped: start over
            self._swipe_accum = 0.0
        self._swipe_accum += dx
        if abs(self._swipe_accum) < cfg.swipe_threshold_px:
            return
        direction = "right" if self._swipe_accum > 0 else "left"
        self._swipe_accum = 0.0
        self._swipe_last = now
        if self.modes.mode == Mode.PRESENTATION:
            # Swipe = slide navigation: right sweep -> next, left -> previous.
            self.mouse.hotkey("pagedown" if direction == "right" else "pageup")
        elif direction == "left":
            self.mouse.hotkey("alt", "shift", "tab")  # previous window
        else:
            self.mouse.hotkey("alt", "tab")           # next window
        actions.append(PipelineAction("swipe_" + direction, gesture="point"))

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
            if self.modes.mode == Mode.PRESENTATION:
                # V-sign = slide navigation: up -> previous, down -> next.
                if ticks > 0:
                    self.mouse.hotkey("pageup")
                else:
                    self.mouse.hotkey("pagedown")
            else:
                self.mouse.scroll(ticks)
            actions.append(PipelineAction("scroll", (ticks,), gesture="v_sign"))

    def _on_hand_lost(self) -> None:
        self._smoothing = None
        self._status_gesture = ""
        self._prev_pinch = False
        self._prev_two_pinch = False
        self._prev_thumbs_up = False
        self._prev_thumbs_down = False
        self._prev_open_palm = False
        self._spread_active = False
        self._spread_frames = 0
        self._zoom_ref = None
        self._zoom_accum = 0.0
        self._last_gesture = None
        self._gesture_frames = 0
        self._trace = []
        self._trace_last = 0.0
        self._v_sign_active = False
        self._scroll_accum = 0.0
        self._prev_scroll_y = 0.5
        self._prev_move_sx = None
        self._swipe_accum = 0.0

    # ------------------------------------------------------------------ #
    # HUD + stats
    # ------------------------------------------------------------------ #

    def _emit(self, result, pose) -> None:
        if self.hud is None:
            return
        now = time.monotonic()
        if pose is not None:
            self._status_gesture = pose.name
        if not self._monitors_sent:
            self.hud.broadcast(MonitorsEvent(monitors=self.mapper.monitors))
            self._monitors_sent = True
        if now - self._last_skeleton_ts >= self.config.hud.skeleton_interval_s:
            self.hud.broadcast(SkeletonEvent(hands=result.hands or []))
            self._last_skeleton_ts = now
        if pose is not None and pose.index_extended:
            (sx, sy), monitor = self.mapper.point_at_zone(*pose.index_xy)
            self.hud.broadcast(ReticleEvent(x=sx, y=sy, monitor=monitor))
        self._emit_status()

    def _emit_status(self) -> None:
        if self.hud is None:
            return
        now = time.monotonic()
        if now - self._last_status_ts < self.config.hud.status_interval_s:
            return
        self._last_status_ts = now
        self.hud.broadcast(StatusEvent(
            mode=self.modes.mode.value,
            fps=self.stats.last_fps,
            detected=self.stats.hands_seen >= self.stats.frames - 1,
            gesture=self._status_gesture,
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
            try:
                self.mouse.drag_end()
            except Exception:  # pragma: no cover - OS input layer
                logger.warning("drag_end failed during shutdown", exc_info=True)
            self._dragging = False
        self.tracker.close()
        self.camera.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()
