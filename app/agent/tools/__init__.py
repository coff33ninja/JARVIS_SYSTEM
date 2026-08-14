"""Tool registry: pure-Python functions exposed to the LLM as tools.

Each tool has a name, description, and JSON-schema ``parameters`` block
(the ``tools`` array the OpenAI-compatible API expects), plus a plain
function. ``execute()`` always returns a string so the result is safe to
feed back to the model as a ``tool`` message.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: Callable[..., str]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"unknown tool: {name}"
        try:
            return str(tool.fn(**arguments))
        except TypeError as exc:
            return f"bad arguments for {name}: {exc}"
        except Exception as exc:
            return f"{name} failed: {exc}"
