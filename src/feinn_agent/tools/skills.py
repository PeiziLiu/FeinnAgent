"""Skill tools: Skill and SkillList for invoking and discovering skills."""

from __future__ import annotations

import logging
from typing import Any

from ..skill.loader import find_skill, get_skill_by_name, load_skills, substitute_arguments
from ..types import ToolDef

logger = logging.getLogger(__name__)


async def _skill_tool(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Execute a skill by name.

    This is a synchronous wrapper that collects the skill output.
    For streaming execution, use the skill executor directly.

    Args:
        params: Tool parameters
            - name: Skill name or trigger
            - args: Arguments to pass to the skill
        config: Agent configuration

    Returns:
        Skill execution result as string
    """
    skill_name = params.get("name", "").strip()
    args = params.get("args", "")

    if not skill_name:
        return "Error: skill name is required"

    # Look up by name first, then by trigger
    skill = get_skill_by_name(skill_name)
    if skill is None:
        skill = find_skill(skill_name)

    if skill is None:
        names = [s.name for s in load_skills()]
        return f"Error: skill '{skill_name}' not found. Available: {', '.join(names)}"

    # Render the skill prompt
    rendered = substitute_arguments(skill.prompt, args, skill.arguments)

    # For tool execution, we return the rendered prompt
    # The agent will then process this as a user message
    result = f"[Skill: {skill.name}]\n\n{rendered}"

    logger.info("Skill tool invoked: %s with args: %s", skill.name, args)

    return result


async def _skill_list_tool(params: dict[str, Any], config: dict[str, Any]) -> str:
    """List all available skills.

    Args:
        params: Empty dict (no parameters)
        config: Agent configuration

    Returns:
        Formatted list of available skills
    """
    skills = load_skills()

    if not skills:
        return "No skills available. Create skills in ~/.feinn/skills/ or .feinn/skills/"

    lines = ["Available skills:\n"]

    for skill in skills:
        if not skill.user_invocable:
            continue

        triggers = ", ".join(skill.triggers)
        hint = f"  args: {skill.argument_hint}" if skill.argument_hint else ""
        when = f"\n    when: {skill.when_to_use}" if skill.when_to_use else ""
        tools = f"\n    tools: {', '.join(skill.tools)}" if skill.tools else ""
        context = f"\n    context: {skill.context}" if skill.context != "inline" else ""

        lines.append(
            f"- **{skill.name}** [{triggers}]{hint}\n"
            f"  {skill.description}{when}{tools}{context}"
        )

    return "\n".join(lines)


# Tool definitions
SKILL_TOOL_DEF = ToolDef(
    name="Skill",
    description=(
        "Invoke a named skill (reusable prompt template). "
        "Skills are pre-defined workflows for common tasks like committing code, "
        "reviewing PRs, generating tests, etc. "
        "Use SkillList to see available skills and their triggers."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Skill name (e.g., 'commit', 'review') or trigger (e.g., '/commit')",
            },
            "args": {
                "type": "string",
                "description": "Arguments to pass to the skill (replaces $ARGUMENTS placeholder)",
                "default": "",
            },
        },
        "required": ["name"],
    },
    handler=_skill_tool,
    read_only=False,
    concurrent_safe=False,
)

SKILL_LIST_TOOL_DEF = ToolDef(
    name="SkillList",
    description="List all available skills with their names, triggers, descriptions, and usage hints.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=_skill_list_tool,
    read_only=True,
    concurrent_safe=True,
)
