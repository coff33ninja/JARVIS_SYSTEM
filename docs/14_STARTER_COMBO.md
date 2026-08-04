# 14 — Starter Combos (Which Repos to Use)

The chat named many existing projects. This doc answers the open question: **fork-and-extend vs. build-from-scratch**, per layer. Recommendation: **build the core, borrow the wheels.**

## Decision: build core, borrow wheels

Reasoning:
- Gesture tracking + HUD + agent = our differentiator; those we own.
- Virtual mouse, throw detection, and HUD aesthetics already exist and are battle-tested → borrow/adapt, don't reinvent.
- Most listed repos are single-purpose scripts; forking them wholesale drags in their opinions and tech debt.

## Layer-by-layer

### 1. Virtual mouse/keyboard — ADAPT, don't fork
| Repo | What to take |
|---|---|
| `ArdaGral06/hand-gesture-pc-control` | gesture→mouse mapping, click/drag/scroll logic, Alt+Tab |
| `oleg-putseiko/gesture-control` | plugin architecture pattern for our tool layer |
| `Ns81000/Vision-Mouse` | offline packaging, tray icon, global hotkey toggle patterns |

Use them as reference implementations for our `control/` layer; port the gesture-state logic, keep our own interfaces.

### 2. HUD aesthetic — STEAL the visuals
| Repo | What to take |
|---|---|
| `quiet-node/gesture-lab` | Three.js holographic environment + pinch interaction ideas |
| `vinayak-hariharno/Jarvis-Mark-XI-AR-Hud` | glassmorphism HUD layout, reticle, panels |
| `xxjun9527/jarvis-holographic` | HUD + LLM integration pattern, sound effects |

Pieces to lift: shader/particle techniques, HUD component layout, "flying icon" throw animation concept. All go into `hud/` as our own frontend.

### 3. Throw/catch gesture layer — STUDY these
| Repo | What to take |
|---|---|
| `MAliffadlan/magic_file_transfer` | fist→open-hand→file lands pattern; MediaPipe receive side |
| `sachinlodhi/gesture_drop` | grab/mark/throw/drop state machine between two devices |

Adopt their gesture-state transitions (grab → hold → throw → drop), but drive transfer through our LocalSend bridge.

### 4. Agent brain — INTEGRATE
| Tool | Role |
|---|---|
| `OpenInterpreter/open-interpreter` | reference for LLM-controlled computer tools |
| `Continue` / `Aider` | reference for tool-calling loops |
| Ollama | the actual runtime |

Write our own thin agent loop (LLM client + tool registry + context) so we control safety (T5 in 11_PRIVACY.md) and latency. Don't fork a full agent framework in.

### 5. Music/media extras (optional, stretch)
| Repo | Note |
|---|---|
| `collidingScopes/arpeggiator`, `amerob/GestureSynth` | browser instruments — could become a HUD "instrument mode" later |
| `khankhushi/Moosic` | emotion→music idea for ambient personalization |

## Suggested baseline combo to start Phase 1

1. **Fork nothing.** Scaffold from `03_ARCHITECTURE.md` folder structure.
2. Port mouse mapping from `hand-gesture-pc-control` (small, clean, single-purpose).
3. Copy the reticle/glass panel styling from `Jarvis-Mark-XI-AR-Hud`.
4. Use `magic_file_transfer`'s gesture-state model when building Phase 4.

This gets a working vertical slice in days instead of months, and keeps the codebase ours.
