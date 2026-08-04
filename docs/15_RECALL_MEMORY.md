# 15 — Recall Memory

Jarvis's long-term memory subsystem. Gives the Phase 3 agent durable memory: facts it remembers about you, plus conversation history that survives restarts. Lives in `app/agent/recall/` (see ADR-009).

## Data model

| Table | Holds | Notes |
|---|---|---|
| `facts` | Durable memories: facts, preferences, entities | `kind`, comma-separated `tags`, `importance` (0–1), `recall_count` / `last_recalled_at` for frequency feedback |
| `episodes` | Conversation turns (`system`/`user`/`assistant`/`tool`) | Grouped by `session_id` for cross-session continuity |
| `mem_fts` | FTS5 keyword index over facts + episodes | Searched with BM25; transparent `LIKE` fallback if the platform lacks FTS5 |
| `embeddings` | Dense vectors as float32 blobs | Keyed by `(table, row_id, model)`; used by semantic recall |

## Files

```
app/agent/recall/
├── __init__.py    # public API
├── config.py      # RecallConfig / EmbedderConfig (+ JARVIS_* env overrides)
├── store.py       # MemoryStore: SQLite + FTS5 persistence
├── embedder.py    # Embedder: optional Ollama embeddings client
└── retriever.py   # Recaller: hybrid keyword + semantic retrieval
app/agent/context.py    # build_context(): history + memories -> prompt
scripts/recall_smoke.py # end-to-end smoke test
tests/test_recall_*.py, tests/test_context.py
```

## Quick start

```powershell
uv run python scripts/recall_smoke.py            # in-memory, tries Ollama
uv run python scripts/recall_smoke.py --db data.db --no-embed
```

## API

```python
from app.agent.recall import MemoryStore, Fact, Episode, Recaller, Embedder

with MemoryStore("jarvis_memory.db") as store:
    store.add_fact(Fact("User prefers the terminal", tags=("preference",)))
    store.add_episode(Episode("user", "open the project folder", session_id="s1"))

    recaller = Recaller(store, embedder=Embedder())
    hits = recaller.remember("what does the user prefer?")
    history = recaller.recall_history(session_id="s1")
    recaller.index()   # backfill embeddings for semantic recall (needs Ollama)
```

Compose both into LLM context:

```python
from app.agent.context import build_context
ctx = build_context(store, recaller, query, session_id=session_id)
prompt = ctx.to_prompt()
```

## Recall flow

1. **Keyword (always on):** `remember()` runs a BM25 query over `mem_fts`. This works with zero configuration.
2. **Semantic (optional):** if an embedder is configured and rows are indexed, the query is embedded and compared by cosine similarity against stored vectors.
3. **Fusion:** both lists are min-max normalised, weighted (`keyword_weight` / `semantic_weight`, default 0.4 / 0.6), and merged per row.
4. **Degradation:** if the embedder is unreachable, disabled, or `index()` was never run, recall silently returns keyword-only results.

## Configuration

`RecallConfig` / `EmbedderConfig` in `recall/config.py`, or via env vars:

| Env var | Default | Meaning |
|---|---|---|
| `JARVIS_MEMORY_DB` | `jarvis_memory.db` | SQLite path |
| `JARVIS_RECALL_EMBED` | `1` | `0` disables semantic recall |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible embeddings endpoint (ADR-003) |
| `JARVIS_EMBED_MODEL` | `nomic-embed-text` | Embedding model (`ollama pull nomic-embed-text`) |

## Operational notes

- **Semantic recall needs a one-time backfill:** `recaller.index()` embeds every row that lacks a vector. Re-run it whenever new rows are added; it is idempotent and batches (default 32).
- **Editing a fact** (`update_fact`) drops its embedding so the next `index()` re-embeds the new content.
- **Scale:** semantic recall scans stored vectors linearly. Fine at MVP scale; swap in a real vector index in Phase 6 if the store grows (ADR-009).
- **Privacy:** everything stays in the local SQLite file; embeddings leave the machine only if you point `OLLAMA_BASE_URL` at a remote host (see ADR-005).

## Tests

- `tests/test_recall_store.py` — persistence, FTS + LIKE fallback, updates/deletes, embeddings round-trip.
- `tests/test_recall_retriever.py` — keyword/semantic/hybrid ranking, graceful degradation, index backfill.
- `tests/test_embedder.py` — client build/availability, single + batch embed, endpoint-down handling (no network).
- `tests/test_context.py` — `build_context` composition and prompt formatting.

All tests use in-memory/tmp SQLite files and fake embedders — no webcam, network, or Ollama required.
