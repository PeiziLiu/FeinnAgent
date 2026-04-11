"""FeinnAgent permission and safety system."""

from __future__ import annotations

import logging
import re
from typing import Any

from ..types import PermissionCallback, PermissionMode, PermissionRequest

logger = logging.getLogger(__name__)

# ── Safe command patterns (for Bash tool auto-approval) ─────────────

_SAFE_READ_COMMANDS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^ls\b",
        r"^cat\b",
        r"^head\b",
        r"^tail\b",
        r"^find\b",
        r"^grep\b",
        r"^rg\b",
        r"^wc\b",
        r"^file\b",
        r"^git status\b",
        r"^git log\b",
        r"^git diff\b",
        r"^git branch\b",
        r"^git show\b",
        r"^pwd$",
        r"^whoami$",
        r"^echo\b",
        r"^which\b",
        r"^env\b",
        r"^python --version",
        r"^node --version",
        r"^npm list\b",
        r"^pip list\b",
    ]
]

_UNSAFE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\brm\s+-rf\b",
        r"\brm\s+-.*/\b",
        r"\bgit\s+push\s+--force\b",
        r"\bgit\s+reset\s+--hard\b",
        r"\bdrop\s+table\b",
        r"\btruncate\s+table\b",
        r">\s*/dev/sd",
        r"\bdd\s+if=",
        r"\bformat\s+[a-z]:",
        r"\bsudo\b",
        r"\bchmod\s+777\b",
        r"\bcurl\b.*\|\s*(ba)?sh",
        r"\bwget\b.*\|\s*(ba)?sh",
    ]
]


def is_safe_bash_command(command: str) -> bool:
    """Check if a bash command is safe for auto-approval."""
    cmd = command.strip()

    for pattern in _UNSAFE_PATTERNS:
        if pattern.search(cmd):
            return False

    for pattern in _SAFE_READ_COMMANDS:
        if pattern.match(cmd):
            return True

    return False


# ── Permission decision ─────────────────────────────────────────────


async def check_permission(
    tool_name: str,
    tool_input: dict[str, Any],
    config: dict[str, Any],
    callback: PermissionCallback | None = None,
) -> bool:
    """Decide whether a tool call is permitted.

    Decision flow:
    1. Check mode-based rules
    2. Check tool-level flags (via registry)
    3. Ask external callback if needed
    """
    mode_str = config.get("permission_mode", "auto")
    mode = PermissionMode(mode_str)

    if mode == PermissionMode.ACCEPT_ALL:
        return True

    if mode == PermissionMode.MANUAL:
        if callback:
            req = PermissionRequest(name=tool_name, inputs=tool_input)
            return await callback(req)
        return False

    if mode == PermissionMode.PLAN:
        from ..tools.registry import get as get_tool

        td = get_tool(tool_name)
        if td and td.read_only:
            return True
        if tool_name in ("Write", "Edit"):
            plan_file = config.get("_plan_file", "")
            target = tool_input.get("file_path", "")
            if plan_file and target == plan_file:
                return True
        if tool_name == "Bash":
            return is_safe_bash_command(tool_input.get("command", ""))
        return False

    # AUTO mode
    from ..tools.registry import get as get_tool

    td = get_tool(tool_name)

    if td and td.read_only:
        return True

    if tool_name == "Bash":
        return is_safe_bash_command(tool_input.get("command", ""))

    if td and td.destructive:
        if callback:
            req = PermissionRequest(name=tool_name, inputs=tool_input)
            return await callback(req)
        return False

    # Non-read, non-destructive writes: ask via callback
    if callback:
        req = PermissionRequest(name=tool_name, inputs=tool_input)
        return await callback(req)

    return False
