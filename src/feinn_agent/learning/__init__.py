"""FeinnAgent closed-loop learning system.

Enables the agent to autonomously learn from experience:
1. Creates reusable skills from successful workflows
2. Self-improves skills during use (detects and patches outdated patterns)
3. Persists user knowledge automatically (memory nudge)
4. Cross-session recall via full-text search
"""

from .nudge import NudgeConfig, NudgeCounter
from .review import BackgroundReviewer
from .session_search import register_session_search_tool

__all__ = [
    "NudgeConfig",
    "NudgeCounter",
    "BackgroundReviewer",
    "register_session_search_tool",
]
