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

`tests/test_llm.py` (response normalisation, tool-call parsing, availability), `tests/test_tools.py` (registry, memory tools, browser/explorer/launch stubbed), `tests/test_agent.py` (episode recording, memory injection, tool flow, iteration bounds, tool-refusal degradation). All offline: fake clients, stubbed subprocess/browser, tmp SQLite.

## Remaining Phase 3 items (voice iteration)

- `app/agent/stt.py` — Faster-Whisper input (models per `08_ASSETS.md`)
- `app/agent/tts.py` — Piper / Coqui output
- HUD chat bubbles / transcript panel (HUD layer)

Exit criteria once wired: "Jarvis, open the project folder" works with voice, round-trip < 2 s.
