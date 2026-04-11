"""FeinnAgent — Enterprise-grade async AI agent framework.

Quick start:
    from feinn_agent import FeinnAgent

    agent = FeinnAgent()
    async for event in agent.run("Fix the bug in login.py"):
        if isinstance(event, TextChunk):
            print(event.text, end="")
        elif isinstance(event, AgentDone):
            print(f"\\nDone. {event.total_input_tokens} tokens used.")
"""

from .agent import FeinnAgent
from .types import (
    AgentDone,
    AgentEvent,
    AgentState,
    PermissionMode,
    TextChunk,
    ThinkingChunk,
    ToolCall,
    ToolDef,
    ToolEnd,
    ToolStart,
    TurnDone,
)

__all__ = [
    "FeinnAgent",
    "AgentDone",
    "AgentEvent",
    "AgentState",
    "PermissionMode",
    "TextChunk",
    "ThinkingChunk",
    "ToolCall",
    "ToolEnd",
    "ToolStart",
    "ToolDef",
    "TurnDone",
]

__version__ = "0.1.0"
