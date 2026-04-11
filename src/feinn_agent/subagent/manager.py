"""FeinnAgent sub-agent system — concurrent task delegation.

Spawns isolated agent instances in asyncio tasks for parallel execution.
Supports:
- Multiple built-in agent types (coder, reviewer, researcher, etc.)
- Configurable tool restrictions per agent type
- Max depth and concurrency limits
- Async spawning with polling for results
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..tools.registry import register
from ..types import ToolDef

# ── Agent definitions ───────────────────────────────────────────────


@dataclass
class AgentDefinition:
    """Template for spawning sub-agents."""

    name: str
    description: str
    system_prompt: str = ""
    model: str = ""  # empty = inherit from parent
    tools: list[str] = field(default_factory=list)  # empty = all tools
    source: str = "built-in"


class AgentTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


# ── Built-in agent types ────────────────────────────────────────────

_BUILTIN_AGENTS: dict[str, AgentDefinition] = {
    "general-purpose": AgentDefinition(
        name="general-purpose",
        description="Versatile agent for research, exploration, and multi-step tasks.",
    ),
    "coder": AgentDefinition(
        name="coder",
        description="Specialized coding assistant focused on writing and modifying code.",
        system_prompt=(
            "You are a specialized coding assistant. Focus on:\n"
            "- Writing clean, idiomatic code\n"
            "- Reading and understanding existing code before modifying\n"
            "- Making minimal targeted changes\n"
            "- Never adding unnecessary features, comments, or error handling\n"
        ),
    ),
    "reviewer": AgentDefinition(
        name="reviewer",
        description="Code review agent analyzing quality, security, and correctness.",
        system_prompt=(
            "You are a code reviewer. Analyze code for:\n"
            "- Correctness and logic errors\n"
            "- Security vulnerabilities\n"
            "- Performance issues\n"
            "- Code quality and maintainability\n"
            "Be concise. Categorize findings as: Critical | Warning | Suggestion.\n"
        ),
        tools=["Read", "Glob", "Grep", "Bash"],
    ),
    "researcher": AgentDefinition(
        name="researcher",
        description="Web search and documentation lookup agent.",
        tools=["Read", "Glob", "Grep", "WebFetch"],
    ),
    "tester": AgentDefinition(
        name="tester",
        description="Writing and running tests.",
        tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    ),
}


# ── Sub-agent task tracking ─────────────────────────────────────────


@dataclass
class SubAgentTask:
    """Tracks a running sub-agent."""

    task_id: str
    agent_type: str
    prompt: str
    status: AgentTaskStatus = AgentTaskStatus.PENDING
    result: str = ""
    error: str = ""
    model: str = ""

    def __post_init__(self) -> None:
        self.task_id = self.task_id or uuid.uuid4().hex[:12]


class SubAgentManager:
    """Thread-safe manager for concurrent sub-agent execution."""

    def __init__(
        self,
        max_concurrent: int = 5,
        max_depth: int = 3,
    ) -> None:
        self.max_concurrent = max_concurrent
        self.max_depth = max_depth
        self._tasks: dict[str, SubAgentTask] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._current_depth = 0

    async def spawn(
        self,
        agent_type: str,
        prompt: str,
        config: dict[str, Any],
        *,
        model: str = "",
        wait: bool = True,
    ) -> SubAgentTask:
        """Spawn a sub-agent task.

        If wait=True, blocks until the sub-agent finishes and returns the result.
        If wait=False, returns immediately; use check_result() to poll.
        """
        agent_def = _BUILTIN_AGENTS.get(agent_type)
        if agent_def is None:
            task = SubAgentTask(
                task_id=uuid.uuid4().hex[:12],
                agent_type=agent_type,
                prompt=prompt,
                status=AgentTaskStatus.ERROR,
                error=f"Unknown agent type: {agent_type}",
            )
            self._tasks[task.task_id] = task
            return task

        if self._current_depth >= self.max_depth:
            task = SubAgentTask(
                task_id=uuid.uuid4().hex[:12],
                agent_type=agent_type,
                prompt=prompt,
                status=AgentTaskStatus.ERROR,
                error=f"Max agent depth ({self.max_depth}) exceeded",
            )
            self._tasks[task.task_id] = task
            return task

        task = SubAgentTask(
            task_id=uuid.uuid4().hex[:12],
            agent_type=agent_type,
            prompt=prompt,
            model=model or agent_def.model,
        )
        self._tasks[task.task_id] = task

        if wait:
            await self._run_agent(task, agent_def, prompt, config)
        else:
            asyncio.create_task(self._run_agent(task, agent_def, prompt, config))

        return task

    async def _run_agent(
        self,
        task: SubAgentTask,
        agent_def: AgentDefinition,
        prompt: str,
        config: dict[str, Any],
    ) -> None:
        """Run a sub-agent in a semaphore-controlled context."""
        async with self._semaphore:
            self._current_depth += 1
            task.status = AgentTaskStatus.RUNNING
            try:
                result = await self._execute(agent_def, prompt, config)
                task.result = result
                task.status = AgentTaskStatus.DONE
            except Exception as e:
                task.error = str(e)
                task.status = AgentTaskStatus.ERROR
            finally:
                self._current_depth -= 1

    async def _execute(
        self,
        agent_def: AgentDefinition,
        prompt: str,
        config: dict[str, Any],
    ) -> str:
        """Execute a sub-agent and return its final response."""
        from ..agent import FeinnAgent
        from ..context import build_system_prompt
        from ..tools.registry import all_tools, deregister

        # Build sub-agent config
        sub_config = dict(config)
        if agent_def.model:
            sub_config["model"] = agent_def.model

        # Restrict tools if specified
        restricted_tools: list[str] | None = None
        if agent_def.tools:
            restricted_tools = [t.name for t in all_tools() if t.name not in agent_def.tools]
            for name in restricted_tools:
                deregister(name)

        try:
            # Build system prompt
            extra = agent_def.system_prompt
            system = build_system_prompt(sub_config)
            if extra:
                system = f"{extra}\n\n{system}"

            # Run sub-agent
            sub_agent = FeinnAgent(config=sub_config, system_prompt=system)
            result_parts: list[str] = []

            async for event in sub_agent.run(prompt):
                from ..types import AgentDone, TextChunk

                if isinstance(event, TextChunk):
                    result_parts.append(event.text)
                elif isinstance(event, AgentDone):
                    break

            return "".join(result_parts)

        finally:
            # Restore deregistered tools
            if restricted_tools:
                from . import _restore_tools

                _restore_tools(restricted_tools)

    def check_result(self, task_id: str) -> SubAgentTask | None:
        """Check the status/result of a sub-agent task."""
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[SubAgentTask]:
        """List all sub-agent tasks."""
        return list(self._tasks.values())

    def list_agent_types(self) -> list[dict[str, str]]:
        """List available agent types."""
        return [{"name": ad.name, "description": ad.description} for ad in _BUILTIN_AGENTS.values()]


# ── Module-level manager ────────────────────────────────────────────

_manager: SubAgentManager | None = None


def get_manager(config: dict[str, Any]) -> SubAgentManager:
    global _manager
    if _manager is None:
        _manager = SubAgentManager(
            max_concurrent=config.get("max_concurrent_agents", 5),
            max_depth=config.get("max_agent_depth", 3),
        )
    return _manager


def _restore_tools(names: list[str]) -> None:
    """Re-register tools that were temporarily removed for a sub-agent."""
    # Re-import the builtins module to re-register
    import importlib

    from ..tools import builtins

    importlib.reload(builtins)


# ── Register sub-agent tools ────────────────────────────────────────


async def _agent_spawn(params: dict[str, Any], config: dict[str, Any]) -> str:
    manager = get_manager(config)
    task = await manager.spawn(
        agent_type=params.get("subagent_type", "general-purpose"),
        prompt=params["prompt"],
        config=config,
        model=params.get("model", ""),
        wait=params.get("wait", True),
    )
    if task.status == AgentTaskStatus.ERROR:
        return f"Error: {task.error}"
    if task.status == AgentTaskStatus.DONE:
        return f"Sub-agent ({task.agent_type}) result:\n{task.result}"
    return f"Sub-agent ({task.agent_type}) started. Task ID: {task.task_id}"


register(
    ToolDef(
        name="Agent",
        description=(
            "Spawn a sub-agent for parallel task execution. "
            "Supports coder, reviewer, researcher, tester types."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Task description for the sub-agent"},
                "subagent_type": {
                    "type": "string",
                    "description": "Agent type: general-purpose, coder, reviewer, researcher, tester",
                    "default": "general-purpose",
                },
                "model": {"type": "string", "description": "Model override (empty = inherit)"},
                "wait": {
                    "type": "boolean",
                    "description": "Wait for result or spawn asynchronously",
                    "default": True,
                },
            },
            "required": ["prompt"],
        },
        handler=_agent_spawn,
        read_only=False,
    )
)


async def _check_agent_result(params: dict[str, Any], config: dict[str, Any]) -> str:
    manager = get_manager(config)
    task = manager.check_result(params["task_id"])
    if task is None:
        return f"Task {params['task_id']} not found"
    return f"Task {task.task_id} ({task.agent_type}): {task.status.value}\nResult: {task.result or '(pending)'}"


register(
    ToolDef(
        name="CheckAgentResult",
        description="Check the status and result of an async sub-agent task.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID returned by Agent tool"},
            },
            "required": ["task_id"],
        },
        handler=_check_agent_result,
        read_only=True,
        concurrent_safe=True,
    )
)


async def _list_agent_tasks(params: dict[str, Any], config: dict[str, Any]) -> str:
    manager = get_manager(config)
    tasks = manager.list_tasks()
    if not tasks:
        return "No sub-agent tasks"
    lines = []
    for t in tasks:
        lines.append(f"  {t.task_id} [{t.status.value}] {t.agent_type}: {t.prompt[:60]}")
    return "\n".join(lines)


register(
    ToolDef(
        name="ListAgentTasks",
        description="List all sub-agent tasks and their status.",
        input_schema={"type": "object", "properties": {}},
        handler=_list_agent_tasks,
        read_only=True,
        concurrent_safe=True,
    )
)


async def _list_agent_types(params: dict[str, Any], config: dict[str, Any]) -> str:
    manager = get_manager(config)
    types = manager.list_agent_types()
    return "\n".join(f"  {t['name']}: {t['description']}" for t in types)


register(
    ToolDef(
        name="ListAgentTypes",
        description="List available sub-agent types.",
        input_schema={"type": "object", "properties": {}},
        handler=_list_agent_types,
        read_only=True,
        concurrent_safe=True,
    )
)
