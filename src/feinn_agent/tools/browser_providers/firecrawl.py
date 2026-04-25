"""Firecrawl cloud browser provider."""

import logging
import os
import uuid
from typing import Dict, Any, Optional
import httpx

from .base import BrowserProvider

logger = logging.getLogger(__name__)


class FirecrawlProvider(BrowserProvider):
    """Firecrawl (https://firecrawl.dev) cloud browser backend."""

    def provider_name(self) -> str:
        return "Firecrawl"

    def is_configured(self) -> bool:
        """Check if Firecrawl API key is available."""
        return bool(os.environ.get("FIRECRAWL_API_KEY"))

    def _get_api_url(self) -> str:
        """Get Firecrawl API URL."""
        return os.environ.get("FIRECRAWL_API_URL", "https://api.firecrawl.dev").rstrip("/")

    async def create_session(self, task_id: str) -> Dict[str, Any]:
        """Create a Firecrawl session."""
        api_key = os.environ.get("FIRECRAWL_API_KEY")
        if not api_key:
            raise ValueError("Firecrawl requires FIRECRAWL_API_KEY")

        session_name = f"feinn_{task_id}_{uuid.uuid4().hex[:8]}"
        
        # Firecrawl doesn't require explicit session creation
        # It uses API keys for authentication
        return {
            "session_name": session_name,
            "session_id": session_name,
            "features": {
                "cloud": True,
                "scraping": True,
            }
        }

    async def execute_command(self, session_id: str, command: str, **kwargs) -> str:
        """Execute browser command using Firecrawl."""
        api_key = os.environ.get("FIRECRAWL_API_KEY")
        if not api_key:
            return "Error: Firecrawl not configured"

        api_url = self._get_api_url()

        if command == "navigate" and "url" in kwargs:
            # Use Firecrawl's scrape endpoint
            url = kwargs["url"]
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{api_url}/v1/scrape",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "url": url,
                        "extractor": "markdown",
                        "includeHtml": True,
                    },
                    timeout=60
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("error", "Scraping failed")
                    return f"Error: {error_msg}"
                
                data = response.json()
                content = data.get("markdown", "")
                
                # Format the response similar to agent-browser
                return f"# Page Snapshot\n\n{content}"
        
        # For other commands, we'll need to use a different approach
        # Firecrawl is primarily for scraping, not interactive browsing
        return f"Error: Command '{command}' not supported by Firecrawl"

    async def close_session(self, session_id: str) -> bool:
        """Close Firecrawl session (no-op for Firecrawl)."""
        # Firecrawl doesn't maintain persistent sessions
        return True

    def emergency_cleanup(self, session_id: str) -> None:
        """Emergency cleanup for Firecrawl session (no-op)."""
        # Firecrawl doesn't require cleanup
        pass
