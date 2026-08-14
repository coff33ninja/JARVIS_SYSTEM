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
| Two-hand pinch apart | Both hands pinch, then palms move apart / together | Zoom in (Ctrl++) / out (Ctrl+-); 1 tick per `two_hand_zoom_threshold` of accumulated palm-center movement | Control, Transfer |
| Grab (fist held still) | Fist, stationary 500 ms | Pick up selected content | Transfer |
| Throw (flick) | Fist → open hand with forward velocity | Send selected content to target device | Transfer |
| Catch (open palm) | Open palm, facing up | Accept incoming content | Transfer |
| Circle / index trace | Index draws circle | Voice command / attention ("Jarvis") | Any |
| Point at zone | Index toward a screen region | Select monitor / window target | Control, Transfer |
| Finger count (secondary) | Secondary hand shows N extended fingers | Select monitor N (1–5); N = number of extended fingers | Control |
| Fist (secondary, held) | Secondary hand in fist, held ≥ `menu_hold_ms` | Open HUD modifier menu (modes / screens / zoom / tune) | Control, Transfer, Chat, Presentation |
| Open palm (secondary, in menu) | Secondary hand open palm while menu open | Cancel / close menu | Control |

## Mode System

| Mode | Active gestures | Purpose |
|---|---|---|
| Idle | Point (for wake), voice keyword | No accidental actions; low CPU |
| Control | All control gestures | Mouse/keyboard/window/media control |
| Chat | Open palm, thumbs up/down, point | Interact with LLM responses |
| Transfer | Grab, Throw, Catch, Open Palm | Cross-device file movement |
| Presentation | Point, swipe, V-sign | Slides/scroll/navigation |

Mode switch triggers: specific gesture (e.g., two-hand pinch apart), voice command, or hotkey override. Voice commands route through `app/control/mode_voice.py` (wired into `VoiceLoop.on_command`): "Jarvis, chat mode" toggles Chat, "control mode" / "go idle" return to Control/Idle, "transfer mode" and "presentation mode" switch the others — shortest-path routed through the mode table, with the agent skipped for pure mode switches and a confirmation phrase spoken.

## Implemented Hotkeys

| Key | Action |
|---|---|
| ESC / q | Quit the control loop |
| F2 | Toggle Idle ↔ Control mode |
| F3 | Toggle Presentation mode |
| F4 | Toggle the on-screen keyboard (Windows `osk.exe`) |
| F5 | Media play/pause |
| F6 | Media next track |
| F7 | Media previous track |
| F8 | Mute / unmute media volume |
| F9 | Media volume down |
| F10 | Media volume up |

The **Circle / index-trace** gesture (the "Jarvis" attention call) is
implemented as a trajectory detector in `app/perception/pipeline.py::_circle`
backed by `app/perception/geometry.py::is_circle_trace`. While the pointing
index is extended (not pinching, not an open palm), the recent index-tip
positions are accumulated; when the trace closes into a circular sweep
(min samples, angular sweep, bounding-box aspect, and start/end closure are
all configurable under `control.circle_*`), an `attention` action fires once
with a cooldown (`control.circle_cooldown_ms`). It works in any mode, and
`ControlPipeline(on_attention=...)` exposes the hook for the agent/voice layer
to respond (main.py logs it today).

Swipe (in Control) fires `Alt+Tab` (swipe right) / `Alt+Shift+Tab` (swipe left) via a configurable threshold (`control.swipe_threshold_px`, default 250 px of accumulated screen motion).

Two-hand spread toggles Control ↔ Transfer (`control.two_hand_spread_threshold`, default 0.4 normalized palm-center distance; held for `control.hold_frames`). While both hands are tracked, the cursor follows the configured preferred hand (`control.preferred_hand`, default "Right"). Open palm acts in Transfer (`catch`) and Chat (`release`), both edge-triggered.

Two-hand pinch-apart zoom: while both hands pinch, palm-center distance changes fire `Ctrl++` (apart) / `Ctrl+-` (together) — one tick per `control.two_hand_zoom_threshold` (default 0.05) of accumulated distance change, active in Control and Transfer. Releasing either pinch (or losing a hand) re-arms the reference so the next pinch starts from a fresh distance.

## Modifier Hand (Phase 2 spatial awareness)

Design grounded in interaction research — see `16_INTERACTION_RESEARCH.md`
(bi-manual fist+point is the canonical mid-air gesture, pie menus cap at
≤8 items / 2 layers, screen-anchored menus beat hand-attached ones, and
user-defined gestures measure better — the case for ADR-011).

The **secondary hand** (the non-`preferred_hand`) acts as a modifier for
multi-monitor targeting, with three levels that never collide with
single-hand gestures (primary-hand fist = drag and primary-hand V-sign =
scroll are untouched):

1. **Passive zone** — when the secondary hand shows no deliberate gesture, its
   lateral position in the frame selects the active monitor (far left → left
   screen, etc.). The primary hand's cursor then maps *relative to that
   monitor's rect* instead of the whole virtual desktop.
2. **Finger count** — the secondary hand showing 1–5 extended fingers selects
   monitor N directly (N = number of extended fingers, 5-monitor cap). This is
   the fast path; monitors beyond 5 fall through to the fist menu.
3. **Fist menu** — the secondary hand in a fist, held for
   `control.menu_hold_ms` (~250 ms), opens a radial menu on the HUD with
   categories **Modes** (Control / Chat / Transfer / Presentation / Idle),
   **Screens** (per-monitor list + "all"), **Zoom** (in/out), **Tune**
   (gain / invert quick sliders), and **Gestures** (dynamic bindings — toggle
   any gesture level on/off, rebind a gesture to another action, tune
   thresholds; see ADR-011). While the menu is open the primary hand
   drives a highlight via the cursor/reticle, a pinch confirms the selection,
   and an open palm cancels.

   The menu is **sticky** once opened: the trigger fist is a momentary
   trigger, so it can relax while the primary hand interacts. It closes on
   **pinch-confirm**, **either-hand open-palm cancel**, **timeout**
   (`control.menu_timeout_ms`), or **hand loss** — never on fist release
   (you can't hold a fist *and* open-palm cancel with the same hand). While
   the menu is open it owns the frame: gesture dispatch (click/catch/release)
   is suspended so the confirming pinch can't also fire a click.

   Implemented in `ControlPipeline._modifier` + `_menu_frame`; the HUD overlay
   (`hud/index.html`) draws the pie via the `menu` event (category ring + leaf
   ring, highlight following the reticle). Modes (via `ModeMachine.goto`,
   which jumps directly — it does not go through the transition table),
   Screens, Zoom, and Tune execute today. The **Gestures** category is live
   (ADR-011): each row toggles that action on/off with a checkmark, and the
   dispatch in `ControlPipeline._dispatch` resolves gestures through the
   `GestureRegistry` instead of hardcoded branches. Rebind-to-another-action
   and threshold tuning remain (see ADR-011). This is the "tune or select
   modes for that scenario" surface, and pulls the *dual-hand / modifier*
   interaction forward from Phase 6 into Phase 2.

All three levels are gated on two hands being tracked and are suppressed by
the two-hand rest-pose guard (a secondary open palm / spread frame stays a
spread, never a monitor selection). Finger-count selection is edge-triggered
and debounced by `control.hold_frames`, so finger jitter (1 vs 2) can't
re-fire. Passive-zone selection fires once per held zone and only when the
target differs from the current monitor; `control.zone_hold_ms` of 0 disables
the level entirely. Fist owns the frame — while the secondary hand is a fist,
zone/count selection is dropped, and the menu has priority over both.

### Collision defaults (decided; remappable in the Gestures menu)

- **5-finger select vs. spread:** spread is defined as *both* hands open palm.
  The finger-count level inspects only the secondary hand, so a lone
  5-finger secondary hand while the primary points = monitor 5, while a
  two-palm frame = Control↔Transfer toggle. No ambiguity.
- **Passive zone anti-thrash:** the active monitor only changes after the
  secondary hand holds the same zone for `control.zone_hold_ms` (~300 ms),
  preventing monitor switching during ordinary two-hand movement. Disable or
  retune in the Gestures menu.

In Presentation mode (F3), V-sign and swipe navigate slides instead of scrolling / switching windows: an upward V-sign sweep or left swipe fires `PageUp` (previous slide); downward or right fires `PageDown` (next slide). Point still moves the cursor as a laser pointer.

Media hotkeys are dispatched through `MediaController` (`app/control/virtual_keyboard.py`), which taps the OS media keys via pynput (`media_play_pause`, `media_next`, `media_previous`, `media_stop`, `media_volume_mute`, `media_volume_up`, `media_volume_down`). Unknown keys are ignored gracefully so the app never crashes on unusual keyboards.

## Detection Requirements

- **Input:** webcam frame → MediaPipe Hands (21 landmarks) + optional Gesture Recognizer classifier
- **Per-frame output:** hand positions, landmark velocity, gesture label, confidence
- **Smoothing:** 1-Euro filter (recommended defaults: `minCutoff=1.0`, `beta=0.007`) to kill jitter without adding lag
- **Debounce / hold times:** gestures that toggle (drag, grab, catch) require a hold window (~500 ms) to avoid accidental triggers; taps (pinch, V-sign) trigger on threshold crossing
- **Confidence thresholds:** minimum landmark confidence ~0.5; only accept gesture labels above configured threshold
- **Accidental-trigger guard:** require 2 consecutive frames at threshold before executing (`control.hold_frames`); ignore gestures if both hands detected in "rest" pose — implemented in `ControlPipeline._rest_pose`, which suppresses the primary open palm (catch/release) while two open palms / a spread are up, since the two-hand spread handler owns that frame. Pinch and two-finger pinch also re-arm whenever the gesture changes, so a click never fires only once per hand-detection.

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

## Calibration UI

When the app is running with the HUD enabled, a calibration server listens on
`http://127.0.0.1:8766/` (link in the HUD's bottom-right corner). The page
edits perception/control values and applies them live — sensitivity and
smoothing changes take effect immediately; camera/resolution changes report
"restart required". The monitor layout is drawn so the mapping area can be
verified against the physical setup. Host/port are configurable via
`hud.calibrate_host` / `hud.calibrate_port`.

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
