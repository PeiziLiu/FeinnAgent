"""FeinnAgent dual-scope memory system.

Storage layout:
  ~/.feinn/memory/          — user scope (cross-project)
  .feinn/memory/            — project scope (repo-local)

Each memory entry is a markdown file with YAML frontmatter:
  ---
  name: coding_style
  description: Python formatting preferences
  type: feedback
  confidence: 0.95
  source: user
  last_used_at: 2026-04-11
  conflict_group: coding_style
  ---
  Content body...
"""

from __future__ import annotations

import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..tools.registry import register
from ..types import ToolDef

# ── Storage paths ───────────────────────────────────────────────────


def _user_memory_dir() -> Path:
    home = os.environ.get("FEINN_HOME", str(Path.home() / ".feinn"))
    return Path(home) / "memory"


def _project_memory_dir() -> Path:
    return Path.cwd() / ".feinn" / "memory"


def _memory_dir(scope: str) -> Path:
    return _user_memory_dir() if scope == "user" else _project_memory_dir()


# ── Memory entry ────────────────────────────────────────────────────


class MemoryEntry:
    """A single memory entry with metadata."""

    __slots__ = (
        "name",
        "description",
        "type",
        "content",
        "scope",
        "confidence",
        "source",
        "last_used_at",
        "conflict_group",
    )

    def __init__(
        self,
        name: str,
        description: str,
        type: str,  # "user" | "feedback" | "project" | "reference"
        content: str,
        scope: str = "user",
        confidence: float = 1.0,
        source: str = "user",
        last_used_at: str = "",
        conflict_group: str = "",
    ) -> None:
        self.name = name
        self.description = description
        self.type = type
        self.content = content
        self.scope = scope
        self.confidence = confidence
        self.source = source
        self.last_used_at = last_used_at
        self.conflict_group = conflict_group

    def to_markdown(self) -> str:
        lines = [
            "---",
            f"name: {self.name}",
            f"description: {self.description}",
            f"type: {self.type}",
            f"confidence: {self.confidence}",
            f"source: {self.source}",
            f"last_used_at: {self.last_used_at}",
            f"conflict_group: {self.conflict_group}",
            "---",
            self.content,
        ]
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str, scope: str = "user") -> MemoryEntry | None:
        """Parse a memory entry from markdown with YAML frontmatter."""
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return None

        meta_text, content = match.groups()
        meta: dict[str, str] = {}
        for line in meta_text.strip().splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                meta[key.strip()] = val.strip()

        return cls(
            name=meta.get("name", "unknown"),
            description=meta.get("description", ""),
            type=meta.get("type", "reference"),
            content=content.strip(),
            scope=scope,
            confidence=float(meta.get("confidence", "1.0")),
            source=meta.get("source", "user"),
            last_used_at=meta.get("last_used_at", ""),
            conflict_group=meta.get("conflict_group", ""),
        )


# ── Core operations ─────────────────────────────────────────────────


def save_memory(
    name: str,
    description: str,
    type: str,
    content: str,
    scope: str = "user",
    confidence: float = 1.0,
    source: str = "user",
    conflict_group: str = "",
) -> str:
    """Save a memory entry to disk."""
    entry = MemoryEntry(
        name=name,
        description=description,
        type=type,
        content=content,
        scope=scope,
        confidence=confidence,
        source=source,
        last_used_at=datetime.now().strftime("%Y-%m-%d"),
        conflict_group=conflict_group or name,
    )

    mem_dir = _memory_dir(scope)
    mem_dir.mkdir(parents=True, exist_ok=True)
    filepath = mem_dir / f"{name}.md"
    filepath.write_text(entry.to_markdown(), encoding="utf-8")
    return f"Saved memory: {name} ({scope} scope)"


def search_memory(
    query: str,
    scope: str = "user",
    max_results: int = 5,
) -> list[MemoryEntry]:
    """Search memories by keyword, ranked by confidence x recency."""
    mem_dir = _memory_dir(scope)
    if not mem_dir.exists():
        return []

    entries: list[tuple[float, MemoryEntry]] = []
    query_lower = query.lower()
    now = datetime.now()

    for filepath in mem_dir.glob("*.md"):
        try:
            text = filepath.read_text(encoding="utf-8")
            entry = MemoryEntry.from_markdown(text, scope=scope)
            if entry is None:
                continue

            # Keyword match
            searchable = f"{entry.name} {entry.description} {entry.content}".lower()
            if query_lower not in searchable:
                continue

            # Score: confidence × recency decay
            score = entry.confidence
            if entry.last_used_at:
                try:
                    last = datetime.strptime(entry.last_used_at, "%Y-%m-%d")
                    days_ago = (now - last).days
                    score *= math.exp(-days_ago / 30)
                except ValueError:
                    pass

            entries.append((score, entry))

        except OSError:
            continue

    entries.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in entries[:max_results]]


def list_memories(scope: str = "user") -> list[str]:
    """List all memory names in a scope."""
    mem_dir = _memory_dir(scope)
    if not mem_dir.exists():
        return []
    return sorted(p.stem for p in mem_dir.glob("*.md"))


def delete_memory(name: str, scope: str = "user") -> str:
    """Delete a memory entry by name."""
    filepath = _memory_dir(scope) / f"{name}.md"
    if filepath.exists():
        filepath.unlink()
        return f"Deleted memory: {name}"
    return f"Memory not found: {name}"


def get_memory_context(config: dict[str, Any]) -> str:
    """Build memory index text for system prompt injection."""
    lines: list[str] = []

    for scope in ("user", "project"):
        names = list_memories(scope)
        if not names:
            continue
        lines.append(f"# Memory ({scope} scope)")
        for name in names:
            filepath = _memory_dir(scope) / f"{name}.md"
            try:
                text = filepath.read_text(encoding="utf-8")
                entry = MemoryEntry.from_markdown(text, scope=scope)
                if entry:
                    lines.append(f"  - [{entry.type}/{scope}] {name}: {entry.description}")
            except OSError:
                pass

    return "\n".join(lines) if lines else ""


# ── Register memory tools ───────────────────────────────────────────


async def _memory_save(params: dict[str, Any], config: dict[str, Any]) -> str:
    return save_memory(
        name=params["name"],
        description=params.get("description", ""),
        type=params.get("type", "reference"),
        content=params["content"],
        scope=params.get("scope", "user"),
        confidence=params.get("confidence", 1.0),
        conflict_group=params.get("conflict_group", ""),
    )


register(
    ToolDef(
        name="MemorySave",
        description="Save a memory entry for cross-session persistence. Supports user and project scopes.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Unique name for this memory"},
                "description": {"type": "string", "description": "One-line summary"},
                "type": {
                    "type": "string",
                    "description": "Category: user, feedback, project, reference",
                    "default": "reference",
                },
                "content": {"type": "string", "description": "Memory body content"},
                "scope": {
                    "type": "string",
                    "description": "Scope: user (global) or project (repo-local)",
                    "default": "user",
                },
                "confidence": {
                    "type": "number",
                    "description": "Reliability score 0-1",
                    "default": 1.0,
                },
                "conflict_group": {
                    "type": "string",
                    "description": "Group tag for conflict detection",
                },
            },
            "required": ["name", "content"],
        },
        handler=_memory_save,
        read_only=False,
    )
)


async def _memory_search(params: dict[str, Any], config: dict[str, Any]) -> str:
    results = search_memory(
        query=params["query"],
        scope=params.get("scope", "user"),
        max_results=params.get("max_results", 5),
    )
    if not results:
        return "No memories found matching the query"
    parts = []
    for entry in results:
        parts.append(
            f"[{entry.type}/{entry.scope}] {entry.name} "
            f"(confidence: {entry.confidence:.2f})\n"
            f"{entry.description}\n{entry.content[:500]}"
        )
    return "\n\n---\n\n".join(parts)


register(
    ToolDef(
        name="MemorySearch",
        description="Search memories by keyword. Results ranked by confidence and recency.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "scope": {
                    "type": "string",
                    "description": "Scope to search: user, project, or both",
                    "default": "user",
                },
                "max_results": {"type": "integer", "description": "Maximum results", "default": 5},
            },
            "required": ["query"],
        },
        handler=_memory_search,
        read_only=True,
        concurrent_safe=True,
    )
)


async def _memory_delete(params: dict[str, Any], config: dict[str, Any]) -> str:
    return delete_memory(params["name"], params.get("scope", "user"))


register(
    ToolDef(
        name="MemoryDelete",
        description="Delete a memory entry by name.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the memory to delete"},
                "scope": {
                    "type": "string",
                    "description": "Scope: user or project",
                    "default": "user",
                },
            },
            "required": ["name"],
        },
        handler=_memory_delete,
        read_only=False,
        destructive=True,
    )
)


async def _memory_list(params: dict[str, Any], config: dict[str, Any]) -> str:
    scope = params.get("scope", "user")
    names = list_memories(scope)
    if not names:
        return f"No memories in {scope} scope"
    return "\n".join(f"  - {n}" for n in names)


register(
    ToolDef(
        name="MemoryList",
        description="List all memory entries in a scope.",
        input_schema={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "description": "Scope: user or project",
                    "default": "user",
                },
            },
            "required": [],
        },
        handler=_memory_list,
        read_only=True,
        concurrent_safe=True,
    )
)
