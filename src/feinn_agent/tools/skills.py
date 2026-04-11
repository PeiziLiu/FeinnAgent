"""Skill tools: Skill and SkillList for invoking and discovering skill templates."""

from __future__ import annotations

import logging
from typing import Any

from ..skill.loader import (
    find_skill,
    get_skill_by_name,
    load_skills,
    render_template,
)
from ..types import ToolDef

logger = logging.getLogger(__name__)


async def _skill_tool(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Execute a skill template by ID.

    This is a synchronous wrapper that prepares the skill for execution.
    For streaming execution, use the skill executor directly.

    Args:
        params: Tool parameters
            - id: Skill identifier or activator
            - params: Parameters to pass to the skill
        config: Agent configuration

    Returns:
        Skill execution preparation result as string
    """
    skill_id = params.get("id", params.get("name", "")).strip()
    skill_params = params.get("params", params.get("args", ""))

    if not skill_id:
        return "Error: skill id is required"

    # Look up by ID first, then by activator
    template = get_skill_by_name(skill_id)
    if template is None:
        template = find_skill(skill_id)

    if template is None:
        ids = [t.skill_id for t in load_skills()]
        return f"Error: skill '{skill_id}' not found. Available: {', '.join(ids)}"

    # Render the skill template
    rendered = render_template(template.template, skill_params, template.param_names)

    # For tool execution, we return the rendered prompt
    # The agent will then process this as a user message
    result = f"[Skill: {template.skill_id}]\n\n{rendered}"

    logger.info("Skill tool invoked: %s with params: %s", template.skill_id, skill_params)

    return result


async def _skill_list_tool(params: dict[str, Any], config: dict[str, Any]) -> str:
    """List all available skill templates.

    Args:
        params: Empty dict (no parameters)
        config: Agent configuration

    Returns:
        Formatted list of available skill templates
    """
    templates = load_skills()

    if not templates:
        return "No skills available. Create skills in ~/.feinn/skills/ or .feinn/skills/"

    lines = ["Available skill templates:\n"]

    for tmpl in templates:
        if not tmpl.visible_to_user:
            continue

        activators = ", ".join(tmpl.activators)
        hint = f"  params: {tmpl.param_guide}" if tmpl.param_guide else ""
        when = f"\n    when: {tmpl.usage_context}" if tmpl.usage_context else ""
        tools = f"\n    tools: {', '.join(tmpl.allowed_tools)}" if tmpl.allowed_tools else ""
        mode = f"\n    mode: {tmpl.exec_mode}" if tmpl.exec_mode != "direct" else ""

        lines.append(
            f"- **{tmpl.skill_id}** [{activators}]{hint}\n"
            f"  {tmpl.summary}{when}{tools}{mode}"
        )

    return "\n".join(lines)


# Tool definitions
SKILL_TOOL_DEF = ToolDef(
    name="Skill",
    description=(
        "Invoke a named skill template (reusable workflow). "
        "Templates are pre-defined workflows for common tasks like committing code, "
        "reviewing PRs, generating tests, etc. "
        "Use SkillList to see available templates and their activators."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "Skill ID (e.g., 'commit', 'review') or activator (e.g., '/commit')",
            },
            "params": {
                "type": "string",
                "description": "Parameters to pass to the skill (replaces $PARAMS placeholder)",
                "default": "",
            },
        },
        "required": ["id"],
    },
    handler=_skill_tool,
    read_only=False,
    concurrent_safe=False,
)

SKILL_LIST_TOOL_DEF = ToolDef(
    name="SkillList",
    description="List all available skill templates with their IDs, activators, summaries, and usage hints.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=_skill_list_tool,
    read_only=True,
    concurrent_safe=True,
)
