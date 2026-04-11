"""Skill execution: inline (current conversation) or forked (sub-agent)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from .loader import SkillDef, substitute_arguments

if TYPE_CHECKING:
    from ..agent import FeinnAgent
    from ..types import AgentEvent

logger = logging.getLogger(__name__)


async def execute_skill(
    skill: SkillDef,
    args: str,
    agent: FeinnAgent,
    config: dict[str, Any],
) -> AsyncIterator[AgentEvent]:
    """Execute a skill.

    If skill.context == "fork", runs as an isolated sub-agent.
    Otherwise (inline), injects the rendered prompt into the current agent loop.

    Args:
        skill: SkillDef to execute
        args: Raw argument string from user (after the trigger word)
        agent: Parent agent instance
        config: Configuration dict

    Yields:
        Agent events (TextChunk, ToolStart, ToolEnd, AgentDone, etc.)
    """
    rendered = substitute_arguments(skill.prompt, args, skill.arguments)
    message = f"[Skill: {skill.name}]\n\n{rendered}"

    logger.info("Executing skill: %s (context=%s)", skill.name, skill.context)

    if skill.context == "fork":
        async for event in _execute_forked(skill, message, agent, config):
            yield event
    else:
        async for event in _execute_inline(message, agent, config):
            yield event


async def _execute_inline(
    message: str,
    agent: FeinnAgent,
    config: dict[str, Any],
) -> AsyncIterator[AgentEvent]:
    """Run skill prompt inline in the current conversation.

    Args:
        message: Rendered skill message
        agent: Parent agent instance
        config: Configuration dict

    Yields:
        Agent events
    """
    # For inline execution, we just run the agent with the skill message
    # The skill's system prompt is already part of the agent's context
    async for event in agent.run(message):
        yield event


async def _execute_forked(
    skill: SkillDef,
    message: str,
    parent_agent: FeinnAgent,
    config: dict[str, Any],
) -> AsyncIterator[AgentEvent]:
    """Run skill as an isolated sub-agent (separate conversation context).

    Args:
        skill: SkillDef to execute
        message: Rendered skill message
        parent_agent: Parent agent instance
        config: Configuration dict

    Yields:
        Agent events from sub-agent
    """
    from ..agent import FeinnAgent
    from ..types import AgentState

    # Build sub-agent config
    sub_config = dict(config)
    sub_config["_depth"] = config.get("_depth", 0) + 1

    # Apply model override if specified
    if skill.model:
        sub_config["model"] = skill.model
        logger.debug("Skill %s using model override: %s", skill.name, skill.model)

    # Restrict tools if skill specifies allowed-tools
    if skill.tools:
        sub_config["_allowed_tools"] = skill.tools
        logger.debug("Skill %s restricted to tools: %s", skill.name, skill.tools)

    # Create fresh state (no shared history)
    sub_state = AgentState()

    # Create sub-agent with same system prompt
    sub_agent = FeinnAgent(
        config=sub_config,
        system_prompt=parent_agent.system_prompt,
        state=sub_state,
        permission_callback=parent_agent._permission_callback,
    )

    # Run sub-agent
    async for event in sub_agent.run(message):
        yield event
