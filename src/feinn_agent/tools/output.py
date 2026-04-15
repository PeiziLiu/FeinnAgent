"""Output post-processing — truncation strategies and diff generation.

Centralizes output handling for tool results, replacing inline truncation
in the registry dispatcher. Applies Harness Engineering "Sensors" pattern:
provide structured feedback (diffs, truncation markers) to guide agent behavior.
"""

from __future__ import annotations

import difflib


def truncate_output(text: str, max_chars: int = 32_000) -> str:
    """Truncate long output, keeping first 50% and last 25%.

    The asymmetric split preserves more tail content because error messages
    and final results typically appear at the end of command output.

    Reference: CheetahClaws tool_registry.py:83-91
    """
    if len(text) <= max_chars:
        return text

    first_half = max_chars // 2
    last_quarter = max_chars // 4
    truncated = len(text) - first_half - last_quarter

    return (
        text[:first_half]
        + f"\n[... {truncated} chars truncated ...]\n"
        + text[-last_quarter:]
    )


def generate_unified_diff(
    old: str, new: str, filename: str, context_lines: int = 3
) -> str:
    """Generate a unified diff between two strings.

    Reference: CheetahClaws tools.py:348-353
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=context_lines,
    )
    return "".join(diff)


def truncate_diff(diff_text: str, max_lines: int = 80) -> str:
    """Truncate a diff to a maximum number of lines.

    Reference: CheetahClaws tools.py:355-361
    """
    lines = diff_text.splitlines()
    if len(lines) <= max_lines:
        return diff_text
    shown = lines[:max_lines]
    remaining = len(lines) - max_lines
    return "\n".join(shown) + f"\n\n[... {remaining} more lines ...]"
