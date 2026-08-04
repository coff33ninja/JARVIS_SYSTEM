# 04 — Gesture Vocabulary

Reference spec for gesture → action mapping. Hand landmarks use MediaPipe's 21-point hand model. All gestures configurable; sensitivities live in `config/`.

## Gesture Definitions (index = pointing finger)

| Gesture | Visual | Primary Action | Mode(s) |
|---|---|---|---|
| Point | Index extended, rest curled | Cursor follows index tip | Control |
| Pinch (thumb+index) | Thumb touches index tip | Left click | Control |
| Pinch (thumb+middle) | Thumb touches middle tip | Right click | Control |
| Fist | All fingers curled | Drag (hold = drag, release = drop) | Control |
| Open Palm | All fingers extended | Release / drop / cancel; "catch" in Transfer | Control, Transfer |
| V-Sign | Index + middle extended | Scroll up / down (finger tilt) | Control |
| Thumbs up | Thumb up, fingers curled | Accept / confirm | Chat |
| Thumbs down | Thumb down, fingers curled | Reject / cancel | Chat |
| Swipe (left/right) | Hand sweeps sideways | Alt+Tab / switch window / next track | Control |
| Two-hand spread | Both palms far apart, held ~2 frames | Toggle Control ↔ Transfer mode | Control, Transfer |
| Two-hand pinch apart | Both hands spread | Zoom / launch transfer-ready mode | Control, Transfer |
| Grab (fist held still) | Fist, stationary 500 ms | Pick up selected content | Transfer |
| Throw (flick) | Fist → open hand with forward velocity | Send selected content to target device | Transfer |
| Catch (open palm) | Open palm, facing up | Accept incoming content | Transfer |
| Circle / index trace | Index draws circle | Voice command / attention ("Jarvis") | Any |
| Point at zone | Index toward a screen region | Select monitor / window target | Control, Transfer |

## Mode System

| Mode | Active gestures | Purpose |
|---|---|---|
| Idle | Point (for wake), voice keyword | No accidental actions; low CPU |
| Control | All control gestures | Mouse/keyboard/window/media control |
| Chat | Open palm, thumbs up/down, point | Interact with LLM responses |
| Transfer | Grab, Throw, Catch, Open Palm | Cross-device file movement |
| Presentation | Point, swipe, V-sign | Slides/scroll/navigation |

Mode switch triggers: specific gesture (e.g., two-hand pinch apart), voice command ("Jarvis, transfer mode"), or hotkey override.

## Implemented Hotkeys

| Key | Action |
|---|---|
| ESC / q | Quit the control loop |
| F2 | Toggle Idle ↔ Control mode |
| F4 | Toggle the on-screen keyboard (Windows `osk.exe`) |
| F5 | Media play/pause |
| F6 | Media next track |
| F7 | Media previous track |
| F8 | Mute / unmute media volume |
| F9 | Media volume down |
| F10 | Media volume up |

Swipe (in Control) fires `Alt+Tab` (swipe right) / `Alt+Shift+Tab` (swipe left) via a configurable threshold (`control.swipe_threshold_px`, default 250 px of accumulated screen motion).

Two-hand spread toggles Control ↔ Transfer (`control.two_hand_spread_threshold`, default 0.4 normalized palm-center distance; held for `control.hold_frames`). While both hands are tracked, the cursor follows the configured preferred hand (`control.preferred_hand`, default "Right"). Open palm acts in Transfer (`catch`) and Chat (`release`), both edge-triggered.

Media hotkeys are dispatched through `MediaController` (`app/control/virtual_keyboard.py`), which taps the OS media keys via pynput (`media_play_pause`, `media_next`, `media_previous`, `media_stop`, `media_volume_mute`, `media_volume_up`, `media_volume_down`). Unknown keys are ignored gracefully so the app never crashes on unusual keyboards.

## Detection Requirements

- **Input:** webcam frame → MediaPipe Hands (21 landmarks) + optional Gesture Recognizer classifier
- **Per-frame output:** hand positions, landmark velocity, gesture label, confidence
- **Smoothing:** 1-Euro filter (recommended defaults: `minCutoff=1.0`, `beta=0.007`) to kill jitter without adding lag
- **Debounce / hold times:** gestures that toggle (drag, grab, catch) require a hold window (~500 ms) to avoid accidental triggers; taps (pinch, V-sign) trigger on threshold crossing
- **Confidence thresholds:** minimum landmark confidence ~0.5; only accept gesture labels above configured threshold
- **Accidental-trigger guard:** require 2 consecutive frames at threshold before executing; ignore gestures if both hands detected in "rest" pose

## Throw / Catch Semantics (Phase 4)

1. **Grab:** fist held still ~500 ms over a file/window/selection → content is "picked up"
2. **Throw:** fist transitions to open hand with forward velocity → target zone computed from throw direction (left/right screen, or toward camera = tablet)
3. **Catch:** open palm held toward the camera on the receiving device (or PC auto-accept) → transfer starts
4. **Drop:** open palm after a short throw = cancel

Direction sensing: projected velocity vector of the wrist/mean hand point determines the destination zone in multi-monitor setups. Optional second camera / pose helps resolve "toward tablet".

## Sensitivity / Calibration Parameters

- Camera index, resolution, FPS
- Cursor gain + smoothing cutoff (per axis)
- Pinch threshold (mm between thumb/index tips)
- Fist curl threshold (avg finger curl distance)
- Throw velocity threshold + direction deadzone
- Hold durations (grab, drag, catch)
- Confidence thresholds per gesture
- Per-monitor layout mapping

## Calibration Test Procedure

Run after any camera/monitor change. Each step has a pass criterion; record values in `config/` per profile.

1. **Camera framing:** sit in normal working position; the system draws the tracked hand bounds. Adjust camera so the hand stays in view through a full range of motion. *Pass: hand detected on > 95% of frames during a 60 s wave.*
2. **Cursor mapping:** 4-point grid calibration (corners of the working area). *Pass: cursor reaches each corner without overshoot and rests within 2 cm.*
3. **Pinch:** perform 10 pinches in a row, slowly then quickly. *Pass: 10/10 clicks, no double-fire, no missed clicks.*
4. **Fist drag:** hold a window and drag in a circle twice. *Pass: window follows without dropping or sticking.*
5. **Scroll (V-sign):** scroll up/down 10 ticks. *Pass: no inversions, no accidental clicks.*
6. **Misfire guard:** type normally and move naturally for 5 minutes. *Pass: 0 unintended actions.*
7. **Mode transitions (Phase 2+):** cycle Idle→Control→Chat→Transfer→Presentation twice. *Pass: no stuck modes, each trigger reliable.*
8. **Throw calibration (Phase 4):** 10 throws toward each target zone. *Pass: ≥ 8/10 reach the intended zone; velocity threshold tuned so normal movement never triggers a throw.*

Automate what you can (`scripts/calibrate.py` scaffold) and keep the checklist in this file for manual passes.
