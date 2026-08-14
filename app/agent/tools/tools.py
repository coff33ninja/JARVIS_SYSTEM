"""Built-in tools for the JARVIS agent.

Windows control tools (open_app, open_path, switch_window) are Win32-based
(ADR-006) and degrade to a descriptive error string when unavailable. The
``recall`` / ``remember`` tools connect the agent loop to the long-term
memory subsystem.
"""

from __future__ import annotations

import os
import subprocess
import urllib.parse
import webbrowser

from ..recall.retriever import Recaller
from ..recall.store import Fact, MemoryStore
from . import Tool, ToolRegistry


def _open_app(target: str) -> str:
    try:
        subprocess.Popen([target], cwd=os.path.expanduser("~"))
        return f"launched: {target}"
    except Exception as exc:
        return f"open_app failed: {exc}"


def _open_path(path: str) -> str:
    try:
        os.startfile(os.path.expanduser(path))  # type: ignore[attr-defined]
        return f"opened: {path}"
    except Exception as exc:
        return f"open_path failed: {exc}"


def _switch_window(title: str) -> str:
    try:
        import win32con
        import win32gui
    except ImportError:
        return "switch_window unavailable (win32 missing)"

    def _match(hwnd, found):
        if (
            win32gui.IsWindowVisible(hwnd)
            and title.lower() in win32gui.GetWindowText(hwnd).lower()
        ):
            found.append(hwnd)

    found: list[int] = []
    win32gui.EnumWindows(_match, found)
    if not found:
        return f"no visible window matches {title!r}"
    win32gui.ShowWindow(found[0], win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(found[0])
    return f"focused window matching {title!r}"


def _web_search(query: str) -> str:
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    webbrowser.open(url)
    return f"opened browser search for {query!r}"


def _recall(recaller: Recaller, query: str) -> str:
    hits = recaller.remember(query, limit=3)
    if not hits:
        return "nothing found in memory"
    return "\n".join(f"- [{h.source}] {h.content} (score {h.score:.2f})" for h in hits)


def _remember(store: MemoryStore, content: str, kind: str = "fact", tags=None) -> str:
    tag_tuple: tuple[str, ...] = ()
    if tags:
        if isinstance(tags, str):
            tag_tuple = tuple(t.strip() for t in tags.split(",") if t.strip())
        else:
            tag_tuple = tuple(t for t in tags if isinstance(t, str) and t.strip())
    store.add_fact(Fact(content, kind=kind, tags=tag_tuple))
    return f"stored fact: {content}"


def default_tools(store: MemoryStore, recaller: Recaller) -> ToolRegistry:
    """Registry with the standard Phase 3 tool set."""
    reg = ToolRegistry()
    reg.register(
        Tool(
            "open_app",
            "Launch an application on this computer by name or path.",
            {
                "type": "object",
                "properties": {"target": {"type": "string"}},
                "required": ["target"],
            },
            lambda target: _open_app(target),
        )
    )
    reg.register(
        Tool(
            "open_path",
            "Open a folder or file in the file explorer.",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            lambda path: _open_path(path),
        )
    )
    reg.register(
        Tool(
            "switch_window",
            "Bring the window whose title contains this text to the foreground.",
            {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
            lambda title: _switch_window(title),
        )
    )
    reg.register(
        Tool(
            "web_search",
            "Open the default web browser with a search for a query.",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            lambda query: _web_search(query),
        )
    )
    reg.register(
        Tool(
            "recall",
            "Search long-term memory for information relevant to a query. "
            "Use when the answer may require remembering past facts or preferences.",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            lambda query: _recall(recaller, query),
        )
    )
    reg.register(
        Tool(
            "remember",
            "Store a new long-term fact about the user or the environment.",
            {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "kind": {"type": "string", "description": "fact|preference|entity"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["content"],
            },
            lambda content, kind="fact", tags=None: _remember(
                store, content, kind, tags
            ),
        )
    )
    return reg
