"""Agent layer: LLM client, voice, tools, context, and recall memory."""

from .agent import Agent, AgentConfig
from .audio import MicConfig, MicInput
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
from .stt import STTConfig, STTEngine
from .tools import Tool, ToolRegistry
from .tools.tools import default_tools
from .tts import TTSConfig, TTSEngine
from .voice import VoiceConfig, VoiceLoop

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
    "MicConfig",
    "MicInput",
    "Recaller",
    "RecallConfig",
    "ScoredHit",
    "STTConfig",
    "STTEngine",
    "TTSConfig",
    "TTSEngine",
    "Tool",
    "ToolRegistry",
    "VoiceConfig",
    "VoiceLoop",
    "build_context",
    "default_tools",
    "focused_window_title",
]
