"""Phase 1 control pipeline: camera -> landmarks -> gestures -> mouse + HUD.

``ControlPipeline.step()`` processes one frame and returns the actions it
took. Every dependency is injectable, so tests drive it with synthetic
frames and fake camera/tracker/mouse/HUD (no webcam, no OS calls —
09_TESTING integration strategy).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ..config import AppConfig
from ..control.menu import MenuCategory, MenuItem, MenuState, RadialMenu
from ..control.modes import Mode, ModeMachine
from ..control.registry import DEFAULT_BINDINGS, GestureRegistry
from ..control.virtual_mouse import VirtualMouse
from ..hud.events import (
    MenuEvent,
    MonitorsEvent,
    ReticleEvent,
    SkeletonEvent,
    StatusEvent,
)
from .camera import Camera
from .geometry import (
    classify,
    extended_finger_count,
    is_circle_trace,
    two_hand_spread,
)
from .hand_tracker import HandLandmarkerTracker
from .mapping import CursorMapper, MappingConfig
from .zones import LateralZone, lateral_zone

logger = logging.getLogger(__name__)

GESTURE_NONE = "none"


@dataclass
class ModifierInfo:
    """Secondary-hand state driving monitor selection and the fist menu.

    ``None``-ness of the pipeline's ``_modifier_hand`` marks "no modifier
    hand present". ``finger_count`` counts extended non-thumb fingers
    (0 = fist). The monitor selector logic (passive zone hold, finger-count
    selection, menu trigger) wires in a later slice — this scaffold only
    computes the state.
    """

    finger_count: int = 0
    fist: bool = False
    open_palm: bool = False
    lateral: LateralZone = LateralZone.CENTER
    index_xy: tuple[float, float] = (0.5, 0.5)


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
        camera: Camera | None = None,
        tracker: HandLandmarkerTracker | None = None,
        mouse: VirtualMouse | None = None,
        mapper: CursorMapper | None = None,
        hud: object | None = None,
        modes: ModeMachine | None = None,
        frame_source: Callable[[], object] | None = None,
        on_attention: Callable[[], None] | None = None,
        registry: GestureRegistry | None = None,
    ):
        self.config = config or AppConfig()
        self.camera = camera or Camera(
            self.config.perception.camera_index,
            self.config.perception.width,
            self.config.perception.height,
        )
        self.tracker = tracker or HandLandmarkerTracker(
            num_hands=self.config.perception.max_hands,
            min_hand_confidence=self.config.perception.min_hand_confidence,
            min_tracking_confidence=self.config.perception.min_tracking_confidence,
        )
        self.mouse = mouse or VirtualMouse(failsafe=self.config.control.failsafe)
        self.mapper = mapper or CursorMapper(
            config=MappingConfig.from_control(self.config.control)
        )
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
        # Modifier hand (Phase 2): fist menu + monitor selection.
        self._registry = registry or GestureRegistry(DEFAULT_BINDINGS)
        self._menu = self._build_menu()
        self._menu_open_at = 0.0
        self._mod_fist_start = 0.0
        self._mod_zone: LateralZone | None = None
        self._mod_zone_start = 0.0
        self._mod_zone_fired = False
        self._mod_count: int | None = None
        self._mod_count_frames = 0
        self._mod_count_fired = False
        self._menu_dirty = False
        # Guided 4-corner calibration (app/calibrate/session.py): while armed,
        # a pinch edge records the index tip instead of clicking.
        self._calibration_armed = False
        self._calibration_capture = None

    # Actions the registry can gate inside _dispatch (ADR-011). "attention"
    # (circle) and "mode.transfer_toggle" (spread) dispatch outside _dispatch,
    # so toggling them here would lie — they stay out of the menu.
    DISPATCH_ACTIONS = (
        "cursor.move",
        "click.left",
        "click.right",
        "drag.toggle",
        "scroll.tick",
        "confirm",
        "cancel",
        "catch",
        "release",
    )

    @staticmethod
    def _action_label(action_id: str) -> str:
        return action_id.replace("_", " ").replace(".", " ").title()

    def _build_menu(self) -> RadialMenu:
        """Fist-menu categories (04_GESTURE_VOCABULARY "Fist menu").

        Modes / Screens / Zoom / Tune / Gestures (ADR-011 dynamic bindings —
        each row toggles that action on/off, with a live checkmark). Screens
        is built from the detected monitor layout and hides itself when empty.
        """
        mode_items = [
            MenuItem(
                f"mode.{m.value}",
                m.value.capitalize(),
                action_id="mode.change",
                params={"mode": m.value},
            )
            for m in (
                Mode.CONTROL,
                Mode.CHAT,
                Mode.TRANSFER,
                Mode.PRESENTATION,
                Mode.IDLE,
            )
        ]
        screen_items = [
            MenuItem(
                f"screen.{i}",
                f"Monitor {i + 1}",
                action_id="screen.select",
                params={"index": i},
            )
            for i in range(len(self.mapper.monitors))
        ]
        screen_items.append(
            MenuItem(
                "screen.all",
                "All screens",
                action_id="screen.select",
                params={"index": None},
            )
        )
        gesture_items = [
            MenuItem(
                action_id,
                self._action_label(action_id),
                action_id="gesture.toggle",
                params={"action": action_id},
                checked=all(b.enabled for b in self._registry.by_action(action_id)),
            )
            for action_id in self.DISPATCH_ACTIONS
            if self._registry.by_action(action_id)
        ]
        return RadialMenu(
            [
                MenuCategory("modes", "Modes", items=mode_items),
                MenuCategory("screens", "Screens", items=screen_items),
                MenuCategory(
                    "zoom",
                    "Zoom",
                    items=[
                        MenuItem(
                            "zoom.in",
                            "Zoom in",
                            action_id="zoom",
                            params={"direction": "in"},
                        ),
                        MenuItem(
                            "zoom.out",
                            "Zoom out",
                            action_id="zoom",
                            params={"direction": "out"},
                        ),
                    ],
                ),
                MenuCategory(
                    "tune",
                    "Tune",
                    items=[
                        MenuItem(
                            "tune.gain_x_up",
                            "Gain X +",
                            action_id="tune",
                            params={"param": "gain_x_up"},
                        ),
                        MenuItem(
                            "tune.gain_x_down",
                            "Gain X -",
                            action_id="tune",
                            params={"param": "gain_x_down"},
                        ),
                        MenuItem(
                            "tune.gain_y_up",
                            "Gain Y +",
                            action_id="tune",
                            params={"param": "gain_y_up"},
                        ),
                        MenuItem(
                            "tune.gain_y_down",
                            "Gain Y -",
                            action_id="tune",
                            params={"param": "gain_y_down"},
                        ),
                        MenuItem(
                            "tune.invert_x",
                            "Invert X",
                            action_id="tune",
                            params={"param": "invert_x"},
                        ),
                        MenuItem(
                            "tune.invert_y",
                            "Invert Y",
                            action_id="tune",
                            params={"param": "invert_y"},
                        ),
                    ],
                ),
                MenuCategory("gestures", "Gestures", items=gesture_items),
            ]
        )

    # ------------------------------------------------------------------ #
    # guided calibration (app/calibrate/session.py)
    # ------------------------------------------------------------------ #

    def arm_calibration(self, capture) -> None:
        """Arm pinch-driven capture: the next pinch edge calls ``capture``.

        While armed, a pinch in Control mode records the normalized index tip
        via ``capture(nx, ny)`` instead of emitting a click. ``disarm``
        restores normal click behavior.
        """
        self._calibration_armed = True
        self._calibration_capture = capture

    def disarm_calibration(self) -> None:
        self._calibration_armed = False
        self._calibration_capture = None

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
            if self._menu.state is MenuState.OPEN:
                self._menu.close()
                self._menu_dirty = True
                actions.append(PipelineAction("menu.close", gesture="hand_lost"))
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
        # Modifier hand: fist menu + monitor selection. While the menu is open
        # it owns the frame — the primary pinch confirms instead of clicking,
        # so dispatch is suspended (and for one more frame after it closes,
        # so the confirming pinch doesn't also click).
        menu_was_open = self._modifier(result, pose, actions)
        # Misfire guard: with both hands up in a resting pose (e.g. a two-hand
        # spread), the spread handler owns the frame — don't also let the
        # primary open palm fire catch/release.
        if (
            not menu_was_open
            and self._menu.state is not MenuState.OPEN
            and not self._rest_pose(result, pose)
        ):
            actions.extend(self._dispatch(pose))
        actions.extend(self._circle(pose))
        if self._menu_dirty or self._menu.state is not MenuState.CLOSED:
            self._broadcast_menu()
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

    def _modifier_hand(self, result) -> ModifierInfo | None:
        """State of the secondary hand, or None when there is no modifier.

        Secondary = the non-preferred hand. Its lateral band selects the
        passive monitor zone, its extended-finger count selects a monitor
        directly, and a held fist triggers the HUD menu (consumed in
        ``_modifier``). Returns None with fewer than two hands or no handedness
        labels, so a lone hand never reads as a modifier.
        """
        hands = result.hands or []
        if len(hands) < 2 or not result.handedness or len(result.handedness) < 2:
            return None
        preferred = self.config.control.preferred_hand
        secondary = None
        for lmks, hand in zip(hands, result.handedness):
            if hand != preferred:
                secondary = lmks
                break
        if secondary is None:
            return None
        pose = classify(secondary)
        return ModifierInfo(
            finger_count=0 if pose.fist else extended_finger_count(secondary),
            fist=pose.fist,
            open_palm=pose.open_palm,
            lateral=lateral_zone(pose.index_xy[0]),
            index_xy=pose.index_xy,
        )

    def _modifier(self, result, pose, actions: list[PipelineAction]) -> bool:
        """Drive the modifier hand: fist menu + monitor selection.

        Three levels, in priority order (04_GESTURE_VOCABULARY): fist -> menu,
        finger count -> monitor, passive lateral zone -> monitor. All gated on
        two hands, a non-rest posture, and a mode other than IDLE. While the
        menu is open it owns the frame (highlight/confirm/cancel/timeout).

        Returns True when the menu was open at entry — the caller suspends
        gesture dispatch for that frame.
        """
        mod = self._modifier_hand(result)
        if self._menu.state is MenuState.OPEN:
            self._menu_frame(result, pose, mod, actions)
            return True
        if self.modes.mode is Mode.IDLE or mod is None:
            self._reset_modifier_state()
            return False
        if self._rest_pose(result, pose):
            self._reset_modifier_state()
            return False
        if self._fist_trigger(mod, actions):
            # A deliberate fist owns the frame; drop any pending zone/count.
            self._mod_zone = None
            self._mod_zone_start = 0.0
            self._mod_zone_fired = False
            self._mod_count = None
            self._mod_count_frames = 0
            self._mod_count_fired = False
            return False
        if self._finger_count_select(mod, pose, actions):
            self._mod_zone = None
            self._mod_zone_start = 0.0
            self._mod_zone_fired = False
            return False
        self._passive_zone_select(mod, actions)
        return False

    # ------------------------------------------------------------------ #
    # modifier levels
    # ------------------------------------------------------------------ #

    def _fist_trigger(self, mod: ModifierInfo, actions: list[PipelineAction]) -> bool:
        """Hold the secondary fist >= ``menu_hold_ms`` to open the menu.

        Returns True whenever the secondary hand is a fist (the frame is
        owned by the modifier, no zone/count action). The menu is sticky once
        opened — the trigger fist can relax; it closes on confirm / cancel /
        timeout / hand loss.
        """
        cfg = self.config.control
        now = time.monotonic()
        if not mod.fist:
            self._mod_fist_start = 0.0
            return False
        if self._mod_fist_start <= 0.0:
            self._mod_fist_start = now
            return True
        hold = cfg.menu_hold_ms / 1000.0 if cfg.menu_hold_ms > 0 else 0.0
        if (
            now - self._mod_fist_start >= hold
            and self._menu.state is MenuState.CLOSED
            and self._menu.open()
        ):
            self._menu_open_at = now
            self._menu_dirty = True
            actions.append(PipelineAction("menu.open", gesture="fist"))
        return True

    def _modifier_count(self, mod: ModifierInfo, pose) -> int | None:
        """Monitor number (1-based) the secondary hand selects, or None.

        1-4 extended fingers select monitor N directly; a full open palm
        (5 fingers) selects monitor 5 only while the primary hand is pointing,
        so a two-palm spread stays a spread (04_GESTURE_VOCABULARY collision
        defaults).
        """
        if mod.fist:
            return None
        if mod.open_palm:
            return 5 if pose.index_extended else None
        if mod.finger_count >= 1:
            return mod.finger_count
        return None

    def _finger_count_select(
        self, mod: ModifierInfo, pose, actions: list[PipelineAction]
    ) -> bool:
        """Edge-trigger a direct monitor selection from the finger count.

        Debounced by ``hold_frames`` so finger jitter (1 vs 2) can't re-fire.
        Returns True when a count is active (owns the frame; no passive zone).
        """
        count = self._modifier_count(mod, pose)
        if count is None:
            self._mod_count = None
            self._mod_count_frames = 0
            self._mod_count_fired = False
            return False
        if count != self._mod_count:
            self._mod_count = count
            self._mod_count_frames = 1
            self._mod_count_fired = False
        else:
            self._mod_count_frames += 1
        if (
            self._mod_count_frames >= self.config.control.hold_frames
            and not self._mod_count_fired
        ):
            self._mod_count_fired = True
            idx = count - 1
            if self.mapper.set_active_monitor(idx):
                actions.append(PipelineAction("screen.select", (idx,), gesture="count"))
        return True

    def _zone_target(self, zone: LateralZone) -> int | None:
        """Monitor index the passive zone leads to (relative to current)."""
        monitors = self.mapper.monitors
        if not monitors:
            return None
        active = self.mapper.config.active_monitor
        if zone is LateralZone.LEFT:
            return 0 if active is None else max(0, active - 1)
        return (
            len(monitors) - 1 if active is None else min(len(monitors) - 1, active + 1)
        )

    def _passive_zone_select(
        self, mod: ModifierInfo, actions: list[PipelineAction]
    ) -> None:
        """Passive monitor selection: hold a lateral zone ``zone_hold_ms``.

        The active monitor only changes after the secondary hand holds the
        same outer zone for the hold window (anti-thrash). ``zone_hold_ms``
        <= 0 disables the level.
        """
        cfg = self.config.control
        now = time.monotonic()
        if cfg.zone_hold_ms <= 0:
            self._mod_zone = None
            self._mod_zone_start = 0.0
            self._mod_zone_fired = False
            return
        zone = mod.lateral if mod.lateral is not LateralZone.CENTER else None
        if zone is None:
            self._mod_zone = None
            self._mod_zone_start = 0.0
            self._mod_zone_fired = False
            return
        if zone != self._mod_zone:
            self._mod_zone = zone
            self._mod_zone_start = now
            self._mod_zone_fired = False
            return
        if (
            now - self._mod_zone_start >= cfg.zone_hold_ms / 1000.0
            and not self._mod_zone_fired
        ):
            self._mod_zone_fired = True
            idx = self._zone_target(zone)
            if (
                idx is not None
                and idx != self.mapper.config.active_monitor
                and self.mapper.set_active_monitor(idx)
            ):
                actions.append(PipelineAction("screen.select", (idx,), gesture="zone"))

    def _reset_modifier_state(self) -> None:
        self._mod_fist_start = 0.0
        self._mod_zone = None
        self._mod_zone_start = 0.0
        self._mod_zone_fired = False
        self._mod_count = None
        self._mod_count_frames = 0
        self._mod_count_fired = False

    # ------------------------------------------------------------------ #
    # fist menu interaction
    # ------------------------------------------------------------------ #

    def _menu_frame(
        self, result, pose, mod: ModifierInfo | None, actions: list[PipelineAction]
    ) -> None:
        """One frame of the open menu: timeout, cancel, highlight, confirm."""
        cfg = self.config.control
        now = time.monotonic()
        if now - self._menu_open_at >= cfg.menu_timeout_ms / 1000.0:
            self._menu.close()
            self._menu_dirty = True
            actions.append(PipelineAction("menu.close", gesture="timeout"))
            return
        if mod is None:
            # Secondary hand gone: the menu has no anchor, close it.
            self._menu.close()
            self._menu_dirty = True
            actions.append(PipelineAction("menu.close", gesture="hand_lost"))
            return
        if mod.open_palm or (pose is not None and pose.open_palm):
            if self._menu.cancel():
                self._menu_dirty = True
                actions.append(PipelineAction("menu.cancel", gesture="open_palm"))
            return
        if pose is not None and pose.index_extended:
            sx, sy = self.mapper.to_screen(*pose.index_xy)
            sx0, sy0, sw, sh = self.mapper.screen
            dx, dy = sx - (sx0 + sw / 2.0), sy - (sy0 + sh / 2.0)
            self._menu.select_category(dx, dy)
            self._menu.select_item(dx, dy)
            self._menu_dirty = True
        if pose is not None and pose.pinch and not self._prev_pinch:
            item = self._menu.confirm()
            if item is not None:
                self._menu.close()
                self._prev_pinch = True
                self._menu_dirty = True
                actions.append(PipelineAction("menu.confirm", gesture="pinch"))
                executed = self._execute_menu_item(item)
                if executed is not None:
                    actions.append(executed)

    def _execute_menu_item(self, item: MenuItem) -> PipelineAction | None:
        """Run a confirmed menu leaf. Returns the action (if any)."""
        pid = item.action_id
        if pid == "screen.select":
            idx = item.params.get("index")
            if self.mapper.set_active_monitor(idx):
                return PipelineAction("screen.select", (idx,), gesture="menu")
        elif pid == "mode.change":
            try:
                target = Mode(item.params["mode"])
            except ValueError:
                return None
            self.modes.goto(target)
            return PipelineAction("mode.change", (target.value,), gesture="menu")
        elif pid == "zoom":
            direction = item.params.get("direction", "in")
            self.mouse.hotkey("ctrl", "+" if direction == "in" else "-")
            return PipelineAction(
                "zoom_in" if direction == "in" else "zoom_out", gesture="menu"
            )
        elif pid == "tune":
            return self._tune(item.params.get("param"))
        elif pid == "gesture.toggle":
            return self._toggle_gesture(item)
        return None

    def _toggle_gesture(self, item: MenuItem) -> PipelineAction | None:
        """Flip an action's enabled state (Gestures menu row, ADR-011)."""
        action_id = item.params.get("action")
        if not action_id or not self._registry.by_action(action_id):
            return None
        target = not all(b.enabled for b in self._registry.by_action(action_id))
        self._registry.set_enabled(action_id, target)
        # Refresh the stored checkmark so the next broadcast shows the new
        # state (the menu's categories survive close/reopen).
        for cat in self._menu.categories:
            for it in cat.items:
                if it.id == action_id:
                    it.checked = target
        self._menu_dirty = True
        return PipelineAction("gesture.toggle", (action_id, target), gesture="menu")

    def _tune(self, param: str) -> PipelineAction | None:
        """Apply a Tune-category adjustment (gain / invert), live."""
        cfg = self.config.control
        m = self.mapper.config
        if param == "gain_x_up":
            value = min(10.0, getattr(cfg, "gain_x", 3.2) + 0.5)
            cfg.gain_x, m.gain_x = value, value
        elif param == "gain_x_down":
            value = max(0.5, getattr(cfg, "gain_x", 3.2) - 0.5)
            cfg.gain_x, m.gain_x = value, value
        elif param == "gain_y_up":
            value = min(10.0, getattr(cfg, "gain_y", 3.2) + 0.5)
            cfg.gain_y, m.gain_y = value, value
        elif param == "gain_y_down":
            value = max(0.5, getattr(cfg, "gain_y", 3.2) - 0.5)
            cfg.gain_y, m.gain_y = value, value
        elif param == "invert_x":
            m.invert_x = not m.invert_x
            cfg.invert_x = m.invert_x
        elif param == "invert_y":
            m.invert_y = not m.invert_y
            cfg.invert_y = m.invert_y
        else:
            return None
        return PipelineAction("tune", (param,), gesture="menu")

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
        spread = (
            two_hand_spread(hands[0], hands[1])
            >= self.config.control.two_hand_spread_threshold
        )
        if spread:
            self._spread_frames += 1
            if (
                self._spread_frames >= self.config.control.hold_frames
                and not self._spread_active
            ):
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
        if len(hands) < 2 or self.modes.mode not in (Mode.CONTROL, Mode.TRANSFER):
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
                self._trace = self._trace[-cfg.circle_max_samples :]
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
            endpoint_tol=cfg.circle_endpoint_tol,
        ):
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

        # Resolve the gesture through the binding registry (ADR-011) and run
        # the bound action. Seed bindings mirror the old hardcoded branches,
        # so behavior is unchanged; toggling a binding off leaves the gesture
        # inert without touching the code. Arbitrary rebind (gesture -> a
        # different action) still needs per-gesture edge re-arm and lands in a
        # later slice.
        action_id = self._registry.resolve(gesture, mode.value)
        return self._run_action(action_id, gesture, pose, actions)

    def _run_action(
        self, action_id: str | None, gesture: str, pose, actions: list[PipelineAction]
    ) -> list[PipelineAction]:
        """Execute the resolved action. None = unbound/disabled gesture."""
        if action_id is None:
            return actions
        if action_id == "cursor.move":
            sx, _sy = self._move_cursor(pose.index_xy, actions)
            self._swipe(sx, actions)
        elif action_id == "click.left":
            if self._calibration_armed and self._calibration_capture is not None:
                if not self._prev_pinch:  # edge: one capture per pinch
                    self._calibration_capture(*pose.index_xy)
                    self._prev_pinch = True
            else:
                actions.extend(self._pinch(pose.index_xy))
        elif action_id == "click.right":
            actions.extend(self._two_finger_pinch(pose.index_xy))
        elif action_id == "drag.toggle":
            actions.extend(self._fist(pose.index_xy))
        elif action_id == "scroll.tick":
            self._scroll(pose, actions)
        elif action_id == "confirm":
            if not self._prev_thumbs_up:
                actions.append(PipelineAction("confirm", gesture=gesture))
            self._prev_thumbs_up = True
        elif action_id == "cancel":
            if not self._prev_thumbs_down:
                actions.append(PipelineAction("cancel", gesture=gesture))
            self._prev_thumbs_down = True
        elif action_id == "catch":
            if not self._prev_open_palm:
                actions.append(PipelineAction("catch", gesture=gesture))
            self._prev_open_palm = True
        elif action_id == "release":
            if not self._prev_open_palm:
                actions.append(PipelineAction("release", gesture=gesture))
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

    def _move_cursor(
        self, index_xy: tuple[float, float], actions: list[PipelineAction]
    ) -> tuple[int, int]:
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
                2, min_cutoff=c.min_cutoff, beta=c.beta, d_cutoff=c.d_cutoff
            )
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
            self.mouse.hotkey("alt", "tab")  # next window
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
        self._scroll_accum += self._prev_scroll_y - ny
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
        self._reset_modifier_state()
        if self._menu.state is MenuState.OPEN:
            self._menu.close()
            self._menu_dirty = True

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
            self.hud.broadcast(
                MonitorsEvent(
                    monitors=self.mapper.monitors,
                    active_monitor=self.mapper.config.active_monitor,
                )
            )
            self._monitors_sent = True
        if now - self._last_skeleton_ts >= self.config.hud.skeleton_interval_s:
            self.hud.broadcast(SkeletonEvent(hands=result.hands or []))
            self._last_skeleton_ts = now
        if pose is not None and pose.index_extended:
            (sx, sy), monitor = self.mapper.point_at_zone(*pose.index_xy)
            self.hud.broadcast(
                ReticleEvent(
                    x=sx,
                    y=sy,
                    monitor=monitor,
                    zone=self.mapper.zone_for(*pose.index_xy),
                )
            )
        self._emit_status()

    def _broadcast_menu(self) -> None:
        """Emit the current radial menu state to the HUD overlay."""
        if self.hud is None:
            return
        cats = self._menu.open_categories
        category = ""
        item = ""
        if (
            self._menu.state is MenuState.OPEN
            and cats
            and 0 <= self._menu.category_idx < len(cats)
        ):
            category = cats[self._menu.category_idx].id
            items = cats[self._menu.category_idx].items
            if self._menu.item_idx is not None and 0 <= self._menu.item_idx < len(
                items
            ):
                item = items[self._menu.item_idx].id
        self.hud.broadcast(
            MenuEvent(
                state=self._menu.state.value,
                category=category,
                item=item,
                categories=[
                    {
                        "id": c.id,
                        "label": c.label,
                        "items": [
                            {"id": i.id, "label": i.label, "checked": i.checked}
                            for i in c.items
                        ],
                    }
                    for c in cats
                ],
            )
        )
        self._menu_dirty = False

    def _emit_status(self) -> None:
        if self.hud is None:
            return
        now = time.monotonic()
        if now - self._last_status_ts < self.config.hud.status_interval_s:
            return
        self._last_status_ts = now
        self.hud.broadcast(
            StatusEvent(
                mode=self.modes.mode.value,
                fps=self.stats.last_fps,
                detected=self.stats.hands_seen >= self.stats.frames - 1,
                gesture=self._status_gesture,
            )
        )

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
