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

## Open Questions / Deferred Decisions

- **Q-01:** Whether the tablet runs its own gesture detector or is a "ready to receive" peer only. Deferred to Phase 4.
- **Q-02:** Which local LLM model family to default (Llama 3.x vs Qwen vs Phi). Deferred to Phase 3 with a benchmark task.
- **Q-03:** Plugin system shape (Python entry points vs subprocess/HTTP). Deferred to Phase 6.
