"""Skill loading: parse markdown files with YAML frontmatter into SkillDef objects."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SkillDef:
    """Skill definition parsed from markdown file.

    Attributes:
        name: Unique skill identifier
        description: Short description of what the skill does
        triggers: List of trigger phrases (e.g., ["/commit", "commit changes"])
        tools: List of allowed tools for this skill
        prompt: Full prompt body (after frontmatter)
        file_path: Source file path
        when_to_use: When the agent should auto-invoke this skill
        argument_hint: Hint for arguments (e.g., "[branch] [description]")
        arguments: List of named argument names
        model: Optional model override
        user_invocable: Whether this skill appears in SkillList
        context: Execution context - "inline" or "fork" (sub-agent)
        source: Source type - "user", "project", or "builtin"
    """

    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    prompt: str = ""
    file_path: str = ""
    when_to_use: str = ""
    argument_hint: str = ""
    arguments: list[str] = field(default_factory=list)
    model: str = ""
    user_invocable: bool = True
    context: str = "inline"  # "inline" or "fork"
    source: str = "user"  # "user", "project", or "builtin"


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


def _parse_skill_file(path: Path, source: str = "user") -> SkillDef | None:
    """Parse a markdown file with ``---`` frontmatter into a SkillDef.

    Frontmatter fields:
        name, description, triggers, tools / allowed-tools,
        when_to_use, argument-hint, arguments, model,
        user-invocable, context

    Args:
        path: Path to the markdown file
        source: Source type ("user", "project", or "builtin")

    Returns:
        Parsed SkillDef or None if invalid
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
    prompt = parts[2].strip()

    fields: dict[str, str] = {}
    for line in frontmatter_raw.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        fields[key.strip().lower()] = val.strip()

    name = fields.get("name", "")
    if not name:
        logger.warning("Skill file %s missing 'name' field", path)
        return None

    # allowed-tools wins over tools if present
    tools_raw = fields.get("allowed-tools", fields.get("tools", ""))
    tools = _parse_list_field(tools_raw) if tools_raw else []

    triggers_raw = fields.get("triggers", "")
    triggers = _parse_list_field(triggers_raw) if triggers_raw else [f"/{name}"]

    arguments_raw = fields.get("arguments", "")
    arguments = _parse_list_field(arguments_raw) if arguments_raw else []

    user_invocable_raw = fields.get("user-invocable", "true")
    user_invocable = user_invocable_raw.lower() not in ("false", "0", "no")

    context = fields.get("context", "inline").strip().lower()
    if context not in ("inline", "fork"):
        context = "inline"

    return SkillDef(
        name=name,
        description=fields.get("description", ""),
        triggers=triggers,
        tools=tools,
        prompt=prompt,
        file_path=str(path),
        when_to_use=fields.get("when_to_use", ""),
        argument_hint=fields.get("argument-hint", ""),
        arguments=arguments,
        model=fields.get("model", ""),
        user_invocable=user_invocable,
        context=context,
        source=source,
    )


# ── Registry of built-in skills (registered by builtin.py) ────────────────

_BUILTIN_SKILLS: list[SkillDef] = []


def register_builtin_skill(skill: SkillDef) -> None:
    """Register a built-in skill.

    Called by builtin.py during module initialization.
    """
    _BUILTIN_SKILLS.append(skill)


# ── Load all skills ────────────────────────────────────────────────────────


def load_skills(include_builtins: bool = True) -> list[SkillDef]:
    """Load all skills from disk and builtins.

    Skills are deduplicated by name with priority:
    project-level > user-level > builtin

    Args:
        include_builtins: Whether to include built-in skills

    Returns:
        List of unique SkillDef objects
    """
    seen: dict[str, SkillDef] = {}

    # Builtins go in first (lowest priority)
    if include_builtins:
        for sk in _BUILTIN_SKILLS:
            seen[sk.name] = sk

    # User-level next, project-level last (highest priority)
    skill_paths = _get_skill_paths()
    for i, skill_dir in enumerate(reversed(skill_paths)):
        src = "project" if i == 0 else "user"
        if not skill_dir.is_dir():
            continue
        for md_file in sorted(skill_dir.glob("*.md")):
            skill = _parse_skill_file(md_file, source=src)
            if skill:
                seen[skill.name] = skill
                logger.debug("Loaded skill: %s from %s", skill.name, md_file)

    return list(seen.values())


def find_skill(query: str) -> SkillDef | None:
    """Find a skill by trigger match.

    Matches the first word of the query against skill triggers.

    Args:
        query: Query string (e.g., "/commit fix the bug")

    Returns:
        Matching SkillDef or None
    """
    query = query.strip()
    if not query:
        return None

    first_word = query.split()[0]
    for skill in load_skills():
        for trigger in skill.triggers:
            if first_word == trigger:
                return skill
            if trigger.startswith(first_word + " "):
                return skill
    return None


def get_skill_by_name(name: str) -> SkillDef | None:
    """Find a skill by exact name match.

    Args:
        name: Skill name

    Returns:
        Matching SkillDef or None
    """
    for skill in load_skills():
        if skill.name == name:
            return skill
    return None


# ── Argument substitution ─────────────────────────────────────────────────


def substitute_arguments(prompt: str, args: str, arg_names: list[str]) -> str:
    """Replace $ARGUMENTS and named placeholders in prompt.

    Replaces:
        - $ARGUMENTS → entire args string
        - $ARG_NAME → corresponding positional argument

    Args:
        prompt: Template prompt with placeholders
        args: Raw argument string from user
        arg_names: List of named argument names

    Returns:
        Rendered prompt with substitutions
    """
    # Always substitute $ARGUMENTS
    result = prompt.replace("$ARGUMENTS", args)

    # Named args: split by whitespace
    arg_values = args.split()
    for i, arg_name in enumerate(arg_names):
        placeholder = f"${arg_name.upper()}"
        value = arg_values[i] if i < len(arg_values) else ""
        result = result.replace(placeholder, value)

    return result
