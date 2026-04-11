"""FeinnAgent — Enterprise-grade async AI agent framework.

Core type definitions used across all modules.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# ── Unique identifiers ──────────────────────────────────────────────


def new_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}_{uid}" if prefix else uid


# ── Message types ───────────────────────────────────────────────────


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """A single tool call requested by the assistant."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class Message:
    """Provider-agnostic message format."""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    tool_name: str = ""
    images: list[dict[str, str]] = field(default_factory=list)
    reasoning: str = ""  # thinking/reasoning content

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role.value}
        if self.content:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "input": tc.input} for tc in self.tool_calls
            ]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_name:
            d["name"] = self.tool_name
        if self.reasoning:
            d["reasoning"] = self.reasoning
        if self.images:
            d["images"] = self.images
        return d


# ── Agent stream events ─────────────────────────────────────────────


@dataclass
class TextChunk:
    """Streaming text fragment from LLM."""

    text: str


@dataclass
class ThinkingChunk:
    """Reasoning block from extended thinking."""

    thinking: str


@dataclass
class ToolStart:
    """Tool execution is about to begin."""

    name: str
    inputs: dict[str, Any]
    call_id: str = ""


@dataclass
class ToolEnd:
    """Tool execution has completed."""

    name: str
    result: str
    call_id: str = ""
    permitted: bool = True


@dataclass
class PermissionRequest:
    """Ask the consumer for tool permission."""

    name: str
    inputs: dict[str, Any]
    call_id: str = ""
    granted: bool = False


@dataclass
class AssistantTurn:
    """Complete assistant response from LLM, including tool calls and token usage."""

    text: str = ""
    reasoning: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class TurnDone:
    """A single LLM turn (potentially with tool calls) has completed."""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class AgentDone:
    """Agent loop has finished — final response delivered."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    turn_count: int = 0


# Union type for all stream events
AgentEvent = (
    TextChunk
    | ThinkingChunk
    | ToolStart
    | ToolEnd
    | PermissionRequest
    | TurnDone
    | AgentDone
    | AssistantTurn
)

# Async generator type for the agent loop
AgentStream = AsyncIterator[AgentEvent]

# Callback type for permission decisions
PermissionCallback = Callable[[PermissionRequest], Coroutine[None, None, bool]]


# ── Agent state ─────────────────────────────────────────────────────


@dataclass
class AgentState:
    """Mutable session state carried across turns."""

    messages: list[Message] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    turn_count: int = 0
    session_id: str = field(default_factory=lambda: new_id("sess"))

    def add_message(self, role: Role, content: str = "", **kwargs: Any) -> Message:
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        return msg


# ── Tool definition ─────────────────────────────────────────────────


@dataclass
class ToolDef:
    """Definition of a tool that can be registered and dispatched."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Coroutine[None, None, str]]
    read_only: bool = False
    concurrent_safe: bool = False
    destructive: bool = False
    requires_env: list[str] = field(default_factory=list)
    max_result_chars: int = 32_000


# ── Permission mode ─────────────────────────────────────────────────


class PermissionMode(StrEnum):
    AUTO = "auto"  # allow reads, ask for writes
    ACCEPT_ALL = "accept-all"  # allow everything
    MANUAL = "manual"  # ask for everything
    PLAN = "plan"  # read-only + plan file writes only
