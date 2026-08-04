# 07 — Environment Setup

Windows-first (ADR-006). Everything uses **uv** (project manager) + **pyproject.toml** (single source of truth for deps — no requirements.txt). Cache and managed Pythons live off the system drive to bypass C: restrictions.

## Prerequisites

- Windows 10/11 64-bit
- Webcam (built-in or USB)
- uv installed — see [Bootstrap uv](#bootstrap-uv)
- Optional: NVIDIA GPU for faster local LLM / Whisper
- Optional: Ollama for the LLM layer (Phase 3)

## Bootstrap uv

Quick install (from skill bundle or astral):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# add to PATH for this session:
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
```

Or use the bundled project script (detects / installs uv, optionally a managed Python):

```powershell
.\scripts\ensure-uv.ps1 -InstallMissing -ManagedPython -PythonVersion 3.11
```

## Cache & Python bypass (keeps C: clean)

Already configured in `pyproject.toml [tool.uv]`:
- `cache-dir = "D:/uv-cache"` — uv's download/build cache never touches C:
- `managed = true` + `python-preference = "managed"` — uv downloads and uses its own CPython (no dependency on system Python, which may be restricted or too old)

Optional: relocate uv-managed Python installs too (env-var only, persistent per user):

```powershell
[Environment]::SetEnvironmentVariable("UV_PYTHON_INSTALL_DIR", "D:/uv-python", "User")
```

## 1. Sync the project environment

```powershell
cd D:\SCRIPTS\JARVIS_SYSTEM
uv sync
```

- Creates `.venv\` in the project root (managed Python 3.11.x auto-downloaded if missing)
- Installs all `[project] dependencies` + the `dev` group (pytest)
- Generates/uses `uv.lock` (commit it — it pins the whole tree)

## 2. Day-to-day commands

| Task | Command |
|---|---|
| Run any command in the env | `uv run python scripts/smoke_test_hands.py` |
| Add a dependency | `uv add <pkg>` |
| Add a dev dependency | `uv add --dev <pkg>` |
| Remove a dependency | `uv remove <pkg>` |
| Sync after lock changes | `uv sync` |
| Update lockfile without sync | `uv lock` |
| Upgrade all | `uv sync --upgrade` |
| Clear cache (off C:, on D:) | `uv cache clean` |

## 3. Verify MediaPipe + webcam

```powershell
uv run python -c "import cv2, mediapipe as mp; print('mp', mp.__version__); print('cv2', cv2.__version__)"
```

Then run the hand-landmark smoke test (webcam window with skeleton overlay):
`uv run python scripts/smoke_test_hands.py` (script added in Phase 1).

## 4. Optional components

| Layer | Install |
|---|---|
| Local LLM | `winget install Ollama.Ollama` or LM Studio; `ollama pull <model>` |
| Voice STT | Faster-Whisper pulls models automatically on first use (see `08_ASSETS.md`) |
| Voice TTS | Piper models downloaded to `models/piper/` |
| Transfer | Install LocalSend on PC + tablet: https://localsend.org |

## 5. Common issues

| Symptom | Fix |
|---|---|
| `mediapipe` fails to resolve | Requires-python is `>=3.11,<3.13`; on RPi use aarch64 wheel or official Docker build |
| uv wants to download Python (slow first time) | Normal — it lands in `D:/uv-cache` / `D:/uv-python` per config |
| `UV_PYTHON_INSTALL_DIR` not honored | It's an env var, not a pyproject key — set it per the step above, restart shell |
| Webcam not found | Change `CAMERA_INDEX` in config; some laptops need index 1 |
| Wrong monitor cursor mapping | Re-run calibration; verify per-monitor DPI scaling (`13_MULTIMONITOR.md`) |
| PermissionError on input injection | Run terminal as admin for Win32 hooks, or use pynput fallback |
