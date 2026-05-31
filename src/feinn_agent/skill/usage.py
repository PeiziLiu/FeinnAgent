"""Skill usage telemetry — tracks how often skills are used, viewed, and patched.

Persistence:
    Data is stored in ``~/.feinn/skills/.usage.json`` as a JSON sidecar file.

Schema:
    {
      "skills": {
        "<skill_id>": {
          "use_count": int,
          "view_count": int,
          "patch_count": int,
          "created_at": "ISO datetime",
          "last_used_at": "ISO datetime",
          "state": "active" | "stale" | "archived" | "pinned"
        }
      }
    }

Thread safety:
    All mutations acquire a per-instance lock and use atomic writes
    to prevent corruption from concurrent access.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SkillState(str, Enum):
    """Lifecycle state of a skill."""

    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"
    PINNED = "pinned"


@dataclass
class SkillUsage:
    """Usage statistics for a single skill."""

    skill_id: str
    use_count: int = 0
    view_count: int = 0
    patch_count: int = 0
    created_at: str = ""
    last_used_at: str = ""
    state: SkillState = SkillState.ACTIVE


class UsageStore:
    """Thread-safe skill usage telemetry store.

    Usage:
        store = UsageStore()
        store.record_use("commit")
        store.record_view("commit")
        usage = store.get_usage("commit")
        stale = store.list_stale_skills(days=30)
    """

    def __init__(self, usage_path: str | None = None) -> None:
        if usage_path is None:
            usage_path = str(Path.home() / ".feinn" / "skills" / ".usage.json")

        self._path = Path(usage_path)
        self._lock = threading.Lock()
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        """Load usage data from disk."""
        if not self._path.exists():
            return {"skills": {}}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load usage data: %s", e)
            return {"skills": {}}

    def _save(self) -> None:
        """Atomically persist usage data to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._data, indent=2, ensure_ascii=False)

        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._path.parent),
            prefix=f".{self._path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(self._path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _ensure_skill(self, skill_id: str) -> dict[str, Any]:
        """Get or create a skill entry in the data."""
        skills = self._data.setdefault("skills", {})
        if skill_id not in skills:
            now = datetime.now(timezone.utc).isoformat()
            skills[skill_id] = {
                "use_count": 0,
                "view_count": 0,
                "patch_count": 0,
                "created_at": now,
                "last_used_at": now,
                "state": SkillState.ACTIVE.value,
            }
        return skills[skill_id]

    # ── Recording ─────────────────────────────────────────────────────

    def record_use(self, skill_id: str) -> None:
        """Record a skill execution.

        Args:
            skill_id: The skill that was used.
        """
        with self._lock:
            entry = self._ensure_skill(skill_id)
            entry["use_count"] += 1
            entry["last_used_at"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def record_view(self, skill_id: str) -> None:
        """Record a skill view (user inspected the skill).

        Args:
            skill_id: The skill that was viewed.
        """
        with self._lock:
            entry = self._ensure_skill(skill_id)
            entry["view_count"] += 1
            entry["last_used_at"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def record_patch(self, skill_id: str) -> None:
        """Record a skill update/patch.

        Args:
            skill_id: The skill that was patched.
        """
        with self._lock:
            entry = self._ensure_skill(skill_id)
            entry["patch_count"] += 1
            entry["last_used_at"] = datetime.now(timezone.utc).isoformat()
            self._save()

    # ── Query ─────────────────────────────────────────────────────────

    def get_usage(self, skill_id: str) -> SkillUsage | None:
        """Get usage stats for a skill.

        Args:
            skill_id: The skill to query.

        Returns:
            SkillUsage if found, None otherwise.
        """
        skills = self._data.get("skills", {})
        entry = skills.get(skill_id)
        if entry is None:
            return None
        return SkillUsage(
            skill_id=skill_id,
            use_count=entry.get("use_count", 0),
            view_count=entry.get("view_count", 0),
            patch_count=entry.get("patch_count", 0),
            created_at=entry.get("created_at", ""),
            last_used_at=entry.get("last_used_at", ""),
            state=SkillState(entry.get("state", SkillState.ACTIVE.value)),
        )

    def list_stale_skills(self, days: int = 30) -> list[SkillUsage]:
        """List skills that haven't been used in N days.

        Args:
            days: Number of days of inactivity to consider stale.

        Returns:
            List of SkillUsage for stale skills.
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stale: list[SkillUsage] = []

        skills = self._data.get("skills", {})
        for skill_id, entry in skills.items():
            if entry.get("state") in (SkillState.ARCHIVED.value, SkillState.PINNED.value):
                continue

            last_used = entry.get("last_used_at", "")
            if not last_used:
                continue

            try:
                last_dt = datetime.fromisoformat(last_used)
                if last_dt < cutoff:
                    usage = self.get_usage(skill_id)
                    if usage:
                        stale.append(usage)
            except ValueError:
                continue

        return stale

    def set_state(self, skill_id: str, state: SkillState) -> None:
        """Set the lifecycle state of a skill.

        Args:
            skill_id: The skill to update.
            state: New lifecycle state.
        """
        with self._lock:
            entry = self._ensure_skill(skill_id)
            entry["state"] = state.value
            self._save()

    def get_all_usage(self) -> dict[str, Any]:
        """Get all usage data (for diagnostics)."""
        return dict(self._data)
