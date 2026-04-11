"""Skill loading: parse markdown files with YAML frontmatter into SkillDef objects."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SkillTemplate:
    """Reusable workflow template defined in markdown with YAML frontmatter.

    Attributes:
        skill_id: Unique identifier for the template
        summary: Brief description of the workflow
        activators: Trigger phrases that invoke this skill (e.g., ["/commit"])
        allowed_tools: Tools this skill can use (empty = all tools)
        template: The prompt template body (after frontmatter)
        origin: Path to source file
        usage_context: When the agent should suggest this skill
        param_guide: Hint for parameters (e.g., "[branch] [message]")
        param_names: Named parameter placeholders
        preferred_model: Optional model override
        visible_to_user: Whether shown in skill listings
        exec_mode: "direct" (current context) or "isolated" (sub-agent)
        origin_type: "builtin", "user", or "workspace"
    """

    skill_id: str
    summary: str
    activators: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    template: str = ""
    origin: str = ""
    usage_context: str = ""
    param_guide: str = ""
    param_names: list[str] = field(default_factory=list)
    preferred_model: str = ""
    visible_to_user: bool = True
    exec_mode: str = "direct"  # "direct" or "isolated"
    origin_type: str = "user"  # "builtin", "user", or "workspace"


# ── Directory paths ────────────────────────────────────────────────────────


def _get_skill_paths() -> list[Path]:
    """Return skill directories in priority order (project > user)."""
    return [
        Path.cwd() / ".feinn" / "skills",  # project-level (highest priority)
        Path.home() / ".feinn" / "skills",  # user-level
    ]


# ── List field parser ──────────────────────────────────────────────────────


def _parse_list_field(value: str) -> list[str]:
    """Parse YAML-like list: ``[a, b, c]`` or ``"a, b, c"``.

    Args:
        value: Raw string value from frontmatter

    Returns:
        List of parsed string items
    """
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [
        item.strip().strip('"').strip("'")
        for item in value.split(",")
        if item.strip()
    ]


# ── Single-file parser ─────────────────────────────────────────────────────


def _parse_skill_file(path: Path, origin_type: str = "user") -> SkillTemplate | None:
    """Parse a markdown file with ``---`` frontmatter into a SkillTemplate.

    Frontmatter fields:
        id, summary, activators, tools,
        usage-context, param-guide, param-names, model,
        visible, exec-mode

    Args:
        path: Path to the markdown file
        origin_type: Source type ("user", "workspace", or "builtin")

    Returns:
        Parsed SkillTemplate or None if invalid
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to read skill file %s: %s", path, e)
        return None

    if not text.startswith("---"):
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter_raw = parts[1].strip()
    template_body = parts[2].strip()

    fields: dict[str, str] = {}
    for line in frontmatter_raw.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        fields[key.strip().lower()] = val.strip()

    # Support both old 'name' and new 'id' field
    skill_id = fields.get("id", fields.get("name", ""))
    if not skill_id:
        logger.warning("Skill file %s missing 'id' or 'name' field", path)
        return None

    # Parse tools list
    tools_raw = fields.get("tools", "")
    allowed_tools = _parse_list_field(tools_raw) if tools_raw else []

    # Parse activators (triggers)
    activators_raw = fields.get("activators", fields.get("triggers", ""))
    activators = _parse_list_field(activators_raw) if activators_raw else [f"/{skill_id}"]

    # Parse parameter names
    param_names_raw = fields.get("param-names", fields.get("arguments", ""))
    param_names = _parse_list_field(param_names_raw) if param_names_raw else []

    # Parse visibility flag
    visible_raw = fields.get("visible", fields.get("user-invocable", "true"))
    visible_to_user = visible_raw.lower() not in ("false", "0", "no")

    # Parse execution mode
    exec_mode = fields.get("exec-mode", fields.get("context", "direct")).strip().lower()
    if exec_mode not in ("direct", "isolated"):
        exec_mode = "direct"
    # Map old values to new ones
    if exec_mode == "inline":
        exec_mode = "direct"
    elif exec_mode == "fork":
        exec_mode = "isolated"

    return SkillTemplate(
        skill_id=skill_id,
        summary=fields.get("summary", fields.get("description", "")),
        activators=activators,
        allowed_tools=allowed_tools,
        template=template_body,
        origin=str(path),
        usage_context=fields.get("usage-context", fields.get("when_to_use", "")),
        param_guide=fields.get("param-guide", fields.get("argument-hint", "")),
        param_names=param_names,
        preferred_model=fields.get("model", ""),
        visible_to_user=visible_to_user,
        exec_mode=exec_mode,
        origin_type=origin_type,
    )


# ── Registry of built-in skills (registered by builtin.py) ────────────────

_BUILTIN_TEMPLATES: list[SkillTemplate] = []


def register_builtin_template(template: SkillTemplate) -> None:
    """Register a built-in skill template.

    Called by builtin.py during module initialization.
    """
    _BUILTIN_TEMPLATES.append(template)


# ── Load all skills ────────────────────────────────────────────────────────


def load_skills(include_builtins: bool = True) -> list[SkillTemplate]:
    """Load all skill templates from disk and builtins.

    Templates are deduplicated by skill_id with priority:
    workspace-level > user-level > builtin

    Args:
        include_builtins: Whether to include built-in templates

    Returns:
        List of unique SkillTemplate objects
    """
    seen: dict[str, SkillTemplate] = {}

    # Builtins go in first (lowest priority)
    if include_builtins:
        for tmpl in _BUILTIN_TEMPLATES:
            seen[tmpl.skill_id] = tmpl

    # User-level next, workspace-level last (highest priority)
    skill_paths = _get_skill_paths()
    for i, skill_dir in enumerate(reversed(skill_paths)):
        src = "workspace" if i == 0 else "user"
        if not skill_dir.is_dir():
            continue
        for md_file in sorted(skill_dir.glob("*.md")):
            template = _parse_skill_file(md_file, origin_type=src)
            if template:
                seen[template.skill_id] = template
                logger.debug("Loaded skill template: %s from %s", template.skill_id, md_file)

    return list(seen.values())


def find_skill(query: str) -> SkillTemplate | None:
    """Find a skill template by activator match.

    Matches the first word of the query against template activators.

    Args:
        query: Query string (e.g., "/commit fix the bug")

    Returns:
        Matching SkillTemplate or None
    """
    query = query.strip()
    if not query:
        return None

    first_word = query.split()[0]
    for template in load_skills():
        for activator in template.activators:
            if first_word == activator:
                return template
            if activator.startswith(first_word + " "):
                return template
    return None


def get_skill_by_name(skill_id: str) -> SkillTemplate | None:
    """Find a skill template by exact skill_id match.

    Args:
        skill_id: Skill identifier

    Returns:
        Matching SkillTemplate or None
    """
    for template in load_skills():
        if template.skill_id == skill_id:
            return template
    return None


# ── Parameter substitution ─────────────────────────────────────────────────


def render_template(template: str, params: str, param_names: list[str]) -> str:
    """Replace $PARAMS and named placeholders in template.

    Replaces:
        - $PARAMS → entire params string
        - $PARAM_NAME → corresponding positional parameter

    Args:
        template: Template string with placeholders
        params: Raw parameter string from user
        param_names: List of named parameter names

    Returns:
        Rendered template with substitutions
    """
    # Always substitute $PARAMS (backward compat with $ARGUMENTS)
    result = template.replace("$PARAMS", params).replace("$ARGUMENTS", params)

    # Named params: split by whitespace
    param_values = params.split()
    for i, param_name in enumerate(param_names):
        placeholder = f"${param_name.upper()}"
        value = param_values[i] if i < len(param_values) else ""
        result = result.replace(placeholder, value)

    return result
