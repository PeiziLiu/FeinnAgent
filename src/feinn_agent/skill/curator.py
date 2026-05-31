"""Skill lifecycle management — curator.

Automatically manages the skill library to prevent accumulation of
stale or unused skills.

Lifecycle:
    active → stale (unused for N days) → archived (moved to .archive/)

Rules:
    - Built-in skills are never curated.
    - Hub-installed skills are never curated.
    - PINNED skills can be content-updated but never archived/deleted.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from .usage import SkillState, UsageStore

logger = logging.getLogger(__name__)

# Skills that should never be curated (built-in IDs)
_PROTECTED_SKILL_IDS = {
    "commit",
    "review",
    "explain",
    "test",
    "doc",
}

# Subdirectory for archived skills
_ARCHIVE_DIR_NAME = ".archive"


def run_curation(
    skill_dir: str | None = None,
    stale_days: int = 30,
    dry_run: bool = False,
) -> list[str]:
    """Scan skills directory and archive stale skills.

    Args:
        skill_dir: Base skills directory. Defaults to ~/.feinn/skills/.
        stale_days: Days of inactivity before a skill is considered stale.
        dry_run: If True, log actions but don't actually perform them.

    Returns:
        List of action descriptions (for logging/display).
    """
    if skill_dir is None:
        skill_dir = str(Path.home() / ".feinn" / "skills")

    skills_path = Path(skill_dir)
    if not skills_path.exists():
        return []

    usage_store = UsageStore()
    actions: list[str] = []

    # 1. Mark stale skills
    stale_skills = usage_store.list_stale_skills(days=stale_days)
    for usage in stale_skills:
        if usage.skill_id in _PROTECTED_SKILL_IDS:
            continue

        if dry_run:
            actions.append(f"[DRY RUN] Would archive stale skill: {usage.skill_id}")
            logger.info("DRY RUN: Would archive stale skill '%s' (unused %s days)", usage.skill_id, stale_days)
        else:
            if archive_skill(usage.skill_id, skill_dir):
                usage_store.set_state(usage.skill_id, SkillState.ARCHIVED)
                actions.append(f"Archived stale skill: {usage.skill_id}")
                logger.info("Archived stale skill: %s", usage.skill_id)

    if not actions:
        actions.append("Curation complete — no skills needed archiving")

    return actions


def archive_skill(skill_id: str, skill_dir: str) -> bool:
    """Move a skill directory to the .archive/ subdirectory.

    Args:
        skill_id: The skill to archive.
        skill_dir: Base skills directory.

    Returns:
        True if successfully archived, False otherwise.
    """
    skills_path = Path(skill_dir)
    skill_path = skills_path / skill_id
    archive_path = skills_path / _ARCHIVE_DIR_NAME / skill_id

    if not skill_path.exists():
        logger.warning("Cannot archive non-existent skill: %s", skill_id)
        return False

    # Skip if it's a built-in skill (identified by SKILL.md in the parent dir)
    skill_file = skill_path / "SKILL.md"
    if skill_file.exists():
        content = skill_file.read_text(encoding="utf-8")
        if "origin_type: builtin" in content:
            logger.info("Skipping built-in skill: %s", skill_id)
            return False

    try:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(skill_path), str(archive_path))
        return True
    except OSError as e:
        logger.error("Failed to archive skill '%s': %s", skill_id, e)
        return False


def restore_skill(skill_id: str, skill_dir: str | None = None) -> bool:
    """Restore an archived skill back to the active directory.

    Args:
        skill_id: The skill to restore.
        skill_dir: Base skills directory.

    Returns:
        True if successfully restored, False otherwise.
    """
    if skill_dir is None:
        skill_dir = str(Path.home() / ".feinn" / "skills")

    skills_path = Path(skill_dir)
    archive_path = skills_path / _ARCHIVE_DIR_NAME / skill_id
    target_path = skills_path / skill_id

    if not archive_path.exists():
        logger.warning("Cannot restore: archived skill '%s' not found", skill_id)
        return False

    try:
        shutil.move(str(archive_path), str(target_path))
        usage_path = str(skills_path / ".usage.json")
        usage_store = UsageStore(usage_path=usage_path)
        usage_store.set_state(skill_id, SkillState.ACTIVE)
        logger.info("Restored archived skill: %s", skill_id)
        return True
    except OSError as e:
        logger.error("Failed to restore skill '%s': %s", skill_id, e)
        return False


def pin_skill(skill_id: str, skill_dir: str | None = None) -> bool:
    """Mark a skill as pinned (exempt from curation).

    Args:
        skill_id: The skill to pin.
        skill_dir: Base skills directory.

    Returns:
        True if successfully pinned.
    """
    if skill_dir is None:
        skill_dir = str(Path.home() / ".feinn" / "skills")
    usage_path = str(Path(skill_dir) / ".usage.json")
    usage_store = UsageStore(usage_path=usage_path)
    usage_store.set_state(skill_id, SkillState.PINNED)
    logger.info("Pinned skill: %s", skill_id)
    return True
