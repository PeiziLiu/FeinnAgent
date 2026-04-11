"""Skill template execution: direct (current context) or isolated (sub-agent)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from .loader import SkillTemplate, render_template

if TYPE_CHECKING:
    from ..agent import FeinnAgent
    from ..types import AgentEvent

logger = logging.getLogger(__name__)


async def execute_skill(
    template: SkillTemplate,
    params: str,
    agent: FeinnAgent,
    config: dict[str, Any],
) -> AsyncIterator[AgentEvent]:
    """Execute a skill template.

    If template.exec_mode == "isolated", runs as an isolated sub-agent.
    Otherwise (direct), injects the rendered prompt into the current agent loop.

    Args:
        template: SkillTemplate to execute
        params: Raw parameter string from user (after the activator)
        agent: Parent agent instance
        config: Configuration dict

    Yields:
        Agent events (TextChunk, ToolStart, ToolEnd, AgentDone, etc.)
    """
    rendered = render_template(template.template, params, template.param_names)
    message = f"[Skill: {template.skill_id}]\n\n{rendered}"

    logger.info("Executing skill template: %s (mode=%s)", template.skill_id, template.exec_mode)

    if template.exec_mode == "isolated":
        async for event in _execute_isolated(template, message, agent, config):
            yield event
    else:
        async for event in _execute_direct(message, agent, config):
            yield event


async def _execute_direct(
    message: str,
    agent: FeinnAgent,
    config: dict[str, Any],
) -> AsyncIterator[AgentEvent]:
    """Run skill template directly in the current conversation.

    Args:
        message: Rendered skill message
        agent: Parent agent instance
        config: Configuration dict

    Yields:
        Agent events
    """
    # For direct execution, we just run the agent with the skill message
    # The template's system prompt is already part of the agent's context
    async for event in agent.run(message):
        yield event


async def _execute_isolated(
    template: SkillTemplate,
    message: str,
    parent_agent: FeinnAgent,
    config: dict[str, Any],
) -> AsyncIterator[AgentEvent]:
    """Run skill as an isolated sub-agent (separate conversation context).

    Args:
        template: SkillTemplate being executed
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
    if template.preferred_model:
        sub_config["model"] = template.preferred_model
        logger.debug("Skill %s using model override: %s", template.skill_id, template.preferred_model)

    # Restrict tools if template specifies allowed tools
    if template.allowed_tools:
        sub_config["_allowed_tools"] = template.allowed_tools
        logger.debug("Skill %s restricted to tools: %s", template.skill_id, template.allowed_tools)

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
