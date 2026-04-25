"""FeinnAgent browser automation tools."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import time
from typing import Dict, Any, Optional

from ..types import ToolDef
from .output import truncate_output
from .registry import register
from .browser_providers import (
    BrowserProvider,
    LocalBrowserProvider,
    BrowserbaseProvider,
    BrowserUseProvider,
    FirecrawlProvider,
)

logger = logging.getLogger(__name__)

# Session storage
_active_sessions: Dict[str, Dict[str, Any]] = {}  # task_id -> session info
_session_last_activity: Dict[str, float] = {}     # task_id -> timestamp
_recording_sessions: set = set()                  # task_ids with active recordings

# Cleanup thread state
_cleanup_thread = None
_cleanup_running = False
_cleanup_lock = threading.Lock()
_cleanup_done = False

# Browser session inactivity timeout (seconds)
BROWSER_SESSION_INACTIVITY_TIMEOUT = int(os.environ.get("BROWSER_INACTIVITY_TIMEOUT", "300"))

# Command timeout (seconds)
DEFAULT_COMMAND_TIMEOUT = 30
_cached_command_timeout: Optional[int] = None
_command_timeout_resolved = False

# Provider registry
_PROVIDER_REGISTRY = {
    "local": LocalBrowserProvider,
    "browserbase": BrowserbaseProvider,
    "browser-use": BrowserUseProvider,
    "firecrawl": FirecrawlProvider,
}

# Cached provider
_cached_provider: Optional[BrowserProvider] = None
_provider_resolved = False

# Private URL handling
_allow_private_urls_resolved = False
_cached_allow_private_urls: Optional[bool] = None


# ============================================================================# Configuration# ============================================================================

def _get_command_timeout() -> int:
    """Get configured command timeout."""
    global _cached_command_timeout, _command_timeout_resolved
    if _command_timeout_resolved:
        return _cached_command_timeout or DEFAULT_COMMAND_TIMEOUT

    _command_timeout_resolved = True
    result = DEFAULT_COMMAND_TIMEOUT
    try:
        from ..config import load_config
        config = load_config()
        browser_config = config.get("browser", {})
        val = browser_config.get("command_timeout")
        if val is not None:
            result = max(int(val), 5)  # Floor at 5s
    except Exception as e:
        logger.debug("Could not read command_timeout from config: %s", e)
    _cached_command_timeout = result
    return result

def _allow_private_urls() -> bool:
    """Check if private URLs are allowed."""
    global _cached_allow_private_urls, _allow_private_urls_resolved
    if _allow_private_urls_resolved:
        return _cached_allow_private_urls or False

    _allow_private_urls_resolved = True
    _cached_allow_private_urls = False  # safe default
    try:
        from ..config import load_config
        config = load_config()
        browser_config = config.get("browser", {})
        _cached_allow_private_urls = bool(browser_config.get("allow_private_urls"))
    except Exception as e:
        logger.debug("Could not read allow_private_urls from config: %s", e)
    return _cached_allow_private_urls


def _get_browser_provider() -> BrowserProvider:
    """Get configured browser provider."""
    global _cached_provider, _provider_resolved
    if _provider_resolved:
        return _cached_provider or LocalBrowserProvider()

    _provider_resolved = True
    try:
        from ..config import load_config
        config = load_config()
        browser_config = config.get("browser", {})
        provider_key = browser_config.get("cloud_provider")
        
        if provider_key and provider_key in _PROVIDER_REGISTRY:
            provider_class = _PROVIDER_REGISTRY[provider_key]
            _cached_provider = provider_class()
            if _cached_provider.is_configured():
                return _cached_provider
    except Exception as e:
        logger.debug("Could not read cloud_provider from config: %s", e)

    # Fallback to available providers
    providers = [
        BrowserbaseProvider(),
        BrowserUseProvider(),
        FirecrawlProvider(),
        LocalBrowserProvider(),
    ]
    
    for provider in providers:
        if provider.is_configured():
            _cached_provider = provider
            logger.info(f"Using browser provider: {provider.provider_name()}")
            return provider

    # Default to local provider
    _cached_provider = LocalBrowserProvider()
    logger.info("Using local browser provider")
    return _cached_provider


# ============================================================================# Security# ============================================================================

def _is_private_url(url: str) -> bool:
    """Check if URL points to private/internal network."""
    import ipaddress
    import urllib.parse
    
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Check localhost
        if hostname in ["localhost", "127.0.0.1", "::1"]:
            return True
        
        # Check private IP ranges
        try:
            ip = ipaddress.ip_address(hostname)
            return ip.is_private
        except ValueError:
            # Not an IP address, check if it's a private domain
            private_domains = [
                ".local", ".internal", ".lan", ".home", ".localhost"
            ]
            for domain in private_domains:
                if hostname.endswith(domain):
                    return True
    except Exception:
        pass
    
    return False

def _validate_url(url: str) -> bool:
    """Validate URL for security."""
    if not _allow_private_urls() and _is_private_url(url):
        raise ValueError(f"Access to private URL not allowed: {url}")
    return True


# ============================================================================# Session Management# ============================================================================

def _update_session_activity(task_id: str):
    """Update session activity timestamp."""
    with _cleanup_lock:
        _session_last_activity[task_id] = time.time()

def _cleanup_inactive_sessions():
    """Clean up inactive browser sessions."""
    current_time = time.time()
    sessions_to_cleanup = []
    
    with _cleanup_lock:
        for task_id, last_time in list(_session_last_activity.items()):
            if current_time - last_time > BROWSER_SESSION_INACTIVITY_TIMEOUT:
                sessions_to_cleanup.append(task_id)
    
    for task_id in sessions_to_cleanup:
        try:
            elapsed = int(current_time - _session_last_activity.get(task_id, current_time))
            logger.info(f"Cleaning up inactive session for task: {task_id} (inactive for {elapsed}s)")
            asyncio.run(cleanup_browser(task_id))
            with _cleanup_lock:
                if task_id in _session_last_activity:
                    del _session_last_activity[task_id]
        except Exception as e:
            logger.warning(f"Error cleaning up inactive session {task_id}: {e}")

def _browser_cleanup_thread_worker():
    """Background thread for session cleanup."""
    while _cleanup_running:
        try:
            _cleanup_inactive_sessions()
        except Exception as e:
            logger.warning(f"Cleanup thread error: {e}")
        
        # Sleep in 1-second intervals
        for _ in range(30):
            if not _cleanup_running:
                break
            time.sleep(1)

def _start_browser_cleanup_thread():
    """Start background cleanup thread if not running."""
    global _cleanup_thread, _cleanup_running
    
    with _cleanup_lock:
        if _cleanup_thread is None or not _cleanup_thread.is_alive():
            _cleanup_running = True
            _cleanup_thread = threading.Thread(
                target=_browser_cleanup_thread_worker,
                daemon=True,
                name="browser-cleanup"
            )
            _cleanup_thread.start()
            logger.info(f"Started inactivity cleanup thread (timeout: {BROWSER_SESSION_INACTIVITY_TIMEOUT}s)")

def _stop_browser_cleanup_thread():
    """Stop background cleanup thread."""
    global _cleanup_running
    _cleanup_running = False
    if _cleanup_thread is not None:
        _cleanup_thread.join(timeout=5)


# ============================================================================# Browser Commands# ============================================================================

async def _get_or_create_session(task_id: str) -> Dict[str, Any]:
    """Get existing session or create new one."""
    with _cleanup_lock:
        if task_id in _active_sessions:
            _update_session_activity(task_id)
            return _active_sessions[task_id]
    
    # Create new session
    provider = _get_browser_provider()
    session = await provider.create_session(task_id)
    
    with _cleanup_lock:
        _active_sessions[task_id] = session
        _update_session_activity(task_id)
    
    # Start cleanup thread if not running
    _start_browser_cleanup_thread()
    
    return session

async def _execute_browser_command(task_id: str, command: str, **kwargs) -> str:
    """Execute browser command."""
    session = await _get_or_create_session(task_id)
    provider = _get_browser_provider()
    
    try:
        result = await provider.execute_command(
            session["session_id"],
            command,
            **kwargs
        )
        _update_session_activity(task_id)
        return result
    except Exception as e:
        logger.error(f"Browser command failed: {e}")
        return f"Error: {str(e)}"


# ============================================================================# Tool Handlers# ============================================================================

async def _browser_navigate(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Navigate to a URL in the browser."""
    url = params.get("url", "")
    if not url:
        return "Error: url is required"
    
    task_id = config.get("task_id", f"task_{time.time()}")
    
    try:
        _validate_url(url)
        result = await _execute_browser_command(
            task_id, "navigate", url=url
        )
        return result
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

async def _browser_snapshot(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Get a snapshot of the current page."""
    full = params.get("full", False)
    task_id = config.get("task_id", f"task_{time.time()}")
    
    try:
        result = await _execute_browser_command(
            task_id, "snapshot", full=full
        )
        return truncate_output(result, max_chars=32000)
    except Exception as e:
        return f"Error: {str(e)}"

async def _browser_click(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Click on an element."""
    ref = params.get("ref", "")
    if not ref:
        return "Error: ref is required"
    
    task_id = config.get("task_id", f"task_{time.time()}")
    
    try:
        result = await _execute_browser_command(
            task_id, "click", ref=ref
        )
        return result
    except Exception as e:
        return f"Error: {str(e)}"

async def _browser_type(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Type text into an input field."""
    ref = params.get("ref", "")
    text = params.get("text", "")
    if not ref:
        return "Error: ref is required"
    
    task_id = config.get("task_id", f"task_{time.time()}")
    
    try:
        result = await _execute_browser_command(
            task_id, "type", ref=ref, text=text
        )
        return result
    except Exception as e:
        return f"Error: {str(e)}"

async def _browser_scroll(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Scroll the page."""
    direction = params.get("direction", "down")
    if direction not in ["up", "down"]:
        return "Error: direction must be 'up' or 'down'"
    
    task_id = config.get("task_id", f"task_{time.time()}")
    
    try:
        result = await _execute_browser_command(
            task_id, "scroll", direction=direction
        )
        return result
    except Exception as e:
        return f"Error: {str(e)}"

async def _browser_back(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Navigate back to previous page."""
    task_id = config.get("task_id", f"task_{time.time()}")
    
    try:
        result = await _execute_browser_command(
            task_id, "back"
        )
        return result
    except Exception as e:
        return f"Error: {str(e)}"

async def _browser_press(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Press a keyboard key."""
    key = params.get("key", "")
    if not key:
        return "Error: key is required"
    
    task_id = config.get("task_id", f"task_{time.time()}")
    
    try:
        result = await _execute_browser_command(
            task_id, "press", key=key
        )
        return result
    except Exception as e:
        return f"Error: {str(e)}"

async def _browser_get_images(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Get list of images on current page."""
    task_id = config.get("task_id", f"task_{time.time()}")
    
    try:
        result = await _execute_browser_command(
            task_id, "get_images"
        )
        return result
    except Exception as e:
        return f"Error: {str(e)}"

async def cleanup_browser(task_id: str) -> bool:
    """Clean up browser session."""
    session = _active_sessions.get(task_id)
    if not session:
        return False
    
    provider = _get_browser_provider()
    try:
        success = await provider.close_session(session["session_id"])
        if success:
            with _cleanup_lock:
                if task_id in _active_sessions:
                    del _active_sessions[task_id]
                if task_id in _session_last_activity:
                    del _session_last_activity[task_id]
                if task_id in _recording_sessions:
                    _recording_sessions.remove(task_id)
        return success
    except Exception as e:
        logger.warning(f"Error cleaning up browser session {task_id}: {e}")
        return False

async def cleanup_all_browsers() -> None:
    """Clean up all browser sessions."""
    task_ids = list(_active_sessions.keys())
    for task_id in task_ids:
        await cleanup_browser(task_id)


def emergency_cleanup_all_sessions():
    """Emergency cleanup of all sessions."""
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    
    if not _active_sessions:
        return
    
    logger.info(f"Emergency cleanup: closing {len(_active_sessions)} active session(s)...")
    
    try:
        asyncio.run(cleanup_all_browsers())
    except Exception as e:
        logger.error(f"Emergency cleanup error: {e}")
    finally:
        with _cleanup_lock:
            _active_sessions.clear()
            _session_last_activity.clear()
            _recording_sessions.clear()


# Register cleanup at exit
import atexit
atexit.register(emergency_cleanup_all_sessions)
atexit.register(_stop_browser_cleanup_thread)


# ============================================================================# Tool Definitions# ============================================================================

# Browser navigate tool
register(
    ToolDef(
        name="browser_navigate",
        description="Navigate to a URL in the browser. Initializes the session and loads the page. Must be called before other browser tools.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to navigate to (e.g., 'https://example.com')"
                }
            },
            "required": ["url"]
        },
        handler=_browser_navigate,
        read_only=False,
        concurrent_safe=True,
    )
)

# Browser snapshot tool
register(
    ToolDef(
        name="browser_snapshot",
        description="Get a text-based snapshot of the current page's accessibility tree. Returns interactive elements with ref IDs for browser_click and browser_type.",
        input_schema={
            "type": "object",
            "properties": {
                "full": {
                    "type": "boolean",
                    "description": "If true, returns complete page content. If false (default), returns compact view with interactive elements only.",
                    "default": False
                }
            }
        },
        handler=_browser_snapshot,
        read_only=True,
        concurrent_safe=True,
    )
)

# Browser click tool
register(
    ToolDef(
        name="browser_click",
        description="Click on an element identified by its ref ID from the snapshot (e.g., '@e5').",
        input_schema={
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": "The element reference from the snapshot (e.g., '@e5', '@e12')"
                }
            },
            "required": ["ref"]
        },
        handler=_browser_click,
        read_only=False,
        concurrent_safe=True,
    )
)

# Browser type tool
register(
    ToolDef(
        name="browser_type",
        description="Type text into an input field identified by its ref ID.",
        input_schema={
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": "The element reference from the snapshot (e.g., '@e3')"
                },
                "text": {
                    "type": "string",
                    "description": "The text to type into the field"
                }
            },
            "required": ["ref", "text"]
        },
        handler=_browser_type,
        read_only=False,
        concurrent_safe=True,
    )
)

# Browser scroll tool
register(
    ToolDef(
        name="browser_scroll",
        description="Scroll the page in a direction to reveal more content.",
        input_schema={
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Direction to scroll"
                }
            },
            "required": ["direction"]
        },
        handler=_browser_scroll,
        read_only=False,
        concurrent_safe=True,
    )
)

# Browser back tool
register(
    ToolDef(
        name="browser_back",
        description="Navigate back to the previous page in browser history.",
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        },
        handler=_browser_back,
        read_only=False,
        concurrent_safe=True,
    )
)

# Browser press tool
register(
    ToolDef(
        name="browser_press",
        description="Press a keyboard key. Useful for submitting forms (Enter), navigating (Tab), or keyboard shortcuts.",
        input_schema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key to press (e.g., 'Enter', 'Tab', 'Escape', 'ArrowDown')"
                }
            },
            "required": ["key"]
        },
        handler=_browser_press,
        read_only=False,
        concurrent_safe=True,
    )
)

# Browser get images tool
register(
    ToolDef(
        name="browser_get_images",
        description="Get a list of all images on the current page with their URLs and alt text.",
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        },
        handler=_browser_get_images,
        read_only=True,
        concurrent_safe=True,
    )
)
