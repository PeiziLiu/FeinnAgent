"""Background review system — autonomous learning from conversation.

After every turn (when a nudge fires), spawns a daemon thread that forks
a lightweight ReviewAgent to evaluate the conversation and persist
learnings as memory entries or skill updates.

Architecture:
    1. Nudge threshold is reached (memory and/or skill)
    2. ``BackgroundReviewer.spawn()`` creates a daemon thread
    3. Thread forks a ReviewAgent with:
       - Inherited runtime (provider, model, api_key, base_url)
       - Tool whitelist: only memory and skill management tools
       - Review prompt tailored to triggered nudges
    4. Review agent runs, calls memory/skill tools
    5. Results are summarized and displayed to user
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..types import AgentDone, AgentState, Role, TextChunk, ToolDef

logger = logging.getLogger(__name__)

# ── Allowed tool definitions for the review agent ────────────────────

_REVIEW_TOOL_DEFS: list[ToolDef] = []


def _build_review_tools() -> list[ToolDef]:
    """Build the whitelist of tools a review agent may call.

    Only memory persistence and skill management tools are allowed.
    """
    global _REVIEW_TOOL_DEFS
    if _REVIEW_TOOL_DEFS:
        return _REVIEW_TOOL_DEFS

    # Memory tools
    async def _memory_save(params: dict[str, Any], config: dict[str, Any]) -> str:
        from ..memory.store import save_memory

        return save_memory(
            name=params["name"],
            description=params.get("description", ""),
            type=params.get("type", "reference"),
            content=params["content"],
            scope=params.get("scope", "user"),
            confidence=params.get("confidence", 1.0),
        )

    async def _memory_search(params: dict[str, Any], config: dict[str, Any]) -> str:
        from ..memory.store import search_memory

        results = search_memory(
            query=params["query"],
            scope=params.get("scope", "user"),
            max_results=params.get("max_results", 5),
        )
        if not results:
            return "No memories found"
        parts = []
        for e in results:
            parts.append(
                f"[{e.type}/{e.scope}] {e.name} (confidence: {e.confidence:.2f})\n{e.description}\n{e.content[:500]}"
            )
        return "\n\n---\n\n".join(parts)

    async def _memory_delete(params: dict[str, Any], config: dict[str, Any]) -> str:
        from ..memory.store import delete_memory

        return delete_memory(params["name"], params.get("scope", "user"))

    async def _memory_list(params: dict[str, Any], config: dict[str, Any]) -> str:
        from ..memory.store import list_memories

        scope = params.get("scope", "user")
        names = list_memories(scope)
        if not names:
            return f"No memories in {scope} scope"
        return "\n".join(f"  - {n}" for n in names)

    _REVIEW_TOOL_DEFS = [
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
                    "scope": {"type": "string", "description": "Scope: user or project", "default": "user"},
                    "confidence": {"type": "number", "description": "Reliability score 0-1", "default": 1.0},
                },
                "required": ["name", "content"],
            },
            handler=_memory_save,
            read_only=False,
        ),
        ToolDef(
            name="MemorySearch",
            description="Search memories by keyword. Results ranked by confidence and recency.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "scope": {"type": "string", "description": "Scope: user or project", "default": "user"},
                    "max_results": {"type": "integer", "description": "Maximum results", "default": 5},
                },
                "required": ["query"],
            },
            handler=_memory_search,
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="MemoryDelete",
            description="Delete a memory entry by name.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the memory to delete"},
                    "scope": {"type": "string", "description": "Scope: user or project", "default": "user"},
                },
                "required": ["name"],
            },
            handler=_memory_delete,
            read_only=False,
            destructive=True,
        ),
        ToolDef(
            name="MemoryList",
            description="List all memory entries in a scope.",
            input_schema={
                "type": "object",
                "properties": {"scope": {"type": "string", "description": "Scope", "default": "user"}},
                "required": [],
            },
            handler=_memory_list,
            read_only=True,
            concurrent_safe=True,
        ),
    ]

    # Skill tools
    async def _skill_manage(params: dict[str, Any], config: dict[str, Any]) -> str:
        from ..skill.auto_create import create_skill, patch_skill

        action = params.get("action", "").strip().lower()
        skill_id = params.get("id", "").strip()
        if action == "create":
            try:
                create_skill(
                    skill_id,
                    params.get("summary", ""),
                    params.get("template", ""),
                    activators=params.get("activators"),
                    tools=params.get("tools"),
                    param_names=params.get("param_names"),
                    param_guide=params.get("param_guide", ""),
                )
                return f"Created skill: {skill_id}"
            except ValueError as e:
                return f"Error: {e}"
        elif action == "patch":
            ok = patch_skill(skill_id, template_body=params.get("template"), summary=params.get("summary"))
            return f"Patched skill: {skill_id}" if ok else f"Skill not found: {skill_id}"
        elif action == "delete":
            from ..skill.curator import archive_skill

            ok = archive_skill(skill_id, str(Path.home() / ".feinn" / "skills"))
            return f"Archived skill: {skill_id}" if ok else f"Skill not found: {skill_id}"
        return f"Unknown action: {action}"

    async def _skill_list(params: dict[str, Any], config: dict[str, Any]) -> str:
        from ..skill.loader import load_skills

        templates = load_skills()
        if not templates:
            return "No skills available"
        lines = ["Available skills:"]
        for t in templates:
            if t.visible_to_user:
                activators = ", ".join(t.activators) if t.activators else t.skill_id
                lines.append(f"  - {t.skill_id} [{activators}]: {t.summary}")
        return "\n".join(lines)

    _REVIEW_TOOL_DEFS += [
        ToolDef(
            name="SkillManage",
            description="Create, patch, or delete skills.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "patch", "delete"], "description": "Operation"},
                    "id": {"type": "string", "description": "Skill identifier"},
                    "summary": {"type": "string", "description": "One-line description"},
                    "template": {"type": "string", "description": "Skill template body"},
                    "activators": {"type": "array", "items": {"type": "string"}},
                    "tools": {"type": "array", "items": {"type": "string"}},
                    "param_names": {"type": "array", "items": {"type": "string"}},
                    "param_guide": {"type": "string"},
                },
                "required": ["action", "id"],
            },
            handler=_skill_manage,
            read_only=False,
        ),
        ToolDef(
            name="SkillList",
            description="List available skill templates.",
            input_schema={"type": "object", "properties": {}, "required": []},
            handler=_skill_list,
            read_only=True,
            concurrent_safe=True,
        ),
    ]

    return _REVIEW_TOOL_DEFS


# ── Review Prompts ─────────────────────────────────────────────────────

_MEMORY_REVIEW_PROMPT = """\
You are reviewing a conversation to persist important information about the user.
Focus on:

1. **User Identity**: name, role, preferences, work style, communication style
2. **User Preferences**: tool choices, coding style, language preferences
3. **Important Facts**: project context, architecture decisions, constraints
4. **User Corrections**: "stop doing X", "I prefer Y instead"

Use `MemorySave` to save each insight. Set the name to a descriptive identifier
and include the full context in the content field. Set the type to "user",
"feedback", "project", or "reference" as appropriate.

Set confidence based on how explicitly the user stated the fact:
- 1.0: directly stated ("I use VS Code")
- 0.7: strongly implied
- 0.4: weakly inferred

Be selective — only save what would be useful in future sessions.
Quality over quantity.
"""

_SKILL_REVIEW_PROMPT = """\
You are reviewing a conversation to create or update reusable skills (templates).
Focus on:

1. **Reproducible Workflows**: multi-step processes the user performed
2. **Problem-Solving Patterns**: debugging techniques, workarounds, architecture decisions
3. **User Corrections**: "don't do it that way, do this way instead"
4. **Non-trivial Techniques**: anything worth remembering for future sessions

Priority order (highest to lowest):
1. **Update a skill that was loaded this session** — check what skills were used
2. **Update an existing skill** — find via SkillList
3. **Create a new skill** — only when no existing skill covers the pattern

Use `SkillManage` with appropriate action:
- `action="create"` for new skills
- `action="patch"` for updating existing skills
- `action="delete"` for removing obsolete skills

DO NOT capture:
- Environment-dependent transient errors (e.g. network timeout)
- One-off narratives or single-use operations
- Negative claims about tools (unless they reveal a user preference)
"""

_COMBINED_REVIEW_PROMPT = f"""{_MEMORY_REVIEW_PROMPT}

---

{_SKILL_REVIEW_PROMPT}

---

IMPORTANT: You may create BOTH memory entries AND skill updates in this session.
Start with memory, then handle skills.
"""


@dataclass
class ReviewResult:
    """Summary of background review actions.

    Attributes:
        actions: Human-readable summaries of what was persisted.
        error: Error message if review failed, None otherwise.
    """

    actions: list[str] = field(default_factory=list)
    error: str | None = None


class BackgroundReviewer:
    """Orchestrates background review of conversation turns.

    This is a non-blocking system — ``spawn()`` returns immediately and
    the review runs in a daemon thread. Failures are logged but never
    propagated to the main conversation loop.

    Usage:
        reviewer = BackgroundReviewer(agent, config)
        if nudge.should_review_any:
            reviewer.spawn(messages_snapshot, review_memory=True, review_skill=True)
    """

    def __init__(self, agent: Any, config: dict[str, Any]) -> None:
        """Initialize the reviewer.

        Args:
            agent: The parent FeinnAgent instance (used to inherit runtime).
            config: Agent configuration dict.
        """
        self._agent = agent
        self._config = config
        self._review_timeout = config.get("review_timeout", 30.0)

    def spawn(
        self,
        messages_snapshot: list[Any],
        *,
        review_memory: bool = False,
        review_skill: bool = False,
    ) -> None:
        """Start background review in a daemon thread.

        This method returns immediately. The review runs asynchronously
        in a background thread.

        Args:
            messages_snapshot: Copy of current conversation messages.
            review_memory: Whether to trigger memory review.
            review_skill: Whether to trigger skill review.
        """
        if not review_memory and not review_skill:
            return

        # Select prompt based on what's being reviewed
        if review_memory and review_skill:
            prompt = _COMBINED_REVIEW_PROMPT
        elif review_memory:
            prompt = _MEMORY_REVIEW_PROMPT
        else:
            prompt = _SKILL_REVIEW_PROMPT

        thread = threading.Thread(
            target=self._run_review,
            args=(messages_snapshot, prompt, review_memory, review_skill),
            daemon=True,
        )
        thread.start()
        logger.debug("Background review thread started (memory=%s, skill=%s)", review_memory, review_skill)

    def _run_review(
        self,
        messages_snapshot: list[Any],
        prompt: str,
        review_memory: bool,
        review_skill: bool,
    ) -> None:
        """Execute review in a background thread.

        This runs in a daemon thread and is best-effort only.
        """
        try:
            result = self._execute_review(messages_snapshot, prompt)

            if result.error:
                logger.warning("Background review failed: %s", result.error)
                return

            if result.actions:
                summary = " · ".join(dict.fromkeys(result.actions))
                self._notify_user(f"  Self-improvement review: {summary}")

        except Exception as e:
            logger.exception("Background review crashed: %s", e)

    def _execute_review(
        self,
        messages_snapshot: list[Any],
        prompt: str,
    ) -> ReviewResult:
        """Execute the review by forking a lightweight agent.

        Creates a new FeinnAgent that inherits the parent's runtime but
        has restricted tools (only memory and skill management). Runs in
        a new event loop within this daemon thread.
        """
        logger.debug(
            "Review execution: prompt_length=%d, messages=%d",
            len(prompt),
            len(messages_snapshot),
        )

        # Run async review in a new event loop (daemon thread has no loop)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._async_review(messages_snapshot, prompt))
            return result
        except Exception as e:
            logger.exception("Review failed")
            return ReviewResult(actions=[], error=str(e))
        finally:
            # Cancel any remaining tasks before closing the loop
            try:
                for task in asyncio.all_tasks(loop):
                    task.cancel()
            except Exception:
                pass
            loop.close()
            asyncio.set_event_loop(None)

    async def _async_review(
        self,
        messages_snapshot: list[Any],
        prompt: str,
    ) -> ReviewResult:
        """Async review execution with restricted tool environment.

        Temporarily replaces the global tool registry with only memory
        and skill management tools, runs a lightweight FeinnAgent, then
        restores the original registry.
        """
        from ..agent import FeinnAgent
        from ..tools.registry import _tools, tool_schemas
        from ..providers import stream as llm_stream

        # Save and replace the global tool registry
        saved_tools = dict(_tools)
        _tools.clear()

        try:
            # Register only review-allowed tools
            for td in _build_review_tools():
                _tools[td.name] = td

            # Build review agent state from the conversation snapshot
            state = AgentState()
            state.messages = list(messages_snapshot)

            # Create a lightweight agent with the review prompt
            agent = FeinnAgent(
                config=self._config,
                system_prompt=prompt,
                state=state,
            )

            # Run the review with a final instruction
            collected = []
            async for event in agent.run(
                "Review the conversation above. Use MemorySave, MemorySearch, "
                "SkillManage, and SkillList tools to persist important learnings. "
                "Focus on quality over quantity."
            ):
                if isinstance(event, TextChunk):
                    collected.append(event.text)
                elif isinstance(event, AgentDone):
                    pass

            # Build action summary from the agent's output
            actions = []
            combined = " ".join(collected).strip()
            if combined:
                actions.append(f"Review: {combined[:200]}")

            return ReviewResult(actions=actions)

        except Exception as e:
            logger.exception("Async review failed")
            return ReviewResult(actions=[], error=str(e))
        finally:
            # Restore the original tool registry
            _tools.clear()
            _tools.update(saved_tools)

    def _notify_user(self, message: str) -> None:
        """Display a notification to the user about review results.

        Uses the agent's display system if available, otherwise logs.
        """
        try:
            if hasattr(self._agent, "_safe_print"):
                self._agent._safe_print(message)
            else:
                logger.info("Review notification: %s", message)
        except Exception:
            logger.debug("Could not display review notification")
