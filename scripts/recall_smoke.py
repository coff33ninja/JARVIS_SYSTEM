"""Smoke test for the recall memory subsystem.

Usage:
    uv run python scripts/recall_smoke.py            # in-memory, tries Ollama
    uv run python scripts/recall_smoke.py --db data.db --no-embed

Seeds demo facts and a short conversation, attempts a semantic index via
Ollama (skipped gracefully if unreachable), then runs sample recall
queries. Exits non-zero if any keyword query returns no hits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.context import build_context
from app.agent.recall import (
    Embedder,
    Episode,
    Fact,
    MemoryStore,
    RecallConfig,
    Recaller,
)

DEMO_FACTS = [
    Fact("User prefers the terminal over GUI file managers", tags=("preference",)),
    Fact("Default file transfer method is LocalSend over the LAN", tags=("file",)),
    Fact(
        "Pinch clicks, a fist drags, and a throw gesture sends files", tags=("gesture",)
    ),
    Fact("Ollama runs locally at localhost:11434", tags=("llm",)),
]

DEMO_EPISODES = [
    Episode("user", "how do I open a file?", session_id="smoke"),
    Episode("assistant", "use the terminal or the file manager", session_id="smoke"),
    Episode("user", "send this to my tablet", session_id="smoke"),
]

QUERIES = ["terminal", "file transfer", "throw gesture"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", default=":memory:", help="SQLite path (default: in-memory)"
    )
    parser.add_argument(
        "--no-embed", action="store_true", help="skip the Ollama index attempt"
    )
    args = parser.parse_args()

    with MemoryStore(args.db) as store:
        for fact in DEMO_FACTS:
            store.add_fact(fact)
        for episode in DEMO_EPISODES:
            store.add_episode(episode)

        embedder = None if args.no_embed else Embedder(RecallConfig().embedder)
        recaller = Recaller(store, embedder=embedder)

        if not args.no_embed:
            try:
                indexed = recaller.index()
                print(
                    f"[semantic] indexed {indexed} row(s)"
                    if indexed
                    else "[semantic] nothing indexed (Ollama offline?)"
                )
            except Exception as exc:
                print(f"[semantic] skipped: {exc}")

        ok = True
        for query in QUERIES:
            hits = recaller.remember(query)
            print(f"[recall] {query!r} -> {len(hits)} hit(s)")
            for hit in hits[:3]:
                print(
                    f"    {hit.score:.2f}  {hit.source:8s} [{hit.table}] {hit.content[:70]}"
                )
            if not hits:
                ok = False

        context = build_context(store, recaller, QUERIES[0], session_id="smoke")
        print(
            "[context] assembled prompt block of",
            len(context.to_prompt().splitlines()),
            "lines",
        )

        print("[stats]", store.stats())

    if not ok:
        print("SMOKE FAILED: a query returned no hits")
        return 1
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
