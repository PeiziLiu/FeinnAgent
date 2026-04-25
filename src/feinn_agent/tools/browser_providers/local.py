"""Local browser provider using agent-browser CLI."""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path

from .base import BrowserProvider

logger = logging.getLogger(__name__)


class LocalBrowserProvider(BrowserProvider):
    """Local browser provider using agent-browser CLI."""

    def provider_name(self) -> str:
        return "local"

    def is_configured(self) -> bool:
        """Check if agent-browser is available."""
        try:
            result = subprocess.run(
                ["npx", "agent-browser", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    async def create_session(self, task_id: str) -> Dict[str, Any]:
        """Create a local browser session."""
        session_name = f"feinn_{task_id}"
        return {
            "session_name": session_name,
            "session_id": session_name,
            "features": {
                "local": True,
                "headless": True
            }
        }

    async def execute_command(self, session_id: str, command: str, **kwargs) -> str:
        """Execute browser command using agent-browser CLI."""
        cmd_args = ["npx", "agent-browser", "--session", session_id, command]
        
        # Add command-specific arguments
        if command == "navigate" and "url" in kwargs:
            cmd_args.append(kwargs["url"])
        elif command == "snapshot" and "full" in kwargs:
            if kwargs["full"]:
                cmd_args.append("--full")
        elif command == "click" and "ref" in kwargs:
            cmd_args.append(kwargs["ref"])
        elif command == "type" and "ref" in kwargs and "text" in kwargs:
            cmd_args.extend([kwargs["ref"], kwargs["text"]])
        elif command == "scroll" and "direction" in kwargs:
            cmd_args.append(kwargs["direction"])
        elif command == "press" and "key" in kwargs:
            cmd_args.append(kwargs["key"])

        try:
            # Set a safe PATH for environments with minimal PATH
            env = os.environ.copy()
            env["PATH"] = self._get_safe_path()
            
            # Create temporary directory for socket (fixes macOS socket path issue)
            temp_dir = self._socket_safe_tmpdir()
            env["TMPDIR"] = temp_dir

            # Execute the command
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace').strip()
                logger.error(f"Browser command failed: {error_msg}")
                return f"Error: {error_msg}"
            
            return stdout.decode('utf-8', errors='replace').strip()
            
        except asyncio.TimeoutError:
            return "Error: Browser command timed out"
        except Exception as e:
            logger.error(f"Browser command error: {e}")
            return f"Error: {str(e)}"

    async def close_session(self, session_id: str) -> bool:
        """Close local browser session."""
        try:
            process = await asyncio.create_subprocess_exec(
                "npx", "agent-browser", "--session", session_id, "close",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except Exception as e:
            logger.warning(f"Error closing session {session_id}: {e}")
            return False

    def emergency_cleanup(self, session_id: str) -> None:
        """Emergency cleanup for local session."""
        try:
            subprocess.run(
                ["npx", "agent-browser", "--session", session_id, "close"],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass  # Ignore errors during emergency cleanup

    def _get_safe_path(self) -> str:
        """Return a safe PATH including common directories."""
        sane_path = (
            "/opt/homebrew/bin:/opt/homebrew/sbin:"
            "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        )
        current_path = os.environ.get("PATH", "")
        return f"{sane_path}:{current_path}"

    def _socket_safe_tmpdir(self) -> str:
        """Return a short temp directory path suitable for Unix domain sockets."""
        if sys.platform == "darwin":
            return "/tmp"
        return tempfile.gettempdir()
