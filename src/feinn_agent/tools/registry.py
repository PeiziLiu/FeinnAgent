"""FeinnAgent tool registry — central registration, schema export, and dispatch.

Tools self-register at import time. The registry provides:
- Schema collection for LLM API calls
- Async dispatch with output truncation
- Concurrent-safe tool parallelization hints
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..types import ToolDef

logger = logging.getLogger(__name__)

# ── Global registry ─────────────────────────────────────────────────

_tools: dict[str, ToolDef] = {}


def register(tool_def: ToolDef) -> None:
    """Register a tool, overwriting any existing with the same name."""
    _tools[tool_def.name] = tool_def
    logger.debug("Registered tool: %s", tool_def.name)


def deregister(name: str) -> None:
    """Remove a tool from the registry."""
    _tools.pop(name, None)


def get(name: str) -> ToolDef | None:
    """Look up a tool by name."""
    return _tools.get(name)


def all_tools() -> list[ToolDef]:
    """Return all registered tools."""
    return list(_tools.values())


def tool_schemas() -> list[dict[str, Any]]:
    """Return JSON schemas for all registered tools (for LLM API calls).

    Converts FeinnAgent schemas to the format expected by
    Anthropic / OpenAI tool calling APIs.
    """
    schemas: list[dict[str, Any]] = []
    for td in _tools.values():
        schemas.append(
            {
                "name": td.name,
                "description": td.description,
                "input_schema": td.input_schema,
            }
        )
    return schemas


async def dispatch(
    name: str,
    params: dict[str, Any],
    config: dict[str, Any],
    *,
    max_output: int | None = None,
) -> str:
    """Execute a tool by name, truncating output if needed.

    Returns the tool result as a string. Errors are caught and
    returned as error messages rather than raised.
    """
    td = _tools.get(name)
    if td is None:
        return f"Error: unknown tool '{name}'"

    limit = max_output or td.max_result_chars
    try:
        result = await td.handler(params, config)
        if len(result) > limit:
            half = limit // 2
            result = (
                result[:half]
                + f"\n... [{len(result) - limit} chars truncated] ...\n"
                + result[-half:]
            )
        return result
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return f"Error in {name}: {type(e).__name__}: {e}"


async def dispatch_batch(
    calls: list[tuple[str, dict[str, Any]]],
    config: dict[str, Any],
) -> list[str]:
    """Execute a batch of tool calls, running concurrent-safe ones in parallel.

    Returns results in the same order as the input calls.
    """
    if not calls:
        return []

    # Group: concurrent-safe vs sequential
    safe_indices: list[int] = []
    seq_indices: list[int] = []

    for i, (name, _) in enumerate(calls):
        td = _tools.get(name)
        if td and td.concurrent_safe and td.read_only:
            safe_indices.append(i)
        else:
            seq_indices.append(i)

    results: dict[int, str] = {}

    # Execute safe tools concurrently
    if safe_indices:
        tasks = []
        for i in safe_indices:
            name, params = calls[i]
            tasks.append(dispatch(name, params, config))
        safe_results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, r in zip(safe_indices, safe_results):
            results[i] = r if isinstance(r, str) else f"Error: {r}"

    # Execute sequential tools one by one
    for i in seq_indices:
        name, params = calls[i]
        results[i] = await dispatch(name, params, config)

    return [results[i] for i in range(len(calls))]


def clear() -> None:
    """Remove all registered tools (useful for testing)."""
    _tools.clear()
