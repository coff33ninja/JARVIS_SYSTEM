"""Agent layer: LLM client, voice, tools, context, and recall memory."""

from .agent import Agent, AgentConfig
from .context import AgentContext, build_context, focused_window_title
from .llm import LLMClient, LLMConfig
from .recall import (
    Embedder,
    EmbedderConfig,
    Episode,
    Fact,
    MemoryStore,
    Recaller,
    RecallConfig,
    ScoredHit,
)
from .tools import Tool, ToolRegistry
from .tools.tools import default_tools

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentContext",
    "Embedder",
    "EmbedderConfig",
    "Episode",
    "Fact",
    "LLMClient",
    "LLMConfig",
    "MemoryStore",
    "Recaller",
    "RecallConfig",
    "ScoredHit",
    "Tool",
    "ToolRegistry",
    "build_context",
    "default_tools",
    "focused_window_title",
]
