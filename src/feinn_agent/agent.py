"""FeinnAgent core agent loop — async generator with concurrent tool execution.

The loop follows this structure:
1. Append user message → check compaction → stream from LLM
2. If tool calls: check permissions → execute (parallel when safe) → append results → loop
3. If no tool calls: yield final response → exit

All state mutations go through AgentState; the loop itself is stateless.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from .compaction import maybe_compact
from .config import load_config
from .permission import check_permission
from .providers import stream as llm_stream
from .tools.registry import dispatch_batch, tool_schemas
from .types import (
    AgentDone,
    AgentEvent,
    AgentState,
    AssistantTurn,
    PermissionCallback,
    Role,
    TextChunk,
    ThinkingChunk,
    ToolCall,
    TurnDone,
)

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRYABLE_ERRORS = ("overloaded", "rate_limit", "timeout", "context_length")


class FeinnAgent:
    """Enterprise-grade async AI agent.

    Usage:
        agent = FeinnAgent(config=my_config)
        async for event in agent.run("Fix the bug in login.py"):
            if isinstance(event, TextChunk):
                print(event.text, end="")
            elif isinstance(event, AgentDone):
                print(f"\\nDone. Tokens: {event.total_input_tokens}")
    """

    def __init__(
        self,
        *,
        config: dict[str, Any] | None = None,
        system_prompt: str = "",
        state: AgentState | None = None,
        permission_callback: PermissionCallback | None = None,
    ) -> None:
        self.config = config or load_config()
        self.system_prompt = system_prompt
        self.state = state or AgentState()
        self._permission_callback = permission_callback

    async def run(
        self,
        user_message: str,
        *,
        images: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run the agent loop for a single user message."""
        logger.info(f"Agent run started: message_length={len(user_message)}, images={len(images) if images else 0}")
        self.state.add_message(Role.USER, content=user_message, images=images or [])

        max_iterations = self.config.get("max_iterations", 50)
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"Agent iteration {iteration}/{max_iterations}")

            # Check compaction
            compacted = maybe_compact(self.state, self.config)
            if compacted:
                logger.info(f"Context compacted: new_size={len(self.state.messages)} messages")

            # Stream from LLM (with retry)
            assistant_text = ""
            assistant_reasoning = ""
            tool_calls: list[ToolCall] = []
            input_tokens = 0
            output_tokens = 0

            async for event in self._stream_with_retry():
                if isinstance(event, TextChunk):
                    assistant_text += event.text
                    yield event
                elif isinstance(event, ThinkingChunk):
                    assistant_reasoning += event.thinking
                    yield event
                elif isinstance(event, AssistantTurn):
                    assistant_text = event.text or assistant_text
                    assistant_reasoning = event.reasoning or assistant_reasoning
                    tool_calls = event.tool_calls
                    input_tokens = event.input_tokens
                    output_tokens = event.output_tokens

            # Record assistant turn
            self.state.add_message(
                Role.ASSISTANT,
                content=assistant_text,
                tool_calls=tool_calls,
                reasoning=assistant_reasoning,
            )
            self.state.total_input_tokens += input_tokens
            self.state.total_output_tokens += output_tokens
            self.state.turn_count += 1

            yield TurnDone(input_tokens=input_tokens, output_tokens=output_tokens)

            # No tool calls → done
            if not tool_calls:
                logger.info(f"Agent run complete: turns={self.state.turn_count}, input_tokens={self.state.total_input_tokens}, output_tokens={self.state.total_output_tokens}")
                yield AgentDone(
                    total_input_tokens=self.state.total_input_tokens,
                    total_output_tokens=self.state.total_output_tokens,
                    turn_count=self.state.turn_count,
                )
                return

            # Execute tool calls
            logger.info(f"Executing {len(tool_calls)} tool calls: {[tc.name for tc in tool_calls]}")
            tool_results = await self._execute_tools(tool_calls)
            logger.debug(f"Tool execution complete: {len(tool_results)} results")

            # Append tool results
            for tc, result in zip(tool_calls, tool_results):
                self.state.add_message(
                    Role.TOOL,
                    content=result,
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                )

        # Max iterations reached
        logger.warning(f"Max iterations ({max_iterations}) reached, stopping")
        yield TextChunk(text="\n[Max iterations reached. Stopping.]")
        yield AgentDone(
            total_input_tokens=self.state.total_input_tokens,
            total_output_tokens=self.state.total_output_tokens,
            turn_count=self.state.turn_count,
        )

    async def _stream_with_retry(self) -> AsyncIterator[TextChunk | ThinkingChunk | AssistantTurn]:
        """Stream from LLM with exponential backoff on retryable errors."""
        logger.debug(f"Starting LLM stream with retry: model={self.config.get('model')}, messages={len(self.state.messages)}")
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async for event in llm_stream(
                    model=self.config["model"],
                    system=self.system_prompt,
                    messages=self.state.messages,
                    tool_schemas=tool_schemas(),
                    config=self.config,
                ):
                    yield event
                logger.debug("LLM stream completed successfully")
                return  # success
            except Exception as e:
                err_str = str(e).lower()
                is_retryable = any(kw in err_str for kw in _RETRYABLE_ERRORS)

                if "context_length" in err_str:
                    logger.warning(f"Context length exceeded, forcing compaction (attempt {attempt + 1})")
                    maybe_compact(self.state, self.config, force=True)
                    if attempt < _MAX_RETRIES:
                        continue

                if not is_retryable or attempt >= _MAX_RETRIES:
                    logger.error(f"Non-retryable error or max retries reached: {e}")
                    yield TextChunk(text=f"[Error: {e}]")
                    return

                wait = 2 ** (attempt + 1)
                logger.warning(
                    "Retryable error (attempt %d/%d), waiting %ds: %s",
                    attempt + 1,
                    _MAX_RETRIES,
                    wait,
                    e,
                )
                await asyncio.sleep(wait)

    async def _execute_tools(self, tool_calls: list[ToolCall]) -> list[str]:
        """Execute tool calls with permission checks and batch optimization."""
        results: list[str] = []

        # Check permissions for each tool call
        permitted_batch: list[tuple[str, dict[str, Any]]] = []
        permission_map: dict[int, bool] = {}  # index → permitted?

        logger.debug(f"Checking permissions for {len(tool_calls)} tool calls")
        for i, tc in enumerate(tool_calls):
            allowed = await check_permission(
                tc.name, tc.input, self.config, self._permission_callback
            )
            permission_map[i] = allowed
            if allowed:
                permitted_batch.append((tc.name, tc.input))
                logger.debug(f"Tool '{tc.name}' permitted")
            else:
                logger.warning(f"Tool '{tc.name}' permission denied")

        # Execute all permitted tools in batch
        logger.info(f"Executing {len(permitted_batch)}/{len(tool_calls)} permitted tools")
        batch_results = (
            await dispatch_batch(permitted_batch, self.config) if permitted_batch else []
        )
        logger.debug(f"Batch execution complete: {len(batch_results)} results")

        # Assemble results in order
        batch_idx = 0
        for i, tc in enumerate(tool_calls):
            if not permission_map[i]:
                results.append("Error: Permission denied for this operation")
            else:
                if batch_idx < len(batch_results):
                    results.append(batch_results[batch_idx])
                    batch_idx += 1
                else:
                    results.append("Error: no result from tool execution")

        return results
