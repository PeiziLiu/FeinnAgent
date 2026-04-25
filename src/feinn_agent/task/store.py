"""FeinnAgent task management with DAG dependency tracking.

Tasks support blocks/blocked_by edges, enabling structured multi-step
workflows where the agent (or sub-agents) can coordinate execution order.

Storage: .feinn/tasks.json
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Backport StrEnum for Python 3.9 compatibility
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass

from ..tools.registry import register
from ..types import ToolDef

# ── Types ───────────────────────────────────────────────────────────


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task:
    """A single task with dependency edges."""

    __slots__ = (
        "id",
        "subject",
        "description",
        "status",
        "active_form",
        "owner",
        "blocks",
        "blocked_by",
        "metadata",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        id: str,
        subject: str,
        description: str = "",
        status: TaskStatus = TaskStatus.PENDING,
        active_form: str = "",
        owner: str = "",
        blocks: list[str] | None = None,
        blocked_by: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.id = id
        self.subject = subject
        self.description = description
        self.status = status
        self.active_form = active_form
        self.owner = owner
        self.blocks = blocks or []
        self.blocked_by = blocked_by or []
        self.metadata = metadata or {}
        now = datetime.now().isoformat()
        self.created_at = now
        self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status.value,
            "active_form": self.active_form,
            "owner": self.owner,
            "blocks": self.blocks,
            "blocked_by": self.blocked_by,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Task:
        t = cls(
            id=d["id"],
            subject=d["subject"],
            description=d.get("description", ""),
            status=TaskStatus(d.get("status", "pending")),
            active_form=d.get("active_form", ""),
            owner=d.get("owner", ""),
            blocks=d.get("blocks", []),
            blocked_by=d.get("blocked_by", []),
            metadata=d.get("metadata", {}),
        )
        t.created_at = d.get("created_at", t.created_at)
        t.updated_at = d.get("updated_at", t.updated_at)
        return t


# ── Persistence ─────────────────────────────────────────────────────

_TASKS_FILE = Path.cwd() / ".feinn" / "tasks.json"


def _load_tasks() -> dict[str, Task]:
    if not _TASKS_FILE.exists():
        return {}
    try:
        data = json.loads(_TASKS_FILE.read_text(encoding="utf-8"))
        return {t["id"]: Task.from_dict(t) for t in data.get("tasks", [])}
    except (json.JSONDecodeError, KeyError):
        return {}


def _save_tasks(tasks: dict[str, Task]) -> None:
    _TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"tasks": [t.to_dict() for t in tasks.values()]}
    _TASKS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _next_id(tasks: dict[str, Task]) -> str:
    max_id = 0
    for tid in tasks:
        try:
            max_id = max(max_id, int(tid))
        except ValueError:
            pass
    return str(max_id + 1)


# ── Core operations ─────────────────────────────────────────────────


def task_create(
    subject: str,
    description: str = "",
    active_form: str = "",
    owner: str = "",
    blocked_by: list[str] | None = None,
) -> str:
    """Create a new task, optionally specifying dependencies."""
    tasks = _load_tasks()
    tid = _next_id(tasks)

    blocked_by = blocked_by or []
    # Validate dependencies exist
    for dep_id in blocked_by:
        if dep_id not in tasks:
            return f"Error: dependency task #{dep_id} not found"

    task = Task(
        id=tid,
        subject=subject,
        description=description,
        active_form=active_form,
        owner=owner,
        blocked_by=blocked_by,
    )

    # Update reverse edges
    for dep_id in blocked_by:
        if dep_id in tasks:
            tasks[dep_id].blocks.append(tid)

    tasks[tid] = task
    _save_tasks(tasks)
    return f"Task created: #{tid}"


def task_update(
    task_id: str,
    **updates: Any,
) -> str:
    """Update a task's fields and optionally add/remove dependencies."""
    tasks = _load_tasks()
    if task_id not in tasks:
        return f"Error: task #{task_id} not found"

    task = tasks[task_id]

    # Handle status
    if "status" in updates:
        task.status = TaskStatus(updates["status"])

    # Handle simple fields
    for field in ("subject", "description", "active_form", "owner"):
        if field in updates:
            setattr(task, field, updates[field])

    # Handle dependency additions
    for dep_id in updates.get("add_blocked_by", []):
        if dep_id in tasks and dep_id not in task.blocked_by:
            task.blocked_by.append(dep_id)
            tasks[dep_id].blocks.append(task_id)

    for dep_id in updates.get("add_blocks", []):
        if dep_id in tasks and dep_id not in task.blocks:
            task.blocks.append(dep_id)
            tasks[dep_id].blocked_by.append(task_id)

    # Handle dependency removals
    for dep_id in updates.get("remove_blocked_by", []):
        if dep_id in task.blocked_by:
            task.blocked_by.remove(dep_id)
            if dep_id in tasks and task_id in tasks[dep_id].blocks:
                tasks[dep_id].blocks.remove(task_id)

    task.updated_at = datetime.now().isoformat()
    _save_tasks(tasks)
    return f"Task #{task_id} updated"


def task_list() -> str:
    """List all tasks with status and dependency info."""
    tasks = _load_tasks()
    if not tasks:
        return "No tasks"

    lines: list[str] = []
    status_icons = {
        TaskStatus.PENDING: "○",
        TaskStatus.IN_PROGRESS: "●",
        TaskStatus.COMPLETED: "✓",
        TaskStatus.CANCELLED: "✗",
    }

    for tid in sorted(tasks, key=lambda x: int(x) if x.isdigit() else 0):
        t = tasks[tid]
        icon = status_icons.get(t.status, "?")
        dep_info = ""
        if t.blocked_by:
            dep_info += f" [blocked by #{', #'.join(t.blocked_by)}]"
        if t.blocks:
            dep_info += f" [blocks #{', #'.join(t.blocks)}]"
        lines.append(f"  #{tid} [{t.status.value}] {icon} {t.subject}{dep_info}")

    return "\n".join(lines)


def task_get(task_id: str) -> str:
    """Get detailed info about a specific task."""
    tasks = _load_tasks()
    if task_id not in tasks:
        return f"Error: task #{task_id} not found"

    t = tasks[task_id]
    parts = [
        f"Task #{t.id}: {t.subject}",
        f"  Status: {t.status.value}",
        f"  Description: {t.description or '(none)'}",
        f"  Active form: {t.active_form or '(none)'}",
        f"  Owner: {t.owner or '(none)'}",
        f"  Blocked by: {', '.join(f'#{d}' for d in t.blocked_by) or 'none'}",
        f"  Blocks: {', '.join(f'#{d}' for d in t.blocks) or 'none'}",
        f"  Created: {t.created_at}",
        f"  Updated: {t.updated_at}",
    ]
    return "\n".join(parts)


# ── Register task tools ─────────────────────────────────────────────


async def _task_create_handler(params: dict[str, Any], config: dict[str, Any]) -> str:
    return task_create(
        subject=params["subject"],
        description=params.get("description", ""),
        active_form=params.get("active_form", ""),
        owner=params.get("owner", ""),
        blocked_by=params.get("blocked_by"),
    )


register(
    ToolDef(
        name="TaskCreate",
        description="Create a task with optional dependency edges. Returns the new task ID.",
        input_schema={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Task title"},
                "description": {"type": "string", "description": "Detailed description"},
                "active_form": {
                    "type": "string",
                    "description": "Present-tense activity description (e.g. 'Running tests')",
                },
                "owner": {"type": "string", "description": "Agent or user assigned to this task"},
                "blocked_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Task IDs that must complete first",
                },
            },
            "required": ["subject"],
        },
        handler=_task_create_handler,
        read_only=False,
    )
)


async def _task_update_handler(params: dict[str, Any], config: dict[str, Any]) -> str:
    return task_update(
        task_id=params["task_id"],
        status=params.get("status"),
        subject=params.get("subject"),
        description=params.get("description"),
        active_form=params.get("active_form"),
        owner=params.get("owner"),
        add_blocked_by=params.get("add_blocked_by"),
        remove_blocked_by=params.get("remove_blocked_by"),
        add_blocks=params.get("add_blocks"),
        remove_blocks=params.get("remove_blocks"),
    )


register(
    ToolDef(
        name="TaskUpdate",
        description="Update a task's fields and dependency edges.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to update"},
                "status": {
                    "type": "string",
                    "description": "New status: pending, in_progress, completed, cancelled",
                },
                "subject": {"type": "string", "description": "Updated title"},
                "description": {"type": "string", "description": "Updated description"},
                "active_form": {"type": "string", "description": "Updated activity description"},
                "owner": {"type": "string", "description": "Updated owner"},
                "add_blocked_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Task IDs to add as dependencies",
                },
                "remove_blocked_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Task IDs to remove from dependencies",
                },
            },
            "required": ["task_id"],
        },
        handler=_task_update_handler,
        read_only=False,
    )
)


async def _task_list_handler(params: dict[str, Any], config: dict[str, Any]) -> str:
    return task_list()


register(
    ToolDef(
        name="TaskList",
        description="List all tasks with their status and dependencies.",
        input_schema={"type": "object", "properties": {}},
        handler=_task_list_handler,
        read_only=True,
        concurrent_safe=True,
    )
)


async def _task_get_handler(params: dict[str, Any], config: dict[str, Any]) -> str:
    return task_get(params["task_id"])


register(
    ToolDef(
        name="TaskGet",
        description="Get detailed info about a specific task.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
            },
            "required": ["task_id"],
        },
        handler=_task_get_handler,
        read_only=True,
        concurrent_safe=True,
    )
)
