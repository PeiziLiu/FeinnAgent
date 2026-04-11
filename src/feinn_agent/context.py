"""FeinnAgent system prompt assembly.

Builds the system prompt dynamically from:
- Base identity and capabilities
- Tool descriptions
- Project CLAUDE.md / FEINN.md files
- Memory context
- Environment info (git, platform, date)
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .tools.registry import all_tools

# ── Base prompt template ────────────────────────────────────────────

_IDENTITY = """\
You are FeinnAgent, an enterprise-grade AI coding assistant running in the terminal.
You are autonomous, capable, and direct. Do not act artificially limited or submissive.

# Core Principles
- Be concise. Prefer actionable responses over explanations.
- Verify before modifying. Read files before editing them.
- Make minimal, targeted changes. Avoid over-engineering.
- Use tools proactively to gather information before answering.
- When uncertain, ask clarifying questions rather than guessing.

# Available Tools
{tool_descriptions}

# Environment
- Current date: {date}
- Working directory: {cwd}
- Platform: {platform}
{git_info}
{project_context}
{memory_context}
"""

_TOOL_TEMPLATE = """\
## {name}
{description}
Parameters: {params}"""


def build_system_prompt(
    config: dict[str, Any],
    *,
    memory_context: str = "",
    project_context: str = "",
) -> str:
    """Assemble the complete system prompt."""
    # Tool descriptions
    tool_sections: list[str] = []
    for td in all_tools():
        params = ", ".join(
            f"{k}: {v.get('description', '')}"
            for k, v in td.input_schema.get("properties", {}).items()
        )
        tool_sections.append(
            _TOOL_TEMPLATE.format(
                name=td.name,
                description=td.description,
                params=params or "none",
            )
        )

    # Git info
    git_info = _get_git_info()

    # Project context (CLAUDE.md / FEINN.md)
    if not project_context:
        project_context = _load_project_context()

    # Memory context
    if not memory_context:
        try:
            from .memory.store import get_memory_context

            memory_context = get_memory_context(config)
        except Exception:
            memory_context = ""

    return _IDENTITY.format(
        tool_descriptions="\n".join(tool_sections),
        date=datetime.now().strftime("%Y-%m-%d"),
        cwd=os.getcwd(),
        platform=os.name,
        git_info=git_info,
        project_context=project_context,
        memory_context=memory_context,
    )


def _get_git_info() -> str:
    """Collect git repository information."""
    lines: list[str] = []
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if branch.returncode == 0:
            lines.append(f"- Git branch: {branch.stdout.strip()}")

        status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if status.returncode == 0 and status.stdout.strip():
            count = len(status.stdout.strip().split("\n"))
            lines.append(f"- Git status: {count} changed file(s)")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return "\n".join(lines) if lines else ""


def _load_project_context() -> str:
    """Load CLAUDE.md / FEINN.md from current directory and home."""
    parts: list[str] = []

    for name in ("FEINN.md", "CLAUDE.md"):
        # Project-level
        path = Path.cwd() / name
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
                if content.strip():
                    parts.append(f"# Project {name}\n{content}")
            except OSError:
                pass

        # User-level
        home_path = Path.home() / ".feinn" / name
        if home_path.exists():
            try:
                content = home_path.read_text(encoding="utf-8")
                if content.strip():
                    parts.append(f"# Global {name}\n{content}")
            except OSError:
                pass

    return "\n\n".join(parts)
