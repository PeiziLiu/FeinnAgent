"""Skill tools: Skill and SkillList for invoking and discovering skill templates."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..skill.loader import (
    find_skill,
    get_skill_by_name,
    load_skills,
    render_template,
)
from ..skill.usage import SkillState, UsageStore
from ..types import ToolDef

logger = logging.getLogger(__name__)

_usage_store: UsageStore | None = None


def _get_usage_store() -> UsageStore:
    global _usage_store
    if _usage_store is None:
        _usage_store = UsageStore()
    return _usage_store


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

    # Record usage telemetry
    try:
        _get_usage_store().record_use(template.skill_id)
    except Exception:
        logger.debug("Failed to record skill usage (non-fatal)", exc_info=True)

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

    # Record view telemetry for all visible skills
    try:
        store = _get_usage_store()
        for t in templates:
            if t.visible_to_user:
                store.record_view(t.skill_id)
    except Exception:
        logger.debug("Failed to record skill view (non-fatal)", exc_info=True)

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

        lines.append(f"- **{tmpl.skill_id}** [{activators}]{hint}\n  {tmpl.summary}{when}{tools}{mode}")

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

# ── SkillManage tool ─────────────────────────────────────────────────


async def _skill_manage_tool(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Create, patch, or delete skills.

    Args:
        params: Tool parameters
            - action: "create", "patch", or "delete"
            - id: Skill identifier
            - summary: One-line description (for create)
            - template: Skill template body (for create/patch)
            - activators: Trigger phrases (for create)
            - tools: Allowed tool names (for create)
            - param_names: Template parameter names (for create)
            - param_guide: Parameter usage hint (for create)
        config: Agent configuration

    Returns:
        Result message
    """
    action = params.get("action", "").strip().lower()
    skill_id = params.get("id", "").strip()

    if not action:
        return "Error: 'action' is required (create, patch, or delete)"
    if not skill_id:
        return "Error: 'id' is required"

    if action == "create":
        from ..skill.auto_create import create_skill

        try:
            skill_file = create_skill(
                skill_id=skill_id,
                summary=params.get("summary", f"Auto-created skill: {skill_id}"),
                template_body=params.get("template", ""),
                activators=params.get("activators"),
                tools=params.get("tools"),
                param_names=params.get("param_names"),
                param_guide=params.get("param_guide", ""),
            )
            try:
                _get_usage_store().record_use(skill_id)
            except Exception:
                pass
            return f"Created skill: {skill_id} ({skill_file})"
        except ValueError as e:
            return f"Error creating skill: {e}"

    elif action == "patch":
        from ..skill.auto_create import patch_skill

        success = patch_skill(
            skill_id=skill_id,
            template_body=params.get("template"),
            summary=params.get("summary"),
            add_tools=params.get("tools"),
        )
        if success:
            try:
                _get_usage_store().record_patch(skill_id)
            except Exception:
                pass
            return f"Patched skill: {skill_id}"
        return f"Skill not found or patch blocked: {skill_id}"

    elif action == "delete":
        from ..skill.curator import archive_skill

        skill_dir = str(Path.home() / ".feinn" / "skills") if not config else None
        success = archive_skill(skill_id, str(Path.home() / ".feinn" / "skills"))
        if success:
            try:
                _get_usage_store().set_state(skill_id, SkillState.ARCHIVED)
            except Exception:
                pass
            return f"Deleted (archived) skill: {skill_id}"
        return f"Skill not found or deletion failed: {skill_id}"

    return f"Error: unknown action '{action}' (use create, patch, or delete)"


SKILL_MANAGE_TOOL_DEF = ToolDef(
    name="SkillManage",
    description=(
        "Create, patch, or delete skills. Use 'create' to make new reusable templates, "
        "'patch' to update an existing skill, or 'delete' to remove one. "
        "Skill templates are stored as SKILL.md files with YAML frontmatter."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "patch", "delete"],
                "description": "Operation to perform",
            },
            "id": {"type": "string", "description": "Skill identifier"},
            "summary": {"type": "string", "description": "One-line description (for create)"},
            "template": {"type": "string", "description": "Skill template body (for create/patch)"},
            "activators": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Trigger phrases like ['/my-skill']",
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Allowed tool names",
            },
            "param_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Template parameter names",
            },
            "param_guide": {
                "type": "string",
                "description": "Parameter usage hint",
            },
        },
        "required": ["action", "id"],
    },
    handler=_skill_manage_tool,
    read_only=False,
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
