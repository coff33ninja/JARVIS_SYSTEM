"""ControlPipeline integration with fakes: no webcam, no OS input calls."""

from __future__ import annotations

import numpy as np
import pytest

from app.config import AppConfig
from app.control.modes import Mode, ModeMachine
from app.perception.hand_tracker import HandTrackingResult
from app.perception.mapping import CursorMapper, MappingConfig
from app.perception.pipeline import ControlPipeline
from conftest import fist, open_hand, pinch_hand, point_hand, two_pinch_hand, v_sign


class FakeTracker:
    def __init__(self, result=None):
        self.result = result
        self.processed = 0

    def process(self, frame):
        self.processed += 1
        return self.result

    def close(self):
        pass


class FakeCamera:
    def read(self):
        return (False, None)

    def release(self):
        pass


class FakeMouse:
    def __init__(self):
        self.calls = []

    def move(self, x, y):
        self.calls.append(("move", x, y))

    def click(self, button="left", clicks=1):
        self.calls.append(("click", button, clicks))

    def right_click(self):
        self.calls.append(("right_click",))

    def drag_start(self, x, y):
        self.calls.append(("drag_start", x, y))

    def drag_to(self, x, y):
        self.calls.append(("drag_to", x, y))

    def drag_end(self):
        self.calls.append(("drag_end",))

    def scroll(self, clicks):
        self.calls.append(("scroll", clicks))

    def hotkey(self, *keys):
        self.calls.append(("hotkey", keys))


class FakeHUD:
    def __init__(self):
        self.events = []

    def broadcast(self, event):
        self.events.append(event.to_dict())


FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


def patch_time(module, now):
    """Monkeypatch module.time.monotonic to return a fixed value."""
    from unittest.mock import patch

    class _FakeTime:
        @staticmethod
        def monotonic():
            return now

    return patch.object(module, "time", _FakeTime)


def make_pipeline(result=None, mode=Mode.CONTROL, config=None):
    cfg = config or AppConfig()
    tracker = FakeTracker(result)
    mouse = FakeMouse()
    hud = FakeHUD()
    mapper = CursorMapper(MappingConfig(screen=(0, 0, 1000, 800)))
    pipe = ControlPipeline(
        config=cfg, camera=FakeCamera(), tracker=tracker, mouse=mouse,
        mapper=mapper, hud=hud, modes=ModeMachine(mode))
    return pipe, mouse, hud, tracker


def hands(hand):
    return HandTrackingResult(hands=[hand], handedness=["Right"])


def test_idle_wakes_on_hand():
    pipe, mouse, hud, _ = make_pipeline(hands(open_hand()), mode=Mode.IDLE)
    actions = pipe.step(FRAME)
    assert actions == []
    assert pipe.modes.mode == Mode.CONTROL
    assert mouse.calls == []


def test_point_moves_cursor():
    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()))
    for _ in range(2):  # hold_frames debounce
        pipe.step(FRAME)
    assert any(c[0] == "move" for c in mouse.calls)


def test_pinch_clicks_once_on_edge():
    pipe, mouse, hud, _ = make_pipeline(hands(pinch_hand()))
    for _ in range(2):  # hold_frames debounce then fire
        pipe.step(FRAME)
    clicks = [c for c in mouse.calls if c[0] == "click"]
    assert len(clicks) == 1
    assert clicks[0][1] == "left"
    # holding the pinch does not double-fire
    pipe.step(FRAME)
    assert len([c for c in mouse.calls if c[0] == "click"]) == 1


def test_two_finger_pinch_right_clicks():
    pipe, mouse, hud, _ = make_pipeline(hands(two_pinch_hand()))
    for _ in range(2):
        pipe.step(FRAME)
    assert ("right_click",) in mouse.calls


def test_fist_drags_then_release_on_hand_lost():
    pipe, mouse, hud, tracker = make_pipeline(hands(fist()))
    for _ in range(2):
        pipe.step(FRAME)
    assert any(c[0] == "drag_start" for c in mouse.calls)
    tracker.result = HandTrackingResult()  # hand gone
    pipe.step(FRAME)
    assert ("drag_end",) in mouse.calls


def test_fist_to_point_releases_drag():
    pipe, mouse, hud, tracker = make_pipeline(hands(fist()))
    for _ in range(2):
        pipe.step(FRAME)
    assert any(c[0] == "drag_start" for c in mouse.calls)
    tracker.result = hands(point_hand())
    for _ in range(2):
        pipe.step(FRAME)
    assert any(c[0] == "drag_end" for c in mouse.calls)


def test_v_sign_scrolls_on_upward_motion():
    pipe, mouse, hud, tracker = make_pipeline(hands(v_sign()))
    # stable v_sign, then move hand up in small steps
    for _ in range(2):
        pipe.step(FRAME)
    base = v_sign()
    import app.perception.geometry as g

    moved = list(base)
    for step in range(5):
        moved[g.INDEX_TIP] = (moved[g.INDEX_TIP][0],
                              moved[g.INDEX_TIP][1] - 0.05, 0.0)
        tracker.result = hands(moved)
        pipe.step(FRAME)
    assert any(c[0] == "scroll" and c[1] > 0 for c in mouse.calls)


def test_no_hand_emits_no_actions():
    pipe, mouse, hud, _ = make_pipeline(HandTrackingResult())
    assert pipe.step(FRAME) == []
    assert mouse.calls == []


def test_swipe_right_hotkeys_alt_tab():
    pipe, mouse, hud, tracker = make_pipeline(hands(point_hand()))
    for _ in range(2):  # let smoothing warm up
        pipe.step(FRAME)
    tracker.result = None  # freeze pose; inject motion via _prev_move_sx
    # Simulate a fast lateral sweep in screen space.
    pipe._prev_move_sx = 400
    pipe._swipe_accum = 0.0
    pipe._swipe_last = 0.0
    pipe._swipe(900, [])  # 500px right past 250px threshold
    assert ("hotkey", ("alt", "tab")) in mouse.calls


def test_swipe_left_hotkeys_alt_shift_tab():
    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()))
    pipe._prev_move_sx = 900
    pipe._swipe_accum = 0.0
    pipe._swipe_last = 0.0
    pipe._swipe(200, [])
    assert ("hotkey", ("alt", "shift", "tab")) in mouse.calls


def test_swipe_direction_change_resets_accumulator():
    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()))
    pipe._prev_move_sx = 400
    pipe._swipe_accum = 200.0  # built up rightward
    pipe._swipe_last = 0.0
    pipe._swipe(300, [])  # reverse: should reset, not fire
    assert all(c[0] != "hotkey" for c in mouse.calls)


def test_swipe_cooldown_prevents_double_fire():
    import app.perception.pipeline as pipeline_mod

    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()))
    now = 1000.0
    pipe._prev_move_sx = 400
    pipe._swipe_accum = 250.0
    pipe._swipe_last = 0.0
    with patch_time(pipeline_mod, 1000.0):
        pipe._swipe(900, [])
    assert ("hotkey", ("alt", "tab")) in mouse.calls
    # Immediately fire again within cooldown -> suppressed.
    pipe._prev_move_sx = 400
    pipe._swipe_accum = 250.0
    with patch_time(pipeline_mod, 1000.1):
        pipe._swipe(900, [])
    assert len([c for c in mouse.calls if c[0] == "hotkey"]) == 1


def test_thumbs_up_in_chat_emits_confirm():
    from unittest.mock import patch

    from conftest import thumb_up_hand

    pipe, mouse, hud, _ = make_pipeline(hands(thumb_up_hand()), mode=Mode.CHAT)
    for _ in range(1):  # one warm-up frame, confirm fires on frame 2
        pipe.step(FRAME)
    with patch("app.perception.pipeline.time.monotonic",
               return_value=1000.0):
        actions = pipe.step(FRAME)
    assert any(a.name == "confirm" for a in actions)


def test_thumbs_up_confirm_is_edge_triggered():
    """Confirm fires once on gesture start, not every frame while held."""
    from unittest.mock import patch

    from conftest import thumb_up_hand

    pipe, mouse, hud, _ = make_pipeline(hands(thumb_up_hand()), mode=Mode.CHAT)
    for _ in range(1):  # confirm fires on the next (second) frame
        pipe.step(FRAME)
    with patch("app.perception.pipeline.time.monotonic",
               return_value=1000.0):
        first = pipe.step(FRAME)
    assert len([a for a in first if a.name == "confirm"]) == 1
    # Holding the thumbs-up must not re-fire.
    with patch("app.perception.pipeline.time.monotonic",
               return_value=1001.0):
        held = pipe.step(FRAME)
    assert all(a.name != "confirm" for a in held)


def test_thumbs_up_rearms_after_other_gesture():
    """Leaving the thumbs-up and returning re-arms the confirm trigger."""
    from unittest.mock import patch

    from conftest import thumb_up_hand, point_hand

    pipe, mouse, hud, tracker = make_pipeline(
        hands(thumb_up_hand()), mode=Mode.CHAT)
    for _ in range(1):
        pipe.step(FRAME)
    with patch("app.perception.pipeline.time.monotonic",
               return_value=1000.0):
        assert any(a.name == "confirm" for a in pipe.step(FRAME))
    # Switch to point (allowed in CHAT) then back to thumbs-up.
    tracker.result = hands(point_hand())
    for _ in range(2):
        pipe.step(FRAME)
    tracker.result = hands(thumb_up_hand())
    for _ in range(1):
        pipe.step(FRAME)
    with patch("app.perception.pipeline.time.monotonic",
               return_value=2000.0):
        again = pipe.step(FRAME)
    assert any(a.name == "confirm" for a in again)


def test_thumbs_down_in_chat_emits_cancel():
    from conftest import thumb_down_hand

    pipe, mouse, hud, _ = make_pipeline(hands(thumb_down_hand()), mode=Mode.CHAT)
    for _ in range(1):  # one warm-up frame, cancel fires on frame 2
        pipe.step(FRAME)
    actions = pipe.step(FRAME)
    assert any(a.name == "cancel" for a in actions)


def test_thumbs_do_not_drag_in_control():
    from conftest import thumb_up_hand

    pipe, mouse, hud, _ = make_pipeline(hands(thumb_up_hand()), mode=Mode.CONTROL)
    for _ in range(2):
        pipe.step(FRAME)
    assert all(c[0] != "drag_start" for c in mouse.calls)


def test_pinch_in_chat_is_inert_but_thumbs_still_fire():
    from conftest import thumb_up_hand

    pipe, mouse, hud, _ = make_pipeline(hands(thumb_up_hand()), mode=Mode.CHAT)
    for _ in range(1):
        pipe.step(FRAME)
    actions = pipe.step(FRAME)
    assert any(a.name == "confirm" for a in actions)


def test_hud_emits_skeleton_and_status():
    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()))
    pipe.step(FRAME)
    types = {e["type"] for e in hud.events}
    assert "skeleton" in types
    assert "status" in types


def test_hud_emits_reticle_on_point():
    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()))
    pipe.step(FRAME)
    reticles = [e for e in hud.events if e["type"] == "reticle"]
    assert reticles
    x, y = reticles[-1]["x"], reticles[-1]["y"]
    assert 0 <= x <= 1000 and 0 <= y <= 800


def test_disallowed_gesture_in_mode_is_inert():
    # CHAT mode does not allow pinch -> no click, no crash.
    pipe, mouse, hud, _ = make_pipeline(hands(pinch_hand()), mode=Mode.CHAT)
    for _ in range(2):
        pipe.step(FRAME)
    assert mouse.calls == []


def test_smoothing_keeps_steady_hand_steady():
    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()))
    for _ in range(3):  # become stable so moves fire
        pipe.step(FRAME)
    first = [c for c in mouse.calls if c[0] == "move"][-1][1:]
    for _ in range(5):
        pipe.step(FRAME)
    last = [c for c in mouse.calls if c[0] == "move"][-1][1:]
    assert first == last  # steady hand -> steady cursor (filter converges)


def test_stats_recorded():
    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()))
    pipe.step(FRAME)
    assert pipe.stats.frames == 1
    assert pipe.stats.hands_seen == 1
    assert pipe.stats.detection_rate == 1.0


def test_fps_tracks_frames_without_detection():
    """fps window must tick even when no hand is in frame."""
    from unittest.mock import patch

    pipe, mouse, hud, _ = make_pipeline(HandTrackingResult(), mode=Mode.CONTROL)
    pipe._window_start = 1000.0
    clock = {"now": 1000.0}

    def _mono():
        clock["now"] += 0.5
        return clock["now"]

    with patch("app.perception.pipeline.time.monotonic", side_effect=_mono):
        pipe.step(FRAME)
        assert pipe.stats.last_fps == 0.0
        pipe.step(FRAME)
        assert pipe.stats.last_fps == 2.0


def test_default_mapper_built_from_control_config():
    from unittest.mock import patch

    cfg = AppConfig()
    cfg.control.gain_x = 5.0
    pipe = None
    with patch("app.perception.pipeline.Camera") as cam, \
            patch("app.perception.pipeline.HandLandmarkerTracker") as tracker:
        pipe = ControlPipeline(
            config=cfg, mouse=FakeMouse(), hud=FakeHUD(),
            frame_source=lambda: (True, FRAME))
    assert pipe.mapper.config.gain_x == 5.0
    assert pipe.mapper.config.invert_x is True
    cam.assert_called_once_with(0, 640, 480)


def test_default_virtual_mouse_reads_control_config():
    from unittest.mock import patch

    cfg = AppConfig()
    cfg.control.failsafe = False
    with patch("app.perception.pipeline.VirtualMouse") as vm, \
            patch("app.perception.pipeline.Camera") as cam, \
            patch("app.perception.pipeline.HandLandmarkerTracker") as tracker:
        ControlPipeline(config=cfg, hud=FakeHUD(),
                        frame_source=lambda: (True, FRAME))
    vm.assert_called_once_with(failsafe=False)
