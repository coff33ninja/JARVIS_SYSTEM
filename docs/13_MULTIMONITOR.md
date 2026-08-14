# 13 — Multi-Monitor Mapping

How hand position on the webcam maps to cursor coordinates across one or more monitors, including mixed-DPI setups (Windows).

## Coordinate systems

| Space | Origin | Notes |
|---|---|---|
| Camera frame | top-left of frame | pixels, 640x480 (configurable) |
| Virtual screen | Windows virtual screen origin (can be negative) | union of all monitors |
| Physical screen | monitor-specific | per-monitor DPI |

## Mapping approach

1. **Hand → camera plane:** normalize index-finger landmark to `[0,1]` in the camera frame.
2. **Camera plane → virtual screen:** apply a calibration homography (4-point calibration) that maps the webcam view to the *entire virtual desktop bounding box*. This is more robust than a simple linear scale because camera placement varies.
3. **Virtual screen → physical monitor:** Windows handles the virtual→physical split; we only need to know which monitor the point lands on (for zone detection and cursor clamping).

> **Current implementation (Phase 1):** `CursorMapper.to_screen`
> (`app/perception/mapping.py`) uses a fixed anchor + gain mapping around the
> frame center (`control.gain_x` / `gain_y`, `invert_x` / `invert_y`) with no
> homography. **Phase 2 plan:** replace this with a fitted projective
> homography (4-point, DLT, 3×3 matrix stored in `MappingConfig.calibration`)
> so camera placement/angle is compensated. `to_screen` then applies the
> homography instead of the gain formula; the gain/invert knobs remain as a
> fallback until a calibration exists.

## Zone & direction detection

- Compute the virtual-screen point and classify it into zones: per-monitor rectangles (from `EnumDisplayMonitors`), plus named regions ("left screen", "right screen", "edge"). Add `zone_for(nx, ny)` returning a named zone for HUD rendering and Phase 4 throw direction.
- **Active monitor:** `MappingConfig.active_monitor` (int or `None` = whole virtual desktop). When set, `to_screen` maps into that monitor's rect (re-centered) instead of the union — this is the target for second-hand screen switching.
- Throw-direction (Phase 4): derive a velocity vector in camera space, project it onto the virtual desktop, and let it decay past the nearest zone border → target device/zone.
- "Point at a screen": pointing ray from hand position toward screen plane → intersect with monitor rectangles.

## Second-hand screen switching (modifier hand)

While two hands are tracked, the secondary (non-`preferred_hand`) hand
selects the active monitor with three levels (see 04_GESTURE_VOCABULARY.md):

1. **Passive zone** — secondary hand's lateral position picks the monitor,
   gated by `control.zone_hold_ms` (~300 ms) in the same zone to prevent
   thrash during ordinary two-hand movement (tunable/disableable in the
   Gestures menu).
2. **Finger count** — 1–5 extended fingers = monitor 1–5 (5-monitor cap; monitors beyond 5 via the fist menu).
3. **Fist menu** — secondary fist held ≥ `menu_hold_ms` opens a HUD radial menu (Modes / Screens / Zoom / Tune); primary hand points, pinch confirms, open palm cancels.

Selecting a monitor sets `active_monitor`, and the primary cursor re-centers on
that monitor's rect. A spread frame is always owned by the spread handler
(never treated as a monitor selection).

**Implemented (Phase 2 wiring, `ControlPipeline._modifier`):** all three
levels are live — passive zone and finger count edge-trigger
`screen.select` actions (finger count debounced by `control.hold_frames`),
and the fist menu is a momentary trigger that stays open (sticky) until
pinch-confirm, either-hand open palm, `menu_timeout_ms`, or hand loss. The
menu executes `mode.change` (via `ModeMachine.goto`), `screen.select`, zoom,
and tune actions; the Gestures category is deferred to the registry-dispatch
slice.

## Mixed-DPI handling (critical)

- Get per-monitor scale from `GetDpiForMonitor` / the per-monitor DPI awareness APIs.
- **Never mix physical and logical coordinates.** Compute mapping in logical (virtual-desktop) coordinates, then let Windows scale cursor targets — or convert explicitly when the target is a physical pixel.
- Set the process DPI awareness to **per-monitor v2** (`SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)`) so the transparent HUD window doesn't blur on scaled monitors.
- Test matrix: same DPI on all monitors; mixed 100%/125%/150%; monitors at different resolutions; negative-origin left-of-primary layouts.

## Calibration (per user setup)

Two phases of "spatial awareness" calibration, both stored per-profile
(homography matrix, monitor rectangles, scale factors) and re-run after
changing camera position or monitor layout:

1. **Guided 4-corner calibration (primary):** the calibration UI (8766)
   shows the current target corner; the user points an extended index finger
   at it and pinches. While a session is armed, a pinch edge records the
   normalized index tip instead of clicking (`ControlPipeline.arm_calibration`,
   `app/calibrate/session.py`). After the 4th corner the homography is fit
   (DLT, 4 point correspondences), applied live to the mapper, and saved.
   Degenerate fits (duplicate/collinear corners) reset all captures so the
   user restarts with 4 distinct points. The corner reticle on the transparent
   HUD overlay is deferred — the calibrate page renders the target for now.
2. **Passive refinement (optional, off by default):** while the user moves the
   cursor with gestures, the system accumulates (hand position → cursor
   target) pairs and periodically fits a RANSAC-refined homography, replacing
   the guided one only when the reprojection error is clearly better. Guards:
   only in Control mode, minimum samples before fitting, and a
   `control.passive_calibrate` enable flag.

## HUD placement

- Create one borderless always-on-top window spanning the virtual desktop, or one per monitor (better for independent DPI).
- The HUD renders in logical coordinates; the window's DPI awareness handles scaling. Keep interactive HUD elements (reticle, panels) away from cursor-clamped edges to avoid fight-between-hand-and-mouse confusion.

## Validation

- `tests/integration/test_mapping.py`: pure math tests using synthetic monitor layouts incl. mixed DPI + negative origin.
- Manual acceptance: cursor lands within a 2 cm radius of the intended target on each monitor; no "jump" when crossing monitor borders.
