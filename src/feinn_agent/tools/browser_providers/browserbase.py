"""Browserbase cloud browser provider."""

import logging
import os
import uuid
from typing import Dict, Any, Optional
import httpx

from .base import BrowserProvider

logger = logging.getLogger(__name__)


class BrowserbaseProvider(BrowserProvider):
    """Browserbase (https://browserbase.com) cloud browser backend."""

    def provider_name(self) -> str:
        return "Browserbase"

    def is_configured(self) -> bool:
        """Check if Browserbase credentials are available."""
        return bool(self._get_config())

    def _get_config(self) -> Optional[Dict[str, str]]:
        """Get Browserbase configuration."""
        api_key = os.environ.get("BROWSERBASE_API_KEY")
        project_id = os.environ.get("BROWSERBASE_PROJECT_ID")
        if api_key and project_id:
            return {
                "api_key": api_key,
                "project_id": project_id,
                "base_url": os.environ.get("BROWSERBASE_BASE_URL", "https://api.browserbase.com").rstrip("/"),
            }
        return None

    async def create_session(self, task_id: str) -> Dict[str, Any]:
        """Create a Browserbase session."""
        config = self._get_config()
        if not config:
            raise ValueError("Browserbase requires BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID")

        session_name = f"feinn_{task_id}_{uuid.uuid4().hex[:8]}"
        
        # Optional features
        enable_proxies = os.environ.get("BROWSERBASE_PROXIES", "true").lower() != "false"
        enable_advanced_stealth = os.environ.get("BROWSERBASE_ADVANCED_STEALTH", "false").lower() == "true"
        enable_keep_alive = os.environ.get("BROWSERBASE_KEEP_ALIVE", "true").lower() != "false"
        
        session_config = {
            "projectId": config["project_id"],
            "name": session_name,
            "keepAlive": enable_keep_alive,
        }

        if enable_advanced_stealth:
            session_config["stealth"] = "advanced"
        
        if enable_proxies:
            session_config["proxy"] = "residential"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config['base_url']}/sessions",
                headers={
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json",
                },
                json=session_config,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            return {
                "session_name": session_name,
                "session_id": data["id"],
                "cdp_url": data["cdpUrl"],
                "features": {
                    "cloud": True,
                    "proxies": enable_proxies,
                    "advanced_stealth": enable_advanced_stealth,
                    "keep_alive": enable_keep_alive,
                }
            }

    async def execute_command(self, session_id: str, command: str, **kwargs) -> str:
        """Execute browser command using Browserbase."""
        config = self._get_config()
        if not config:
            return "Error: Browserbase not configured"

        # For Browserbase, we'll use the agent-browser CLI with CDP URL
        # This allows us to reuse the same command structure as local mode
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
        """Close Browserbase session."""
        config = self._get_config()
        if not config:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{config['base_url']}/sessions/{session_id}",
                    headers={
                        "Authorization": f"Bearer {config['api_key']}",
                    },
                    timeout=30
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Error closing Browserbase session {session_id}: {e}")
            return False

    def emergency_cleanup(self, session_id: str) -> None:
        """Emergency cleanup for Browserbase session."""
        config = self._get_config()
        if not config:
            return

        try:
            import httpx
            client = httpx.Client()
            response = client.delete(
                f"{config['base_url']}/sessions/{session_id}",
                headers={
                    "Authorization": f"Bearer {config['api_key']}",
                },
                timeout=5
            )
            client.close()
        except Exception:
            pass  # Ignore errors during emergency cleanup
