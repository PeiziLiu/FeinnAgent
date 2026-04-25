"""Abstract base class for browser providers."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BrowserProvider(ABC):
    """Interface for browser backends (local, cloud)."""

    @abstractmethod
    def provider_name(self) -> str:
        """Short, human-readable name shown in logs and diagnostics."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when all required env vars / credentials are present.

        Called at tool-registration time to gate availability.
        Must be cheap — no network calls.
        """

    @abstractmethod
    async def create_session(self, task_id: str) -> Dict[str, Any]:
        """Create a browser session and return session metadata.

        Must return a dict with at least:
            {
                "session_name": str,   # unique name for session
                "session_id": str,     # provider session ID
                "features": dict,      # feature flags that were enabled
            }
        """

    @abstractmethod
    async def execute_command(self, session_id: str, command: str, **kwargs) -> str:
        """Execute a browser command and return the result.

        Args:
            session_id: The session ID to use
            command: The command to execute
            **kwargs: Additional command parameters

        Returns:
            The result of the command
        """

    @abstractmethod
    async def close_session(self, session_id: str) -> bool:
        """Release / terminate a session by its provider session ID.

        Returns True on success, False on failure.
        Should not raise.
        """

    @abstractmethod
    def emergency_cleanup(self, session_id: str) -> None:
        """Best-effort session teardown during process exit.

        Called from atexit / signal handlers.
        Must tolerate missing credentials, network errors, etc.
        """
