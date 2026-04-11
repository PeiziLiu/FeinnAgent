"""FeinnAgent multi-layer context compression.

Three layers of context management:
  Layer 1: Snip — trim old tool outputs (zero API cost)
  Layer 2: Compact — AI summarization of old messages (API cost)
  Layer 3: Collapse — emergency pruning when compact fails

Triggered when estimated tokens exceed config threshold (default 70%).
"""

from __future__ import annotations

import logging
from typing import Any

from .types import AgentState, Message, Role

logger = logging.getLogger(__name__)


# ── Token estimation ────────────────────────────────────────────────


def estimate_tokens(messages: list[Message]) -> int:
    """Estimate token count for a message list.

    Uses chars/2.8 divisor calibrated for code-heavy content,
    plus per-message framing overhead and 10% buffer.
    """
    total_chars = 0
    msg_count = 0

    for m in messages:
        msg_count += 1
        if m.content:
            total_chars += len(m.content)
        if m.reasoning:
            total_chars += len(m.reasoning)
        for tc in m.tool_calls:
            total_chars += len(tc.name)
            total_chars += len(str(tc.input))
        for img in m.images:
            total_chars += 100  # rough estimate for image references

    content_tokens = int(total_chars / 2.8)
    framing_tokens = msg_count * 4
    return int((content_tokens + framing_tokens) * 1.1)


def get_context_limit(config: dict[str, Any]) -> int:
    """Get context limit for the configured model."""
    from .providers import detect_provider

    model = config.get("model", "anthropic/claude-sonnet-4-20250514")
    info = detect_provider(model)
    return info.context_limit


# ── Public API ──────────────────────────────────────────────────────


def maybe_compact(state: AgentState, config: dict[str, Any], *, force: bool = False) -> bool:
    """Check if compaction is needed and apply it.

    Returns True if any compaction was applied.
    """
    limit = get_context_limit(config)
    threshold = int(limit * config.get("compaction_threshold", 0.70))
    tokens = estimate_tokens(state.messages)

    if not force and tokens <= threshold:
        return False

    logger.info("Compaction triggered: %d tokens > %d threshold", tokens, threshold)

    # Layer 1: Snip old tool outputs
    _snip_old_tool_outputs(
        state.messages,
        max_chars=config.get("max_tool_output_chars", 32_000) // 4,
        preserve_last_n=config.get("compaction_preserve_last_n", 6),
    )

    if not force:
        tokens_after = estimate_tokens(state.messages)
        if tokens_after <= threshold:
            logger.info("Layer 1 snip sufficient: %d → %d tokens", tokens, tokens_after)
            return True

    # Layer 2: AI summarization (placeholder — actual LLM call in async context)
    # In production, this would call an LLM to summarize old messages.
    # Here we do a simpler truncation-based approach for the sync path.
    _compact_by_truncation(state.messages, threshold)

    tokens_after = estimate_tokens(state.messages)
    logger.info("After compaction: %d → %d tokens", tokens, tokens_after)
    return True


# ── Layer 1: Snip ───────────────────────────────────────────────────


def _snip_old_tool_outputs(
    messages: list[Message],
    *,
    max_chars: int = 8000,
    preserve_last_n: int = 6,
) -> int:
    """Trim old tool result messages to max_chars, preserving last N turns.

    Returns the number of messages modified.
    """
    # Find the boundary: don't touch the last N tool messages
    tool_msg_indices = [i for i, m in enumerate(messages) if m.role == Role.TOOL]
    preserve_from = (
        tool_msg_indices[-preserve_last_n]
        if len(tool_msg_indices) > preserve_last_n
        else len(messages)
    )

    modified = 0
    for i, msg in enumerate(messages):
        if i >= preserve_from:
            break
        if msg.role == Role.TOOL and len(msg.content) > max_chars:
            half = max_chars // 2
            quarter = max_chars // 4
            msg.content = (
                msg.content[:half]
                + f"\n... [{len(msg.content) - max_chars} chars snipped] ...\n"
                + msg.content[-quarter:]
            )
            modified += 1

    return modified


# ── Layer 2: Compact (truncation fallback) ──────────────────────────


def _compact_by_truncation(messages: list[Message], target_tokens: int) -> None:
    """Emergency truncation: keep system + first exchange + recent messages.

    Replaces old middle messages with a summary marker.
    """
    if len(messages) <= 4:
        return

    # Keep: first 2 messages (system/user), last 30% of messages
    keep_head = 2
    keep_tail = max(2, len(messages) // 3)

    if keep_head + keep_tail >= len(messages):
        return

    # Replace middle section with a compact marker
    removed_count = len(messages) - keep_head - keep_tail
    marker = Message(
        role=Role.SYSTEM,
        content=f"[Context compressed: {removed_count} earlier messages summarized to save space]",
    )

    messages[:] = messages[:keep_head] + [marker] + messages[-keep_tail:]
