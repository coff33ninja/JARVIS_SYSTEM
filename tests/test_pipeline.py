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


def make_pipeline(result=None, mode=Mode.CONTROL, config=None, monitors=None):
    cfg = config or AppConfig()
    tracker = FakeTracker(result)
    mouse = FakeMouse()
    hud = FakeHUD()
    mapper = CursorMapper(MappingConfig(screen=(0, 0, 1000, 800),
                                        monitors=monitors or []))
    pipe = ControlPipeline(
        config=cfg, camera=FakeCamera(), tracker=tracker, mouse=mouse,
        mapper=mapper, hud=hud, modes=ModeMachine(mode))
    return pipe, mouse, hud, tracker


def hands(hand):
    return HandTrackingResult(hands=[hand], handedness=["Right"])


def _shift(lm, dx, dy):
    return [(x + dx, y + dy, z) for x, y, z in lm]


def two_hands(right, left, right_label="Right", left_label="Left"):
    return HandTrackingResult(hands=[right, left],
                              handedness=[right_label, left_label])


def _spread_result():
    """Two open palms far apart in the frame -> a spread."""
    return two_hands(_shift(open_hand(), 0.3, 0.0),
                     _shift(open_hand(), -0.3, 0.0))


def test_idle_wakes_on_hand():
    pipe, mouse, hud, _ = make_pipeline(hands(open_hand()), mode=Mode.IDLE)
    actions = pipe.step(FRAME)
    assert actions == []
    assert pipe.modes.mode == Mode.CONTROL

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


def test_status_reports_gesture_and_clears_on_loss():
    pipe, mouse, hud, tracker = make_pipeline(hands(point_hand()))
    pipe.step(FRAME)
    statuses = [e for e in hud.events if e["type"] == "status"]
    assert statuses and statuses[-1]["gesture"] == "point"
    # Sustained hand loss clears the shown gesture (and the status throttle
    # would normally gate re-emission; force it here to check the value).
    tracker.result = HandTrackingResult()
    for _ in range(pipe.config.control.lost_grace_frames + 2):
        pipe._last_status_ts = 0.0
        pipe.step(FRAME)
    statuses = [e for e in hud.events if e["type"] == "status"]
    assert statuses[-1]["gesture"] == ""


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

    class _FakeTime:
        now = 1000.0

        @staticmethod
        def monotonic():
            return _FakeTime.now

    with patch("app.perception.pipeline.time.monotonic", _FakeTime.monotonic):
        pipe.step(FRAME)  # no hand: fps stays 0 until a second elapses
        assert pipe.stats.last_fps == 0.0
        _FakeTime.now += 1.0
        pipe.step(FRAME)
        assert pipe.stats.last_fps == 2.0


def test_hud_throttles_skeleton_but_streams_reticle():
    """Skeleton/status are throttled; reticle still broadcasts every frame."""
    from unittest.mock import patch

    from conftest import point_hand

    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()))

    class _FakeTime:
        now = 1000.0

        @staticmethod
        def monotonic():
            return _FakeTime.now

    with patch("app.perception.pipeline.time.monotonic", _FakeTime.monotonic):
        pipe.step(FRAME)
        assert len([e for e in hud.events if e["type"] == "skeleton"]) == 1
        reticles_before = len([e for e in hud.events if e["type"] == "reticle"])
        # Advance well past the skeleton throttle interval.
        _FakeTime.now += 0.2
        pipe.step(FRAME)
        skeletons = [e for e in hud.events if e["type"] == "skeleton"]
        reticles = [e for e in hud.events if e["type"] == "reticle"]
        assert len(skeletons) == 2          # throttled: only 2 across 2 steps
        assert len(reticles) == reticles_before + 1  # reticle not throttled


def test_loss_grace_keeps_smoothing_then_resets():
    """Transient 1-frame loss keeps the filter; sustained loss resets it."""
    from conftest import point_hand

    pipe, mouse, hud, tracker = make_pipeline(hands(point_hand()))
    for _ in range(2):
        pipe.step(FRAME)
    assert pipe._smoothing is not None
    # One lost frame: within grace, smoothing survives.
    tracker.result = HandTrackingResult()
    pipe.step(FRAME)
    assert pipe._smoothing is not None
    # Sustained loss: past grace, the filter fully resets.
    for _ in range(pipe.config.control.lost_grace_frames):
        pipe.step(FRAME)
    assert pipe._smoothing is None


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


def test_two_hand_spread_toggles_transfer_mode():
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CONTROL)
    tracker.result = _spread_result()
    for _ in range(pipe.config.control.hold_frames):
        pipe.step(FRAME)
    assert pipe.modes.mode == Mode.TRANSFER
    # Held spread does not re-fire.
    pipe.step(FRAME)
    assert pipe.modes.mode == Mode.TRANSFER
    # Releasing the spread (one hand) re-arms it; spread again exits Transfer.
    tracker.result = hands(open_hand())
    pipe.step(FRAME)
    tracker.result = _spread_result()
    for _ in range(pipe.config.control.hold_frames):
        pipe.step(FRAME)
    assert pipe.modes.mode == Mode.CONTROL


def test_hands_touching_is_not_a_spread():
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CONTROL)
    tracker.result = two_hands(_shift(open_hand(), 0.05, 0.0),
                               _shift(open_hand(), -0.05, 0.0))
    for _ in range(5):
        pipe.step(FRAME)
    assert pipe.modes.mode == Mode.CONTROL


def test_primary_hand_prefers_right():
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CONTROL)
    # Right hand = fist (would drag), Left hand = point (would move).
    tracker.result = two_hands(_shift(fist(), 0.05, 0.0),
                               _shift(point_hand(), -0.05, 0.0))
    for _ in range(pipe.config.control.hold_frames):
        pipe.step(FRAME)
    assert any(c[0] == "drag_start" for c in mouse.calls)
    assert not any(c[0] == "move" for c in mouse.calls)


def _pinch_zoom_hands(dx):
    """Both hands pinching, palm centers |dx| apart around center."""
    return two_hands(_shift(pinch_hand(), dx, 0.0),
                     _shift(pinch_hand(), -dx, 0.0))


def _zoom_actions(pipe, frames):
    return [a for _ in range(frames) for a in pipe.step(FRAME)]


def test_two_hand_pinch_apart_zooms_in():
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CONTROL)
    tracker.result = _pinch_zoom_hands(0.1)
    assert not [a for a in pipe.step(FRAME) if "zoom" in a.name]  # sets ref
    tracker.result = _pinch_zoom_hands(0.2)  # spread grew by 0.2 -> 4 ticks
    actions = _zoom_actions(pipe, 1)
    assert [a.name for a in actions].count("zoom_in") == 4
    assert not any(a.name == "zoom_out" for a in actions)
    assert [c for c in mouse.calls if c[0] == "hotkey"].count(("hotkey", ("ctrl", "+"))) == 4


def test_two_hand_pinch_together_zooms_out():
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CONTROL)
    tracker.result = _pinch_zoom_hands(0.3)
    pipe.step(FRAME)
    tracker.result = _pinch_zoom_hands(0.2)  # spread shrank by 0.2 -> 4 ticks
    actions = _zoom_actions(pipe, 1)
    assert [a.name for a in actions].count("zoom_out") == 4
    assert not any(a.name == "zoom_in" for a in actions)


def test_two_hand_zoom_ignores_open_palms():
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CONTROL)
    tracker.result = _spread_result()  # open palms, not pinching
    pipe.step(FRAME)
    pipe.step(FRAME)
    assert not [c for c in mouse.calls if c[0] == "hotkey"]


def test_two_hand_zoom_requires_both_pinching():
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CONTROL)
    tracker.result = two_hands(_shift(pinch_hand(), 0.2, 0.0),
                               _shift(open_hand(), -0.2, 0.0))
    for _ in range(3):
        pipe.step(FRAME)
    assert not [c for c in mouse.calls if c[0] == "hotkey"]


def test_two_hand_zoom_not_in_chat():
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CHAT)
    tracker.result = _pinch_zoom_hands(0.1)
    pipe.step(FRAME)
    tracker.result = _pinch_zoom_hands(0.2)
    assert not [c for c in mouse.calls if c[0] == "hotkey"]


def test_two_hand_zoom_rearms_after_release_and_hand_loss():
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CONTROL)
    tracker.result = _pinch_zoom_hands(0.1)
    pipe.step(FRAME)
    tracker.result = _pinch_zoom_hands(0.2)
    assert any(a.name == "zoom_in" for a in pipe.step(FRAME))
    # Release one hand (re-arm), then spread again from the same base.
    tracker.result = hands(pinch_hand())
    pipe.step(FRAME)
    tracker.result = _pinch_zoom_hands(0.1)
    pipe.step(FRAME)  # re-established reference, no tick yet
    tracker.result = _pinch_zoom_hands(0.2)
    actions = _zoom_actions(pipe, 1)
    assert any(a.name == "zoom_in" for a in actions)


def test_open_palm_catch_in_transfer_fires_once():
    pipe, mouse, hud, _ = make_pipeline(hands(open_hand()), mode=Mode.TRANSFER)
    all_actions = []
    for _ in range(3):
        all_actions.extend(pipe.step(FRAME))
    names = [a.name for a in all_actions]
    assert names.count("catch") == 1  # edge-triggered, not per-frame
    assert all(a.gesture == "open_palm" for a in all_actions if a.name == "catch")


def test_open_palm_release_in_chat_fires_once():
    pipe, mouse, hud, _ = make_pipeline(hands(open_hand()), mode=Mode.CHAT)
    all_actions = []
    for _ in range(3):
        all_actions.extend(pipe.step(FRAME))
    names = [a.name for a in all_actions]
    assert names.count("release") == 1


def test_presentation_point_moves_cursor():
    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()),
                                        mode=Mode.PRESENTATION)
    for _ in range(pipe.config.control.hold_frames):
        pipe.step(FRAME)
    assert any(c[0] == "move" for c in mouse.calls)


def test_presentation_pinch_is_inert():
    pipe, mouse, hud, _ = make_pipeline(hands(pinch_hand()),
                                        mode=Mode.PRESENTATION)
    for _ in range(3):
        pipe.step(FRAME)
    assert not any(c[0] in ("click", "right_click") for c in mouse.calls)


def test_presentation_swipe_navigates_slides():
    pipe, mouse, hud, _ = make_pipeline(hands(point_hand()),
                                        mode=Mode.PRESENTATION)
    pipe._prev_move_sx = 400
    pipe._swipe_accum = 0.0
    pipe._swipe_last = 0.0
    pipe._swipe(900, [])  # right sweep = next slide
    assert ("hotkey", ("pagedown",)) in mouse.calls
    pipe._prev_move_sx = 900
    pipe._swipe_accum = 0.0
    pipe._swipe_last = 0.0
    pipe._swipe(200, [])  # left sweep = previous slide
    assert ("hotkey", ("pageup",)) in mouse.calls
    assert ("hotkey", ("alt", "tab")) not in mouse.calls


def test_presentation_v_sign_navigates_slides():
    from conftest import v_sign as v_sign_hand

    pipe, mouse, hud, tracker = make_pipeline(hands(v_sign_hand()),
                                              mode=Mode.PRESENTATION)
    # Stable V-sign (seeds the reference), then move the hand up in the frame.
    for _ in range(2):
        pipe.step(FRAME)
    tracker.result = hands(_shift(v_sign_hand(), 0.0, -0.05))
    pipe.step(FRAME)
    assert any(c[0] == "hotkey" and c[1] == ("pageup",) for c in mouse.calls)
    assert all(c[0] != "scroll" for c in mouse.calls)


# --------------------------------------------------------------------------- #
# Circle / index-trace attention ("Jarvis")
# --------------------------------------------------------------------------- #

def _circle_steps(n=18, r=0.1):
    """Frame-by-frame tracker results sweeping the pointing hand in a circle."""
    import math

    base = point_hand()
    frames = []
    for i in range(n):
        a = 2 * math.pi * i / 16
        frames.append(hands(_shift(base, r * math.cos(a), r * math.sin(a))))
    return frames


def test_circle_trace_fires_attention():
    pipe, mouse, hud, tracker = make_pipeline(hands(point_hand()))
    called = []
    pipe.on_attention = lambda: called.append(1)
    actions = []
    for result in _circle_steps():
        tracker.result = result
        actions.extend(pipe.step(FRAME))
    attn = [a for a in actions if a.name == "attention"]
    assert len(attn) == 1
    assert attn[0].gesture == "circle"
    assert called == [1]


def test_circle_trace_cooldown_prevents_repeat():
    pipe, mouse, hud, tracker = make_pipeline(hands(point_hand()))
    actions = []
    for _ in range(2):
        for result in _circle_steps():
            tracker.result = result
            actions.extend(pipe.step(FRAME))
    assert len([a for a in actions if a.name == "attention"]) == 1


def test_line_sweep_is_not_attention():
    pipe, mouse, hud, tracker = make_pipeline(hands(point_hand()))
    base = point_hand()
    actions = []
    for i in range(24):
        tracker.result = hands(_shift(base, 0.0, 0.1 * i / 24))
        actions.extend(pipe.step(FRAME))
    assert all(a.name != "attention" for a in actions)


def test_breaking_pose_resets_trace():
    """An open palm mid-trace resets the accumulated trajectory."""
    pipe, mouse, hud, tracker = make_pipeline(hands(point_hand()))
    actions = []
    for result in _circle_steps(n=8):  # half a circle, not enough
        tracker.result = result
        actions.extend(pipe.step(FRAME))
    tracker.result = hands(open_hand())  # breaks the trace pose
    pipe.step(FRAME)
    for result in _circle_steps():  # second attempt after the break
        tracker.result = result
        actions.extend(pipe.step(FRAME))
    assert len([a for a in actions if a.name == "attention"]) == 1


# --------------------------------------------------------------------------- #
# Misfire guards
# --------------------------------------------------------------------------- #

def test_pinch_rearms_after_other_gesture():
    pipe, mouse, hud, tracker = make_pipeline(hands(pinch_hand()))
    for _ in range(2):
        pipe.step(FRAME)
    assert len([c for c in mouse.calls if c[0] == "click"]) == 1
    tracker.result = hands(point_hand())
    for _ in range(2):
        pipe.step(FRAME)
    tracker.result = hands(pinch_hand())
    for _ in range(2):
        pipe.step(FRAME)
    assert len([c for c in mouse.calls if c[0] == "click"]) == 2


def test_two_finger_pinch_rearms_after_other_gesture():
    pipe, mouse, hud, tracker = make_pipeline(hands(two_pinch_hand()))
    for _ in range(2):
        pipe.step(FRAME)
    assert len([c for c in mouse.calls if c[0] == "right_click"]) == 1
    tracker.result = hands(point_hand())
    for _ in range(2):
        pipe.step(FRAME)
    tracker.result = hands(two_pinch_hand())
    for _ in range(2):
        pipe.step(FRAME)
    assert len([c for c in mouse.calls if c[0] == "right_click"]) == 2


def test_spread_frame_does_not_fire_catch():
    """Two open palms = spread/rest: mode toggles, catch is suppressed."""
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CONTROL)
    tracker.result = _spread_result()
    actions = []
    for _ in range(pipe.config.control.hold_frames + 1):
        actions.extend(pipe.step(FRAME))
    assert pipe.modes.mode == Mode.TRANSFER
    assert all(a.name != "catch" for a in actions)


def test_two_hand_rest_suppresses_open_palm_in_chat():
    """Both hands up relaxed in Chat must not fire 'release'."""
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CHAT)
    tracker.result = two_hands(_shift(open_hand(), 0.15, 0.0),
                               _shift(open_hand(), -0.15, 0.0))
    actions = []
    for _ in range(4):
        actions.extend(pipe.step(FRAME))
    assert all(a.name != "release" for a in actions)
    # A single open palm still releases.
    tracker.result = hands(open_hand())
    actions = []
    for _ in range(2):
        actions.extend(pipe.step(FRAME))
    assert any(a.name == "release" for a in actions)


def test_two_hand_deliberate_primary_still_acts():
    """Rest-pose suppression only kicks in for rest; a deliberate primary
    pinch still clicks even with a second hand present."""
    pipe, mouse, hud, tracker = make_pipeline(mode=Mode.CONTROL)
    tracker.result = two_hands(_shift(pinch_hand(), 0.1, 0.0),
                               _shift(fist(), -0.1, 0.0))
    for _ in range(2):
        pipe.step(FRAME)
    assert any(c[0] == "click" for c in mouse.calls)


# ------------------------------------------------------------------ #
# Modifier hand scaffold (Phase 2 second-hand interaction)
# ------------------------------------------------------------------ #

def test_modifier_hand_none_with_single_hand():
    pipe, *_ = make_pipeline()
    assert pipe._modifier_hand(hands(open_hand())) is None


def test_modifier_hand_none_without_handedness_labels():
    pipe, *_ = make_pipeline()
    result = HandTrackingResult(hands=[open_hand(), fist()], handedness=[])
    assert pipe._modifier_hand(result) is None


def test_modifier_hand_is_secondary_non_preferred():
    pipe, *_ = make_pipeline()
    mod = pipe._modifier_hand(two_hands(
        _shift(open_hand(), 0.3, 0.0),   # primary (Right)
        _shift(fist(), -0.3, 0.0)))      # secondary (Left)
    assert mod is not None
    assert mod.fist is True
    assert mod.finger_count == 0
    assert mod.open_palm is False


def test_modifier_hand_finger_count():
    pipe, *_ = make_pipeline()
    mod = pipe._modifier_hand(two_hands(
        _shift(point_hand(), 0.3, 0.0),
        _shift(v_sign(), -0.3, 0.0)))
    assert mod is not None
    assert mod.finger_count == 2  # index + middle
    assert mod.fist is False


def test_modifier_hand_open_palm():
    pipe, *_ = make_pipeline()
    mod = pipe._modifier_hand(two_hands(
        _shift(point_hand(), 0.3, 0.0),
        _shift(open_hand(), -0.3, 0.0)))
    assert mod is not None
    assert mod.open_palm is True
    assert mod.finger_count == 4


def test_modifier_hand_lateral_zone_tracks_secondary_x():
    pipe, *_ = make_pipeline()
    # Secondary pushed far left in frame -> LEFT zone.
    mod_left = pipe._modifier_hand(two_hands(
        _shift(open_hand(), 0.3, 0.0),
        _shift(open_hand(), -0.35, 0.0)))
    assert mod_left.lateral.value == "left"
    # Secondary pushed far right -> RIGHT zone.
    mod_right = pipe._modifier_hand(two_hands(
        _shift(open_hand(), -0.3, 0.0),
        _shift(open_hand(), 0.35, 0.0)))
    assert mod_right.lateral.value == "right"


# --------------------------------------------------------------------------- #
# Modifier wiring: fist menu + finger-count / passive-zone monitor selection
# --------------------------------------------------------------------------- #

from unittest.mock import patch  # noqa: E402

from app.control.menu import MenuState  # noqa: E402
from conftest import thumb_up_hand  # noqa: E402


class _Clock:
    now = 1000.0

    @staticmethod
    def monotonic():
        return _Clock.now


def make_two_monitors():
    return [(0, 0, 1000, 800), (1000, 0, 1000, 800)]


def step_actions(pipe, clock_now):
    _Clock.now = clock_now
    with patch("app.perception.pipeline.time.monotonic", _Clock.monotonic):
        return pipe.step(FRAME)


def test_modifier_fist_hold_opens_menu():
    pipe, *_ = make_pipeline(monitors=make_two_monitors())
    result = two_hands(_shift(point_hand(), 0.3, 0.0),
                       _shift(fist(), -0.3, 0.0))
    pipe.tracker.result = result
    step_actions(pipe, 1000.0)  # arms the hold timer
    assert pipe._menu.state is MenuState.CLOSED
    actions = step_actions(pipe, 1000.3)  # 300ms > menu_hold_ms (250)
    assert ("menu.open", ()) in [(a.name, a.args) for a in actions]
    assert pipe._menu.state is MenuState.OPEN


def test_modifier_fist_release_does_not_close_menu():
    """The menu is sticky once open; dropping the trigger fist keeps it."""
    pipe, *_ = make_pipeline(monitors=make_two_monitors())
    two = lambda secondary: two_hands(  # noqa: E731
        _shift(point_hand(), 0.3, 0.0), secondary)
    pipe.tracker.result = two(_shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens
    assert pipe._menu.state is MenuState.OPEN
    pipe.tracker.result = two(_shift(thumb_up_hand(), -0.3, 0.0))
    step_actions(pipe, 1000.4)  # fist relaxed -> thumb up, no deliberate gesture
    assert pipe._menu.state is MenuState.OPEN


def test_modifier_menu_confirm_mode_change():
    """Point up-left into Modes, pinch -> mode.change; no stray click."""
    pipe, mouse, *_ = make_pipeline(monitors=make_two_monitors())
    two = lambda secondary: two_hands(  # noqa: E731
        _shift(point_hand(), -0.3, -0.3), secondary)
    pipe.tracker.result = two(_shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens menu
    pipe.tracker.result = two_hands(_shift(pinch_hand(), -0.3, -0.3),
                                    _shift(fist(), -0.3, 0.0))
    actions = step_actions(pipe, 1000.35)
    names = [a.name for a in actions]
    assert "menu.confirm" in names
    assert ("mode.change", ("control",)) in [(a.name, a.args) for a in actions]
    assert pipe._menu.state is MenuState.CLOSED
    assert not any(a.name == "left_click" for a in actions)
    assert all(c[0] != "click" for c in mouse.calls)


def test_modifier_menu_confirm_screen():
    """Point east into Screens, pinch -> screen.select(0)."""
    pipe, *_ = make_pipeline(monitors=make_two_monitors())
    two = lambda secondary: two_hands(  # noqa: E731
        _shift(point_hand(), -0.3, -0.3), secondary)
    pipe.tracker.result = two(_shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens menu
    pipe.tracker.result = two_hands(_shift(pinch_hand(), -0.3, 0.0),
                                    _shift(fist(), -0.3, 0.0))
    actions = step_actions(pipe, 1000.35)
    assert ("screen.select", (0,)) in [(a.name, a.args) for a in actions]
    assert pipe.mapper.config.active_monitor == 0


def test_modifier_menu_cancel_open_palm():
    pipe, *_ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens menu
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(open_hand(), -0.3, 0.0))
    actions = step_actions(pipe, 1000.35)
    assert "menu.cancel" in [a.name for a in actions]
    assert pipe._menu.state is MenuState.CLOSED


def test_modifier_menu_timeout_closes():
    pipe, *_ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens menu
    actions = step_actions(pipe, 1000.3 + 5.1)  # past menu_timeout_ms (5000)
    assert any(a.name == "menu.close" and a.gesture == "timeout"
               for a in actions)
    assert pipe._menu.state is MenuState.CLOSED


def test_modifier_menu_hand_lost_closes():
    pipe, *_ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens menu
    pipe.tracker.result = HandTrackingResult()  # no hands at all
    actions = step_actions(pipe, 1000.4)
    assert any(a.name == "menu.close" and a.gesture == "hand_lost"
               for a in actions)
    assert pipe._menu.state is MenuState.CLOSED


def test_modifier_finger_count_selects_monitor():
    """Two extended fingers on the secondary -> monitor 2 (index 1)."""
    pipe, *_ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(v_sign(), -0.3, 0.0))
    seen = []
    for i in range(pipe.config.control.hold_frames):
        seen.extend(step_actions(pipe, 1000.0 + 0.05 * i))
    assert ("screen.select", (1,)) in [(a.name, a.args) for a in seen]
    assert pipe.mapper.config.active_monitor == 1


def test_modifier_five_fingers_needs_primary_pointing():
    """Open palm on the secondary = monitor 5 only while the primary points."""
    pipe, *_ = make_pipeline(monitors=[(0, 0, 1000, 800)] * 5)
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(open_hand(), -0.3, 0.0))
    seen = []
    for i in range(pipe.config.control.hold_frames):
        seen.extend(step_actions(pipe, 1000.0 + 0.05 * i))
    assert ("screen.select", (4,)) in [(a.name, a.args) for a in seen]
    assert pipe.mapper.config.active_monitor == 4


def test_modifier_both_open_palms_is_rest_no_select():
    pipe, *_ = make_pipeline(monitors=[(0, 0, 1000, 800)] * 5)
    pipe.tracker.result = two_hands(_shift(open_hand(), 0.1, 0.0),
                                    _shift(open_hand(), -0.1, 0.0))
    seen = []
    for i in range(pipe.config.control.hold_frames + 1):
        seen.extend(step_actions(pipe, 1000.0 + 0.05 * i))
    assert not any(a.name == "screen.select" for a in seen)
    assert pipe.mapper.config.active_monitor is None


def test_modifier_passive_zone_selects_left():
    pipe, *_ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(thumb_up_hand(), -0.35, 0.0))
    step_actions(pipe, 1000.0)  # arms the zone hold
    actions = step_actions(pipe, 1000.35)  # 350ms > zone_hold_ms (300)
    assert ("screen.select", (0,)) in [(a.name, a.args) for a in actions]
    assert pipe.mapper.config.active_monitor == 0


def test_modifier_passive_zone_requires_hold():
    pipe, *_ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(thumb_up_hand(), -0.35, 0.0))
    seen = [*step_actions(pipe, 1000.0)]  # LEFT zone armed
    # Break the hold by drifting back to center before the window elapses.
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(thumb_up_hand(), 0.0, 0.0))
    seen.extend(step_actions(pipe, 1000.1))
    # Re-enter the zone: the hold timer restarts, so nothing fires yet.
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(thumb_up_hand(), -0.35, 0.0))
    seen.extend(step_actions(pipe, 1000.4))
    assert not any(a.name == "screen.select" for a in seen)
    assert pipe.mapper.config.active_monitor is None


def test_modifier_passive_zone_hold_zero_disables():
    cfg = AppConfig()
    cfg.control.zone_hold_ms = 0
    pipe, *_ = make_pipeline(monitors=make_two_monitors(), config=cfg)
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(thumb_up_hand(), -0.35, 0.0))
    seen = []
    for i in range(pipe.config.control.hold_frames + 1):
        seen.extend(step_actions(pipe, 1000.0 + 0.2 * i))
    assert not any(a.name == "screen.select" for a in seen)


def test_modifier_idle_does_not_open_menu():
    pipe, *_ = make_pipeline(mode=Mode.IDLE, monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), 0.3, 0.0),
                                    _shift(fist(), -0.3, 0.0))
    actions = step_actions(pipe, 1000.0)
    assert "menu.open" not in [a.name for a in actions]
    assert pipe._menu.state is MenuState.CLOSED


def test_modifier_none_with_single_hand():
    """A lone hand (primary only) must never act as a modifier."""
    pipe, *_ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = hands(_shift(fist(), 0.3, 0.0))
    step_actions(pipe, 1000.0)
    assert pipe._modifier_hand(pipe.tracker.result) is None
    assert pipe._menu.state is MenuState.CLOSED


def menu_events(hud):
    return [e for e in hud.events if e["type"] == "menu"]


def test_menu_event_broadcast_on_open():
    pipe, _, hud, _ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), -0.3, -0.3),
                                    _shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens menu
    evs = menu_events(hud)
    assert evs, "no menu event emitted"
    last = evs[-1]
    assert last["state"] == "open"
    assert any(c["id"] == "modes" for c in last["categories"])
    assert any(c["id"] == "screens" for c in last["categories"])
    # The reticle was pointing up-left into Modes at open.
    assert last["category"] == "modes"


def test_menu_event_highlight_tracks_reticle():
    pipe, _, hud, _ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), -0.3, -0.3),
                                    _shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens
    # Move the primary reticle east (hand shifted left, selfie mirror).
    pipe.tracker.result = two_hands(_shift(point_hand(), -0.3, 0.0),
                                    _shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.4)
    assert any(e["state"] == "open" and e["category"] == "screens"
               for e in menu_events(hud))


def test_menu_event_confirm_emits_closed():
    pipe, _, hud, _ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), -0.3, -0.3),
                                    _shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens
    pipe.tracker.result = two_hands(_shift(pinch_hand(), -0.3, -0.3),
                                    _shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.35)  # pinch confirms mode.control
    assert menu_events(hud)[-1]["state"] == "closed"


# ------------------------------------------------------------------ #
# ADR-011: registry dispatch + Gestures menu category
# ------------------------------------------------------------------ #

def test_registry_dispatch_resolves_mode_bindings():
    """_dispatch consults the binding registry, not hardcoded branches."""
    pipe, *_ = make_pipeline()
    assert pipe._registry.resolve("pinch", "control") == "click.left"
    assert pipe._registry.resolve("open_palm", "chat") == "release"
    assert pipe._registry.resolve("open_palm", "transfer") == "catch"
    assert pipe._registry.resolve("thumbs_up", "control") is None


def test_gesture_toggle_disables_pinch():
    pipe, mouse, *_ = make_pipeline()
    pipe._registry.set_enabled("click.left", False)
    pipe.tracker.result = hands(pinch_hand())
    seen = []
    for _ in range(pipe.config.control.hold_frames + 2):
        seen.extend(step_actions(pipe, 1000.0))
    assert not any(a.name == "left_click" for a in seen)
    assert not any(c[0] == "click" for c in mouse.calls)


def test_gesture_toggle_reenables_pinch():
    pipe, mouse, *_ = make_pipeline()
    pipe._registry.set_enabled("click.left", False)
    pipe._registry.set_enabled("click.left", True)
    pipe.tracker.result = hands(pinch_hand())
    seen = []
    for _ in range(pipe.config.control.hold_frames + 2):
        seen.extend(step_actions(pipe, 1000.0))
    assert any(a.name == "left_click" for a in seen)


def test_gestures_menu_category_lists_actions():
    pipe, _, hud, _ = make_pipeline(monitors=make_two_monitors())
    pipe.tracker.result = two_hands(_shift(point_hand(), -0.3, -0.3),
                                    _shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens
    ev = menu_events(hud)[-1]
    gestures = next(c for c in ev["categories"] if c["id"] == "gestures")
    ids = [i["id"] for i in gestures["items"]]
    assert ids == list(pipe.DISPATCH_ACTIONS)
    # Rows ship their live enabled state (checkmark).
    row = next(i for i in gestures["items"] if i["id"] == "click.left")
    assert row["checked"] is True


def test_gestures_menu_confirm_toggles_binding():
    """Confirming the row under the pointer flips that action off."""
    pipe, _, hud, _ = make_pipeline(monitors=make_two_monitors())
    two = lambda secondary: two_hands(  # noqa: E731
        _shift(point_hand(), 0.3, -0.3), secondary)  # top-left = Gestures wedge
    pipe.tracker.result = two(_shift(fist(), -0.3, 0.0))
    step_actions(pipe, 1000.0)
    step_actions(pipe, 1000.3)  # opens
    step_actions(pipe, 1000.33)  # highlight Gestures category
    assert pipe._menu.category_idx == 4
    # The row under the Gestures wedge is item 7 (catch).
    pipe.tracker.result = two_hands(_shift(pinch_hand(), 0.3, -0.3),
                                    _shift(fist(), -0.3, 0.0))
    actions = step_actions(pipe, 1000.35)  # pinch confirms the same row
    assert ("gesture.toggle", ("catch", False)) in [
        (a.name, a.args) for a in actions]
    # open_palm no longer resolves in Transfer -> catch is inert.
    assert pipe._registry.resolve("open_palm", "transfer") is None
    assert pipe._registry.resolve("open_palm", "chat") == "release"
    # The re-broadcast carries the unchecked row.
    ev = menu_events(hud)[-1]
    gestures = next(c for c in ev["categories"] if c["id"] == "gestures")
    row = next(i for i in gestures["items"] if i["id"] == "catch")
    assert row["checked"] is False
