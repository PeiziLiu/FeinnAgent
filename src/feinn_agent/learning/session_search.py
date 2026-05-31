"""Cross-session search tool — DISCOVER, SCROLL, BROWSE.

Registered as a tool so the LLM can recall past conversations
without any additional model cost (pure SQLite FTS5).

Three calling shapes:
1. DISCOVER (query="..."): FTS5 full-text search, returns snippets
2. SCROLL (session_id + around_message_id): ±N window around a message
3. BROWSE (no args): List recent sessions
"""

from __future__ import annotations

import logging
from typing import Any

from ..types import ToolDef
from .session_store import SessionStore

logger = logging.getLogger(__name__)


def _format_search_results(results: list[Any], mode: str) -> str:
    """Format search results into a readable string.

    Args:
        results: List of search result objects.
        mode: The search mode (discover/scroll/browse).

    Returns:
        Formatted string representation.
    """
    if not results:
        return f"No results found ({mode} mode)."

    lines: list[str] = []

    if mode == "browse":
        lines.append("Recent sessions:")
        for s in results:
            title = s.title or "Untitled"
            lines.append(f"  [{s.id}] {title} — {s.created_at[:10]} ({s.token_count} tokens)")

    elif mode == "scroll":
        lines.append(f"Messages around anchor (session: {results[0].session_id}):")
        for m in results:
            tool_info = ""
            if m.tool_calls:
                tool_info = " [tool calls]"
            lines.append(f"  [{m.role}] {m.content[:200]}{tool_info}")

    else:  # discover
        lines.append(f"Search results ({len(results)} hits):")
        for r in results:
            lines.append(f"  [{r.session_id}] {r.snippet}")
            lines.append(f"       ({r.created_at[:10]})")

    return "\n".join(lines)


async def _session_search_tool(
    params: dict[str, Any],
    config: dict[str, Any],
) -> str:
    """Search past conversations for relevant context.

    Three modes:
    - DISCOVER: Pass ``query`` for full-text search across all sessions.
    - SCROLL: Pass ``session_id`` and ``around_message_id`` for context window.
    - BROWSE: Pass no args to list recent sessions.

    Args:
        params: Tool parameters
            - query: Search query (DISCOVER mode)
            - session_id: Session ID (SCROLL mode)
            - around_message_id: Anchor message ID (SCROLL mode)
        config: Agent configuration.

    Returns:
        Formatted search results.
    """
    query = params.get("query", "").strip()
    session_id = params.get("session_id", "").strip()
    around_message_id = params.get("around_message_id")

    store = SessionStore()

    # BROWSE mode: list recent sessions
    if not query and not session_id:
        sessions = store.browse(limit=20)
        return _format_search_results(sessions, "browse")

    # SCROLL mode: context window around a message
    if session_id and around_message_id is not None:
        messages = store.scroll(session_id, int(around_message_id))
        return _format_search_results(messages, "scroll")

    # DISCOVER mode: full-text search
    if query:
        results = store.search(query)
        return _format_search_results(results, "discover")

    return "No search parameters provided. Use 'query' for DISCOVER, 'session_id'+'around_message_id' for SCROLL, or no args for BROWSE."


SESSION_SEARCH_TOOL_DEF = ToolDef(
    name="SessionSearch",
    description=(
        "Search past conversations for relevant context. "
        "Three modes:\n"
        "- DISCOVER: pass 'query' for full-text search across all sessions\n"
        "- SCROLL: pass 'session_id' and 'around_message_id' for context window around a match\n"
        "- BROWSE: pass no args to list recent sessions\n\n"
        "Use this when the user references something from a past conversation "
        "or you suspect relevant cross-session context exists."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (DISCOVER mode) — leave empty for BROWSE",
                "default": "",
            },
            "session_id": {
                "type": "string",
                "description": "Session ID (SCROLL mode, requires around_message_id)",
                "default": "",
            },
            "around_message_id": {
                "type": "integer",
                "description": "Anchor message ID (SCROLL mode, requires session_id)",
            },
        },
    },
    handler=_session_search_tool,
    read_only=True,
    concurrent_safe=True,
)


def register_session_search_tool() -> None:
    """Register the SessionSearch tool in the global registry."""
    from ..tools.registry import register

    register(SESSION_SEARCH_TOOL_DEF)
    logger.debug("SessionSearch tool registered")
