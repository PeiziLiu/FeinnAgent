"""Nudge system — periodic triggers for background review.

Two independent counters drive the learning loop:
1. Memory Nudge: counts user turns → triggers memory review (save user facts)
2. Skill Nudge: counts tool iterations → triggers skill review (create/patch skills)

Counters are reset when the agent actively performs the relevant action
(e.g. using skill_manage suppresses the skill nudge).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NudgeConfig:
    """Configuration for the nudge system.

    Attributes:
        memory_nudge_interval: User turns between memory review triggers.
            Set to 0 to disable memory nudge.
        skill_nudge_interval: Tool iterations between skill review triggers.
            Set to 0 to disable skill nudge.
        enabled: Master switch for all nudges.
    """

    memory_nudge_interval: int = 10
    skill_nudge_interval: int = 10
    enabled: bool = True


class NudgeCounter:
    """Tracks nudge state for a conversation session.

    On session resume, counters are reconstructed from history
    to avoid an immediate trigger.

    Usage:
        counter = NudgeCounter(config)
        counter.record_turn()
        counter.record_tool_iterations(3)

        if counter.should_review_memory:
            # spawn background memory review
            counter.reset_memory_nudge()

        if counter.should_review_skill:
            # spawn background skill review
            counter.reset_skill_nudge()
    """

    def __init__(self, config: NudgeConfig | None = None) -> None:
        self.config = config or NudgeConfig()
        self._turns_since_memory: int = 0
        self._iters_since_skill: int = 0

    # ── Query ─────────────────────────────────────────────────────────

    @property
    def should_review_memory(self) -> bool:
        """True if memory nudge threshold has been reached."""
        if not self.config.enabled:
            return False
        if self.config.memory_nudge_interval <= 0:
            return False
        return self._turns_since_memory >= self.config.memory_nudge_interval

    @property
    def should_review_skill(self) -> bool:
        """True if skill nudge threshold has been reached."""
        if not self.config.enabled:
            return False
        if self.config.skill_nudge_interval <= 0:
            return False
        return self._iters_since_skill >= self.config.skill_nudge_interval

    @property
    def should_review_any(self) -> bool:
        """True if any nudge threshold has been reached."""
        return self.should_review_memory or self.should_review_skill

    # ── Recording ─────────────────────────────────────────────────────

    def record_turn(self) -> None:
        """Increment after each user turn."""
        self._turns_since_memory += 1

    def record_tool_iterations(self, count: int) -> None:
        """Increment after tool calls in a turn.

        Args:
            count: Number of tool calls made this iteration.
        """
        self._iters_since_skill += count

    # ── Reset ──────────────────────────────────────────────────────────

    def reset_memory_nudge(self) -> None:
        """Reset memory counter (called after review)."""
        self._turns_since_memory = 0

    def reset_skill_nudge(self) -> None:
        """Reset skill counter (called after review or when skill_manage used)."""
        self._iters_since_skill = 0

    def reset_all(self) -> None:
        """Reset both counters."""
        self._turns_since_memory = 0
        self._iters_since_skill = 0

    # ── Hydration ─────────────────────────────────────────────────────

    def hydrate_from_history(self, prior_turns: int, prior_tool_iters: int) -> None:
        """Reconstruct counters from prior session history.

        This prevents an immediate nudge when resuming a long session.
        The counter is set to ``prior_count % interval`` so the next
        nudge fires after the expected number of additional turns/iters.
        """
        if self.config.memory_nudge_interval > 0:
            self._turns_since_memory = prior_turns % self.config.memory_nudge_interval
        if self.config.skill_nudge_interval > 0:
            self._iters_since_skill = prior_tool_iters % self.config.skill_nudge_interval

    def suppress_skill_nudge(self) -> None:
        """Suppress skill nudge when agent is already managing skills.

        Called when the agent uses ``SkillManage`` — active management
        means the nudge is unnecessary this cycle.
        """
        self._iters_since_skill = 0
