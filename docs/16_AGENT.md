# 16 — Agent (Phase 3)

The JARVIS brain. A thin, hand-rolled tool-using loop over an OpenAI-compatible LLM (ADR-003, ADR-010) that uses the recall memory subsystem (see `15_RECALL_MEMORY.md`) for long-term memory.

## Files

```
app/agent/
├── llm.py        # LLMClient / LLMConfig — OpenAI-compatible chat + tool calls
├── tools/        # Tool / ToolRegistry + built-in tools
├── context.py    # build_context(), focused_window_title()
├── agent.py      # Agent loop
└── recall/       # memory subsystem (see 15_RECALL_MEMORY.md)
tests/test_llm.py, tests/test_tools.py, tests/test_agent.py
```

## Agent loop

Each `agent.handle_turn(text)`:

1. Pulls recent episodes for the session (`recaller.recall_history`).
2. Recalls memories relevant to the request (`recaller.remember`).
3. Sends the LLM: a system prompt (persona + focused window + known memories), conversation history, then the user turn.
4. Executes any tool calls, feeding results back, bounded by `max_tool_iterations` (default 5).
5. Records the user turn and final answer as episodes.

```python
from app.agent import Agent, LLMClient, LLMConfig, MemoryStore, Recaller

store = MemoryStore("jarvis_memory.db")
llm = LLMClient(LLMConfig(model="llama3.2"))
agent = Agent(llm, store, recaller=Recaller(store))
agent.handle_turn("open the project folder")
```

## Tools

`ToolRegistry` exposes plain Python functions with JSON-schema definitions. `execute()` always returns a string so results are safe to feed back to the model.

| Tool | Action |
|---|---|
| `open_app` | Launch an application by name or path |
| `open_path` | Open a folder/file in Explorer |
| `switch_window` | Bring a window (title match) to the foreground |
| `web_search` | Open the default browser with a search |
| `recall` | Query long-term memory (hybrid keyword/semantic) |
| `remember` | Store a long-term fact / preference / entity |

Windows tools are Win32-based and return a descriptive error string when unavailable (ADR-006).

## LLM configuration

`LLMConfig` (env overrides: `JARVIS_LLM_BASE_URL`, `JARVIS_LLM_MODEL`):

| Field | Default | Meaning |
|---|---|---|
| `base_url` | `http://localhost:11434/v1` | OpenAI-compatible endpoint (ADR-003) |
| `model` | `llama3.2` | Chat model (`ollama pull llama3.2`) |
| `temperature` | `0.2` | Sampling temperature |
| `timeout_s` | `30.0` | Request timeout |

## Graceful degradation

- **LLM down** → `available` is `False`; the agent raises rather than faking a reply.
- **Model has no tool support** (e.g. `smallthinker:latest` returns HTTP 400 for tool requests) → the agent logs a warning, retries the turn **without tools**, and keeps working tool-less for the rest of the session.
- **Unknown / failing tool** → the tool returns an error string to the model; the loop continues instead of crashing.

## Tests

`tests/test_llm.py` (response normalisation, tool-call parsing, availability), `tests/test_tools.py` (registry, memory tools, browser/explorer/launch stubbed), `tests/test_agent.py` (episode recording, memory injection, tool flow, iteration bounds, tool-refusal degradation), `tests/test_stt.py` (segment joining, lazy model load, graceful failure), `tests/test_tts.py` (SAPI speak/voice selection, Piper subprocess), `tests/test_audio.py` (silence detection, max caps), `tests/test_voice.py` (wake-word gating, stripping, push-to-talk, transcript). All offline: fake clients, stubbed subprocess/browser, tmp SQLite.

## Voice pipeline (Phase 3, built)

- `app/agent/stt.py` — `STTEngine` wrapping Faster-Whisper. Lazy model load (auto-downloads on first use, sizes in `08_ASSETS.md`); `transcribe(audio)` and `transcribe_file(path)`; graceful `available` probe.
- `app/agent/tts.py` — `TTSEngine`. **SAPI default** (Windows `SpVoice`, zero downloads; voice picked by substring, optional pitch via SAPI XML) and optional **Piper** backend (`en_US-amy-medium` via `JARVIS_PIPER_BINARY`/`JARVIS_PIPER_MODEL`). `say()` never raises.
- `app/agent/audio.py` — `MicInput`: block-wise 16 kHz float32 capture with RMS end-of-speech detection (`record_until_silence`), hard max caps.
- `app/agent/voice.py` — `VoiceLoop` composition: one utterance → transcribe once → keyword mode gates on the wake word ("jarvis", stripped from the command) → `Agent.handle_turn` → `TTSEngine.say`. `run()` loops in its own thread so the gesture loop is never blocked. Transcript available via `Agent.transcript()`.
- Config via env: `JARVIS_STT_MODEL`, `JARVIS_STT_LANGUAGE`, `JARVIS_TTS_BACKEND`, `JARVIS_TTS_VOICE`, `JARVIS_PIPER_BINARY`, `JARVIS_PIPER_MODEL`, `JARVIS_WAKE_WORD`, `JARVIS_WAKE_MODE`, `JARVIS_MIC_RATE`.

### HUD transcript panel

The data layer is done (`Agent.transcript()` returns recent user/assistant episodes; `VoiceLoop.run_once` returns them with each turn). The on-screen chat bubbles/panel render with the HUD overlay layer (Phase 1/2).

Exit criteria once wired: "Jarvis, open the project folder" works with voice, round-trip < 2 s. This needs a **tool-capable LLM** (e.g. `ollama pull llama3.2`, `smallthinker` has no tools), the STT model downloaded, and a live mic.
