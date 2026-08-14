# 06 — Decision Log (ADRs)

Architecture Decision Records. Each entry records a decision made during planning, the context, the options considered, and the chosen path. Append new decisions as they're made; never silently change a past decision — supersede it instead.

## ADR-001: LocalSend as the transfer backend

- **Status:** Accepted
- **Context:** The "throw / catch" layer needs a reliable way to move files between tablet ↔ PC over LAN. Options: build a custom WebSocket/HTTP server, use PairDrop/Snapdrop (browser-based), or use LocalSend.
- **Options:** (a) Custom WebSocket/HTTP server — full control, but we'd own crypto, discovery, and platform apps; (b) PairDrop/Snapdrop — browser-based, but mobile flow is awkward and less polished; (c) LocalSend — mature, cross-platform (Win/macOS/Linux/Android/iOS), encrypted, discovery built-in.
- **Decision:** LocalSend as primary backend; custom trigger API wraps it. Keep a thin abstraction so a custom server or PairDrop can swap in later.
- **Consequences:** We don't rebuild transfer/crypto. We must integrate with LocalSend's automation surface (CLI/API) which may lag; the trigger layer must tolerate it.

## ADR-002: Python core + web HUD, not Electron/Tauri or pure Python UI

- **Status:** Accepted
- **Context:** Need a transparent always-on-top HUD across multiple monitors plus a Python ML/agent core.
- **Options:** (a) Electron/Tauri full app — nice packaging, but couples the whole system to Node/Rust toolchain; (b) Pure Python UI (PyQt/Dear PyGui) — simplest integration but weakest for rich 3D holographic visuals; (c) Python core + web frontend in a transparent Chromium window — best of both: Python owns vision/control/agent, web owns visuals (Three.js).
- **Decision:** Python core serving a web HUD via WebSocket/HTTP; the HUD runs in a transparent, always-on-top, borderless Chromium window. Keep the HUD protocol as plain JSON events so the frontend could move to Electron/Tauri later without touching the core.
- **Consequences:** Two runtimes to manage; must handle window transparency reliably on Windows (Chromium `--transparent` / `use_rgba` quirks).

## ADR-003: Ollama as default local LLM, OpenAI-compatible API everywhere

- **Status:** Accepted
- **Context:** The "brain" layer needs a local LLM with tool calling and an easy swap path to cloud APIs.
- **Options:** Ollama, LM Studio, vLLM, text-generation-webui, or direct cloud APIs.
- **Decision:** Default to Ollama because it is the easiest install and has solid tool/function calling. All agent code talks to the LLM through an OpenAI-compatible client so swapping to LM Studio, vLLM, or a cloud provider is a config change, not a code change.
- **Consequences:** Ollama's tool-calling quality varies by model; we keep a small compatibility layer and document per-model quirks.

## ADR-004: 1-Euro filter for gesture smoothing

- **Status:** Accepted
- **Context:** Raw landmark positions jitter at webcam resolution, causing cursor shakiness; heavy smoothing adds perceived latency.
- **Options:** Exponential moving average (EMA), Kalman filter, 1-Euro filter.
- **Decision:** 1-Euro filter (adaptive low-pass: min cutoff + speed-dependent beta). Defaults `min_cutoff=1.0`, `beta=0.007`, tune per axis during calibration. It's the de-facto standard in gesture HCI and preserves responsiveness during fast movement.
- **Consequences:** Slight added CPU cost (negligible); parameters must be calibrated per camera/monitor setup.

## ADR-005: Local-first privacy default, cloud opt-in only

- **Status:** Accepted
- **Context:** The system watches a webcam and can read screen content. Data handling is a core product decision.
- **Decision:** Everything runs locally by default. Camera frames, gestures, screen captures, and transfers stay on the LAN. Cloud LLM/vision APIs are opt-in per-feature and clearly labeled. Include a camera kill switch and a local-only mode.
- **Consequences:** Heavier local hardware requirements for the LLM; we document the tradeoff and fallback behavior when the local model is insufficient.

## ADR-006: Windows-first platform focus

- **Status:** Accepted
- **Context:** Primary user environment is Windows with multi-monitor.
- **Decision:** Target Windows first (Win32 input injection, per-monitor DPI). Keep the perception and transfer layers OS-agnostic so a later port to Linux/macOS is isolated to the control and HUD layers.
- **Consequences:** Some code paths (window management, DPI mapping, transparent window) are Windows-specific and must stay behind interfaces.

## ADR-007: Mode machine to prevent accidental actions

- **Status:** Accepted
- **Context:** A broad gesture set can misfire during normal movement (scratching face, picking up a cup, etc.).
- **Decision:** Enforce a mode machine (Idle / Control / Chat / Transfer / Presentation). Each mode whitelists a subset of gestures. Confidence + hold-time + consecutive-frame checks gate execution. Idle mode requires an explicit wake (voice keyword or gesture).
- **Consequences:** Slightly higher cognitive load to switch modes; mitigated by predictable, discoverable triggers and hotkey overrides.

## ADR-008: uv + pyproject.toml, cache bypassed off the system drive

- **Status:** Accepted
- **Context:** C: has very little free space and system Python installs/global caches are restricted. The project needed a reproducible, fast dependency workflow that doesn't touch system locations.
- **Options:** (a) pip + `requirements.txt` (previous default) — global/venv pip, system-dependent, no lockfile; (b) poetry — heavier, slower resolver; (c) uv + `pyproject.toml` — Rust-fast, single source of truth, managed Pythons, proper lockfile.
- **Decision:** Use uv as the sole package/venv/Python manager. `pyproject.toml` holds dependencies; `uv.lock` pins the tree; `[tool.uv]` sets `cache-dir = "D:/uv-cache"`, `managed = true`, `python-preference = "managed"` so uv installs its own CPython and caches entirely off C: (bypassing system cache/install restrictions). All pip usage banned; project script `scripts/ensure-uv.ps1` bootstraps uv where missing.
- **Consequences:** Requires uv installed (one-line bootstrap); `UV_PYTHON_INSTALL_DIR` must be set as an env var (not a pyproject key) if managed Pythons should also leave C:. Faster, reproducible, no global pollution.

## ADR-009: SQLite-backed hybrid recall memory for the agent

- **Status:** Accepted
- **Context:** The Phase 3 agent needs persistent long-term memory (facts, user preferences, entities) plus conversation history so Jarvis can recall context across sessions. No memory subsystem was specified in the planning docs.
- **Options:** (a) A purpose-built vector database (ChromaDB / LanceDB / FAISS) — best semantic recall, but a heavy dependency and external service; (b) in-memory only — trivially simple but loses everything on restart; (c) SQLite + FTS5 with optional Ollama embeddings — zero new dependencies, local-first, graceful degradation to keyword recall when embeddings are unavailable.
- **Decision:** SQLite-backed store in `app/agent/recall/` with an FTS5 keyword index as the always-on recall path, plus an optional semantic layer that embeds rows through Ollama's OpenAI-compatible embeddings endpoint (the `openai` client is already a dependency). The retriever fuses keyword and semantic scores with configurable weights; if the embedder is down or disabled, recall degrades to keyword-only (ADR-005, graceful degradation).
- **Consequences:** Keyword recall always works with no external services. Semantic recall requires Ollama running with an embedding model pulled, and currently scans stored vectors linearly (acceptable at MVP scale; swap in a real vector index in Phase 6 if it grows). All content stays on disk locally, consistent with ADR-005.

## ADR-010: Hand-rolled tool loop with a pluggable tool registry

- **Status:** Accepted
- **Context:** The Phase 3 agent needs tool calling (open apps, switch windows, web search, memory). `14_STARTER_COMBO.md` decided against forking a full agent framework.
- **Options:** (a) Open Interpreter / Continue / other agent framework; (b) a thin hand-rolled loop over the OpenAI-compatible chat API with a Python tool registry.
- **Decision:** Thin `Agent` loop (`app/agent/agent.py`) over the chat API with a `ToolRegistry` of pure-Python functions exposing JSON-schema tool definitions. Memory is exposed as `recall` / `remember` tools, so long-term memory is used exactly like any other tool. Tool iteration is bounded (`max_tool_iterations`), and models that reject tool requests (HTTP 400, e.g. `smallthinker`) are retried once without tools so the agent degrades gracefully.
- **Consequences:** We own iteration bounds, error handling, and tool safety. Per-model tool-calling quirks surface at the compatibility layer (`llm.py`), consistent with ADR-003.

## ADR-011: Data-driven gesture bindings, editable live from the HUD menu

- **Status:** Accepted (Phase 2)
- **Context:** With the modifier-hand + fist-menu surface, the user wants the gesture setup to be "dynamic to a point": reassign gestures, toggle them on/off, and tune thresholds in-session rather than editing YAML or code. Today gesture→action dispatch is hardcoded in `ControlPipeline` (`app/perception/pipeline.py`), and each gesture needs code to add.
- **Options:** (a) Keep hardcoded dispatch, menu only toggles existing levels — simplest, but every new gesture variation is a code change; (b) full rule engine / state machine with arbitrary gesture→action DSL — flexible but complex and hard to debug; (c) a data-driven registry: stable action IDs (e.g. `cursor.move`, `click.left`, `mode.chat`, `screen.monitor_3`) bound to gesture conditions, persisted in config, editable via the fist menu, with uniqueness enforcement.
- **Decision:** (c). Introduce a gesture registry keyed by action ID; `ControlPipeline` dispatch resolves bindings from the registry instead of hardcoded branches. The fist menu's **Gestures** category edits bindings live (rebind, toggle, thresholds) with an in-menu collision warning when two conditions map to the same action or one condition is claimed twice.
- **Status (Phase 2):** Implemented end to end. `ControlPipeline._dispatch` resolves each gesture through `GestureRegistry` (`app/control/registry.py`); the Gestures menu rows are per-gesture toggles with a live checkmark, plus a "Rebind…" row that re-points a gesture at any dispatch action via a two-level picker (applied live; a collision keeps the picker open with an in-menu warning). The click/catch edge flags now re-arm per-gesture, so a rebound gesture fires its edge once per stable onset. A Thresholds category tunes each classification threshold with Increase / Decrease / Reset, applies it live to the hot-path `classify()` calls, and persists it to the config file. `attention` (circle) and `mode.transfer_toggle` (spread) dispatch outside `_dispatch` and are intentionally not listed, since toggling them would lie.
- **Consequences:** New gesture variations become config/bindings, not code. Requires refactoring the dispatch in `pipeline.py` to consult the registry, a config schema for bindings, and menu plumbing. Registry uniqueness is the invariant that keeps collisions (e.g. 5-finger select vs. spread) resolvable at runtime instead of baked in. Note: `GestureRegistry` deep-copies its seed bindings, so toggling never leaks between registries or back into `DEFAULT_BINDINGS`.

## ADR-012: Guided 4-corner pinch calibration for spatial mapping

- **Status:** Accepted (Phase 2), implemented
- **Context:** Cursor mapping defaults to a linear gain/invert formula, which
  breaks as soon as the camera placement or the multi-monitor layout differs
  from the assumed plane. `13_MULTIMONITOR.md` calls for a per-profile
  homography from 4 screen-corner correspondences; `app/perception/calibration.py`
  already ships a pure-DLT `fit_homography`.
- **Options:** (a) Page-button capture — the user clicks "capture" at each
  corner in the 8766 form; deterministic and trivially testable, but the page
  has no index-tip signal and it fights the gesture-first UX; (b) pinch-driven
  capture — the pipeline is armed and a pinch edge records the normalized
  index tip instead of clicking, matching the documented "point and pinch"
  flow; (c) a dedicated calibration mode in the mode machine — cleanest
  separation but adds a whole mode/transition/permission surface for one flow.
- **Decision:** (b) as primary, with (a) kept as a thin explicit
  `POST /api/calibration/capture {nx, ny}` fallback for tests and scripting.
  A `CalibrationController` (`app/calibrate/session.py`) owns the session
  state machine, arms/disarms `ControlPipeline.arm_calibration`, and on the
  4th capture applies the fitted homography live (`mapper.config.calibration`
  + `control.calibration`) and persists it. Degenerate fits reset all four
  captures so recovery is guaranteed (a one-corner retry can stay degenerate).
- **Consequences:** `click.left` becomes capture-aware while armed, so the
  calibration session can't produce stray clicks. The transparent-HUD corner
  reticle and passive RANSAC refinement (`control.passive_calibrate`) remain
  deferred. HTTP endpoints: `GET /api/calibration` (state), `POST
  /api/calibration/{start,reset,clear,capture}`.

## Open Questions / Deferred Decisions

- **Q-01:** Whether the tablet runs its own gesture detector or is a "ready to receive" peer only. Deferred to Phase 4.
- **Q-02:** Which local LLM model family to default (Llama 3.x vs Qwen vs Phi). Deferred to Phase 3 with a benchmark task.
- **Q-03:** Plugin system shape (Python entry points vs subprocess/HTTP). Deferred to Phase 6.
