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

## Zone & direction detection

- Compute the virtual-screen point and classify it into zones: per-monitor rectangles (from `EnumDisplayMonitors`), plus named regions ("left screen", "right screen", "edge").
- Throw-direction (Phase 4): derive a velocity vector in camera space, project it onto the virtual desktop, and let it decay past the nearest zone border → target device/zone.
- "Point at a screen": pointing ray from hand position toward screen plane → intersect with monitor rectangles.

## Mixed-DPI handling (critical)

- Get per-monitor scale from `GetDpiForMonitor` / the per-monitor DPI awareness APIs.
- **Never mix physical and logical coordinates.** Compute mapping in logical (virtual-desktop) coordinates, then let Windows scale cursor targets — or convert explicitly when the target is a physical pixel.
- Set the process DPI awareness to **per-monitor v2** (`SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)`) so the transparent HUD window doesn't blur on scaled monitors.
- Test matrix: same DPI on all monitors; mixed 100%/125%/150%; monitors at different resolutions; negative-origin left-of-primary layouts.

## Calibration (per user setup)

1. Point at each monitor corner in turn (or use a 4-point grid) → record homography.
2. Store per-profile: homography matrix, monitor rectangles, scale factors.
3. Re-run after changing camera position or monitor layout.

## HUD placement

- Create one borderless always-on-top window spanning the virtual desktop, or one per monitor (better for independent DPI).
- The HUD renders in logical coordinates; the window's DPI awareness handles scaling. Keep interactive HUD elements (reticle, panels) away from cursor-clamped edges to avoid fight-between-hand-and-mouse confusion.

## Validation

- `tests/integration/test_mapping.py`: pure math tests using synthetic monitor layouts incl. mixed DPI + negative origin.
- Manual acceptance: cursor lands within a 2 cm radius of the intended target on each monitor; no "jump" when crossing monitor borders.
