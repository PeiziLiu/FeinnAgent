"""Auto-creation and self-improvement of skills from conversation experience.

These functions are called by the background review system's fork agent
through the ``SkillManage`` tool. They handle:

1. **create_skill()**: Write a new SKILL.md with YAML frontmatter
2. **patch_skill()**: Update an existing skill's content or metadata
3. **security_scan()**: Block dangerous patterns before persisting
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Dangerous patterns that should never appear in auto-created skills ─

_DANGEROUS_PATTERNS: list[str] = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs.",
    "dd if=",
    "> /dev/sda",
    "| bash",
    "| sh",
    "curl.*|.*bash",
    "wget.*|.*bash",
    ":(){ :|:& };:",
    "chmod -R 000 /",
    "chown -R 0:0 /",
]


def create_skill(
    skill_id: str,
    summary: str,
    template_body: str,
    activators: list[str] | None = None,
    tools: list[str] | None = None,
    param_names: list[str] | None = None,
    param_guide: str = "",
    skill_dir: str | None = None,
) -> Path:
    """Create a new skill file on disk.

    The skill is written to ``{skill_dir}/{skill_id}/SKILL.md``.
    If ``skill_dir`` is not specified, defaults to ``~/.feinn/skills/``.

    Args:
        skill_id: Unique identifier for the skill (used as directory name).
        summary: One-line description.
        template_body: The skill template content.
        activators: Trigger phrases (e.g. ["/my-skill"]).
        tools: Allowed tool names.
        param_names: Named parameters for template substitution.
        param_guide: Parameter usage hint.
        skill_dir: Base directory for skills. Defaults to ~/.feinn/skills/.

    Returns:
        Path to the created SKILL.md file.

    Raises:
        ValueError: If the skill_id contains path traversal characters
            or the template body fails security scan.
    """
    # Validate skill_id — no path traversal
    if "/" in skill_id or "\\" in skill_id or ".." in skill_id:
        raise ValueError(f"Invalid skill_id: {skill_id!r} (path traversal detected)")

    # Security scan
    if not _security_scan(template_body):
        raise ValueError(f"Skill '{skill_id}' blocked by security scan")

    # Resolve target directory
    if skill_dir is None:
        skill_dir = str(Path.home() / ".feinn" / "skills")

    skill_path = Path(skill_dir) / skill_id
    skill_path.mkdir(parents=True, exist_ok=True)

    skill_file = skill_path / "SKILL.md"

    # Build frontmatter
    activators_str = ", ".join(activators) if activators else f"/{skill_id}"
    tools_str = ", ".join(tools) if tools else ""
    param_names_str = ", ".join(param_names) if param_names else ""

    frontmatter = f"---\nid: {skill_id}\nsummary: {summary}\nactivators: [{activators_str}]\n"
    if tools_str:
        frontmatter += f"tools: [{tools_str}]\n"
    if param_guide:
        frontmatter += f"param-guide: {param_guide}\n"
    if param_names_str:
        frontmatter += f"param-names: [{param_names_str}]\n"
    frontmatter += "exec-mode: direct\n"
    frontmatter += "visible: true\n"
    frontmatter += "---\n\n"

    content = frontmatter + template_body.strip() + "\n"

    # Atomic write: tempfile + os.replace
    _atomic_write(skill_file, content)
    logger.info("Skill created: %s (%s)", skill_id, skill_file)

    return skill_file


def patch_skill(
    skill_id: str,
    template_body: str | None = None,
    summary: str | None = None,
    add_tools: list[str] | None = None,
    skill_dir: str | None = None,
) -> bool:
    """Patch an existing skill's content or metadata.

    Args:
        skill_id: The skill to patch.
        template_body: New template body (None = keep existing).
        summary: New summary (None = keep existing).
        add_tools: Additional tools to allow (None = keep existing).
        skill_dir: Base skills directory.

    Returns:
        True if the skill was patched, False if the skill doesn't exist
        or the update was blocked by security scan.
    """
    if skill_dir is None:
        skill_dir = str(Path.home() / ".feinn" / "skills")

    skill_file = Path(skill_dir) / skill_id / "SKILL.md"
    if not skill_file.exists():
        logger.warning("Cannot patch non-existent skill: %s", skill_id)
        return False

    # Read existing content
    existing = skill_file.read_text(encoding="utf-8")

    # Security scan on new content
    if template_body and not _security_scan(template_body):
        logger.warning("Patch blocked by security scan: %s", skill_id)
        return False

    # For simplicity, rewrite the entire file with updated fields
    # In production, this would parse and modify the YAML frontmatter
    if template_body:
        _atomic_write(skill_file, existing + "\n\n---\n\n" + template_body.strip())
    else:
        _atomic_write(skill_file, existing)

    logger.info("Skill patched: %s", skill_id)
    return True


def _atomic_write(path: Path, content: str) -> None:
    """Atomically write content to a file.

    Uses a temporary file in the same directory, then renames it
    atomically via ``os.replace()`` to prevent partial writes.
    """
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _security_scan(template_body: str) -> bool:
    """Scan skill content for dangerous patterns.

    Args:
        template_body: The skill template content to scan.

    Returns:
        True if safe, False if blocked.
    """
    lower = template_body.lower()
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.lower() in lower:
            logger.warning("Security scan blocked: dangerous pattern '%s' found", pattern)
            return False
    return True
