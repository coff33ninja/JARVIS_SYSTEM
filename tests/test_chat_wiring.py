"""End-to-end Idle->Chat voice-trigger flow with shared fake components.

Proves the full wiring docs/02_PROJECT_PLAN.md marks done but never tested as
a flow: a voice utterance ("jarvis chat mode") switches the *same* mode machine
that gates the gesture pipeline, so Chat gestures then act (open palm ->
release), and a second voice command returns to Control.

No hardware: FakeMic/FakeSTT/FakeTTS/StubLLM from test_voice, fake tracker/
mouse/HUD from test_pipeline (09_TESTING integration strategy).
"""

from __future__ import annotations

from conftest import open_hand, pinch_hand, point_hand
from test_pipeline import FRAME, FakeCamera, FakeHUD, FakeMouse, FakeTracker
from test_voice import LOUD, make_loop

from app.config import AppConfig
from app.control.mode_voice import handle_mode_command
from app.control.modes import Mode, ModeMachine
from app.perception.mapping import CursorMapper, MappingConfig
from app.perception.pipeline import ControlPipeline


def _pipeline_with(modes: ModeMachine) -> ControlPipeline:
    return ControlPipeline(
        config=AppConfig(),
        camera=FakeCamera(),
        tracker=FakeTracker(_hand(point_hand())),
        mouse=FakeMouse(),
        mapper=CursorMapper(MappingConfig(screen=(0, 0, 1000, 800))),
        hud=FakeHUD(),
        modes=modes,
    )


def _hand(result):
    from app.perception.hand_tracker import HandTrackingResult

    return HandTrackingResult(hands=[result], handedness=["Right"])


def test_full_idle_to_chat_voice_trigger_flow(store):
    modes = ModeMachine(Mode.IDLE)
    pipe = _pipeline_with(modes)
    loop, agent = make_loop(store, LOUD, ["jarvis chat mode", "jarvis control mode"])
    loop.on_command = lambda cmd: handle_mode_command(cmd, modes)

    # 1) Idle wakes to Control on any tracked hand.
    assert modes.mode is Mode.IDLE
    pipe.step(FRAME)  # wake: open_hand irrelevant in IDLE
    assert modes.mode is Mode.CONTROL

    # 2) Voice triggers Chat: same machine, agent skipped, TTS confirms.
    result = loop.run_once()
    assert result["command"] == "chat mode"
    assert result["mode_change"] is True
    assert modes.mode is Mode.CHAT
    assert agent.llm.calls == []

    # 3) Chat gesture now acts: open palm fires "release" once.
    pipe.tracker.result = _hand(open_hand())
    pipe.step(FRAME)  # debounce frame 1
    actions = pipe.step(FRAME)  # frame 2: release fires
    assert [a.name for a in actions].count("release") == 1
    pipe.step(FRAME)  # edge-triggered: holding does not re-fire
    assert all(a.name != "release" for a in pipe.step(FRAME))

    # 4) Voice returns to Control.
    result = loop.run_once()
    assert result["reply"] == "Control mode."
    assert modes.mode is Mode.CONTROL

    # 5) Control gestures act again (pinch -> click), proving the round trip.
    pipe.tracker.result = _hand(pinch_hand())
    pipe.step(FRAME)
    actions = pipe.step(FRAME)
    assert any(a.name == "left_click" for a in actions)


def test_non_mode_voice_command_does_not_change_mode(store):
    modes = ModeMachine(Mode.CONTROL)
    pipe = _pipeline_with(modes)
    loop, agent = make_loop(
        store,
        LOUD,
        ["jarvis open settings"],
        llm_responses=[{"role": "assistant", "content": "done", "tool_calls": []}],
    )
    loop.on_command = lambda cmd: handle_mode_command(cmd, modes)

    result = loop.run_once()
    assert result["command"] == "open settings"
    assert modes.mode is Mode.CONTROL  # untouched
    assert len(agent.llm.calls) == 1  # agent handled it instead

    # Pipeline still acts as Control afterwards.
    pipe.tracker.result = _hand(point_hand())
    pipe.step(FRAME)
    actions = pipe.step(FRAME)
    assert any(a.name == "move" for a in actions)
