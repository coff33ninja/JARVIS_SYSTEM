# 16 — Interaction Research Grounding

Research synthesis behind the Phase 2 spatial-awareness / modifier-hand /
fist-menu design (04_GESTURE_VOCABULARY.md, 13_MULTIMONITOR.md, ADR-011).
Collected as the *Iron Man / Jarvis* interaction paradigm plus the HCI
literature on mid-air gesture menus. This is a design-grounding note, not a
spec; numbers here are research findings, and the config defaults that matter
are pinned in 04 and 13.

## The Iron Man / Jarvis paradigm (what the breakdowns actually teach)

Sources: Sci-Fi Interfaces "Iron Man HUD: A Breakdown" (scifiinterfaces.com),
UX Matters "The User Experience of Iron Man" (uxmatters.com).

1. **The cinematic HUD is famous but bad UX.** Both breakdowns criticize the
   HUD's complex layering and translucency against "the limits of human
   perception" — Tony's interface is described as a "massive distraction."
   The design corollary for us is already the project principle *"cinematic
   but useful"*: the fist menu must be on-demand, fast-dismissing, and
   low-opacity by default; the HUD never blocks daily usability.
2. **Modality depends on hand state.** In the suit, input shifts to head/eye
   gaze + voice when the hands are occupied, and back to hands when they're
   free (designing, manipulating the 3D workspaces). Corollary: the fist menu
   and voice are complementary surfaces, not competing ones — use whichever
   hand is free, and let voice confirm/query the same actions the menu offers.
3. **Jarvis goes beyond the literal request.** The canonical example: asked
   "how many people are in the air?", Jarvis answers *and* highlights where
   they are. Corollary for the fist menu / agent integration: after an action
   resolves, offer the next step (or the confirmation phrase) instead of a
   bare execute — the menu is the tactile half of a proactive assistant.

## HCI literature on mid-air gestures and menus

### Bi-manual gesture taxonomy — the modifier hand is canonical

- **"A Survey of Mid-Air Gestures in HCI for Maximized Agreement Across
  Domains"** (ACM CHI '23, DOI 10.1145/3544548.3581420) builds a 22-gesture
  consensus set and a taxonomy across Nature / Binding / Form / Flow. Its
  *Multiple / bi-manual* class names **"clench the right hand into a fist and
  move the index finger of the left hand" as the canonical example** — a
  modifier hand in a command pose (fist) while the other hand points. This is
  exactly the secondary-fist + primary-point design in 04.
- **Fist as a command/clutch gesture:** mid-air translation studies found fist
  interaction "faster, more fun, and intuitive" than palm for browsing and
  object translation (Identifying the Usability Factors of Mid-Air Hand
  Gestures for 3D Virtual Model Manipulation). Fist-as-clutch is a tested
  engagement metaphor, supporting the fist-held menu trigger over alternatives.

### Menu geometry — radial/pie with strict limits

- **"Depth and Breadth of Pie Menus for Mid-Air Gesture Interaction"** (2020):
  breadth **≤ 8 items per layer** is the key to accuracy; **two layers** is
  the performance sweet spot (breadth drives accuracy + reaction time, depth
  only reaction time). The fist menu stays within this: ≤ 5 categories, one
  sub-level.
- **"Depth-based 3D gesture multi-level radial menu"** (IEEE VR 2016, Davis et
  al.): multi-level radial menus driven by freehand gestures work for
  selection/manipulation — evidence for the category→item two-level structure.
- **"Radial Menu for VR Based on Wrist Rotation"** (SVR '23): angle-based
  highlight on a menu attached to the hand eliminates extra movement. We adopt
  the *angle/highlight* idea but drive the highlight with the primary hand's
  reticle position instead, since the menu is cursor-anchored.

### Placement — anchor to the screen, not the hand

- **"Comparison of Radial and Panel Menus in VR"** (Monteiro et al., IEEE
  Access 2019): all menu types performed, but **wall/screen-fixed menus give a
  better overview** and better action perception than hand-attached ones.
  Corollary: the fist menu renders anchored to the cursor/reticle, not glued
  to the hand that summoned it.

### Gesture authoring — users want to define their own

- **Elicitation studies** (user-defined gesture sets, e.g. "A User-based Mid-Air
  Hand Gesture Set" 2021 and the CHI '23 survey's agreement analysis) show
  user-defined gestures achieve high cross-user agreement and learnability.
  This is direct evidence for ADR-011: the *dynamic bindings* registry is not
  just convenience — letting users remap gestures in the menu is measurably
  better UX than a fixed vocabulary.

### Pointing precision

- A HUD segment study (3 vs 4 segments, index-finger pointing) found the
  **3-segment HUD superior in interaction time and error rate** for
  mid-air segment selection. When the menu/monitor-picker renders zones or
  segments, keep the visible division count low (3 works best per segment).

## Concrete decisions already taken from this research

| Finding | Decision |
|---|---|
| HUD is a distraction if always-on | Fist menu is on-demand, `menu_timeout_ms` auto-close, low opacity |
| Hand-state-dependent modality | Fist menu + voice are complementary surfaces (both wired in Phase 2/3) |
| Bi-manual fist+point is canonical | Secondary-fist trigger + primary-point navigation (04) |
| Fist-as-clutch is fast + intuitive | `menu_hold_ms` ~250 ms grip-to-open |
| Pie: ≤8 items, 2 layers | Menu capped at ≤5 categories, one sub-level |
| Screen-anchored menus win | Menu renders at reticle/cursor position, not on the fist hand |
| User-defined gestures help | ADR-011 dynamic bindings registry, editable in the Gestures menu |
| 3 segments best for pointing | Keep zone/segment counts low (3 per axis) in HUD pickers |

## Open questions for a future pass

- Depth: a single webcam has no reliable hand Z. 2D zones (left/right/edge)
  work today; "toward camera" targets stay Phase 4 (throw direction) until a
  second camera or pose model adds depth (13_MULTIMONITOR).
- Gaze estimation (Phase 6) would add the hands-occupied input channel from
  the Iron Man breakdown; until then voice + the modifier hand cover it.
