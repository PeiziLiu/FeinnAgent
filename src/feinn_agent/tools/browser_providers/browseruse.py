"""Browser Use cloud browser provider."""

import logging
import os
import uuid
from typing import Dict, Any, Optional
import httpx

from .base import BrowserProvider

logger = logging.getLogger(__name__)


class BrowserUseProvider(BrowserProvider):
    """Browser Use (https://browser-use.com) cloud browser backend."""

    def provider_name(self) -> str:
        return "Browser Use"

    def is_configured(self) -> bool:
        """Check if Browser Use API key is available."""
        return bool(os.environ.get("BROWSER_USE_API_KEY"))

    async def create_session(self, task_id: str) -> Dict[str, Any]:
        """Create a Browser Use session."""
        api_key = os.environ.get("BROWSER_USE_API_KEY")
        if not api_key:
            raise ValueError("Browser Use requires BROWSER_USE_API_KEY")

        session_name = f"feinn_{task_id}_{uuid.uuid4().hex[:8]}"
        
        # Browser Use API is simpler - just get a CDP URL
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.browser-use.com/v1/sessions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "name": session_name,
                    "headless": True,
                },
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            return {
                "session_name": session_name,
                "session_id": data["sessionId"],
                "cdp_url": data["cdpUrl"],
                "features": {
                    "cloud": True,
                    "headless": True,
                }
            }

    async def execute_command(self, session_id: str, command: str, **kwargs) -> str:
        """Execute browser command using Browser Use."""
        api_key = os.environ.get("BROWSER_USE_API_KEY")
        if not api_key:
            return "Error: Browser Use not configured"

        # Use agent-browser CLI with CDP URL
        import asyncio
        import subprocess
        
        cdp_url = kwargs.get("cdp_url", "")
        if not cdp_url:
            return "Error: CDP URL not available"

        cmd_args = [
            "npx", "agent-browser", 
            "--session", session_id,
            "--cdp", cdp_url,
            command
        ]

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
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace').strip()
                return f"Error: {error_msg}"
            
            return stdout.decode('utf-8', errors='replace').strip()
            
        except asyncio.TimeoutError:
            return "Error: Browser command timed out"
        except Exception as e:
            return f"Error: {str(e)}"

    async def close_session(self, session_id: str) -> bool:
        """Close Browser Use session."""
        api_key = os.environ.get("BROWSER_USE_API_KEY")
        if not api_key:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"https://api.browser-use.com/v1/sessions/{session_id}",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                    },
                    timeout=30
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Error closing Browser Use session {session_id}: {e}")
            return False

    def emergency_cleanup(self, session_id: str) -> None:
        """Emergency cleanup for Browser Use session."""
        api_key = os.environ.get("BROWSER_USE_API_KEY")
        if not api_key:
            return

        try:
            import httpx
            client = httpx.Client()
            response = client.delete(
                f"https://api.browser-use.com/v1/sessions/{session_id}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=5
            )
            client.close()
        except Exception:
            pass  # Ignore errors during emergency cleanup
