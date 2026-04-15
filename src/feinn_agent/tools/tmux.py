"""Tmux integration — persistent terminal sessions for long-running commands.

Gives the agent direct control over tmux sessions: create panes, send
commands, read output, and manage layouts.  Tools are only registered when
a tmux-compatible binary is detected on the system.

Uses ``asyncio.to_thread()`` to bridge synchronous subprocess calls into
FeinnAgent's async handler interface.

Harness Engineering patterns:
* **Guides**: ``_safe()`` sanitizes all tmux identifiers to prevent injection.
* **Sensors**: ``TmuxCapture`` lets the agent observe long-running output.
* **Guardrails**: read-only tools are marked so the permission system can
  auto-approve them.

Reference: CheetahClaws tmux_tools.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any

from ..types import ToolDef
from .registry import register

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _find_tmux() -> str | None:
    """Locate a tmux-compatible binary."""
    found = shutil.which("tmux") or shutil.which("psmux")
    if found:
        return found
    if sys.platform == "win32":
        custom = os.environ.get("FEINN_PSMUX_PATH")
        if custom and os.path.isfile(custom):
            return custom
        candidates = [
            os.path.expanduser(r"~\.cargo\bin\psmux.exe"),
            os.path.expanduser(r"~\.cargo\bin\tmux.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
    return None


_TMUX_BIN: str | None = _find_tmux()

# Sanitize: only alphanumerics, underscores, hyphens, dots, colons
_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.:-]+$")
_RESIZE_FLAGS = {"up": "-U", "down": "-D", "left": "-L", "right": "-R"}
_READ_ONLY_TOOLS = frozenset((
    "TmuxListSessions", "TmuxCapture", "TmuxListPanes", "TmuxListWindows",
))


def tmux_available() -> bool:
    """Return True if a tmux-compatible binary exists on the system."""
    return _TMUX_BIN is not None


def _safe(value: str) -> str:
    """Sanitize a tmux target / session name to prevent shell injection."""
    if not value or not _SAFE_NAME.match(value):
        raise ValueError(f"Invalid tmux identifier: {value!r}")
    return value


def _t(params: dict[str, Any], key: str = "target") -> str:
    """Build a ``-t`` flag from *params*, or empty string if absent."""
    val = params.get(key, "")
    return f" -t {_safe(val)}" if val else ""


# ---------------------------------------------------------------------------
# Low-level runner (sync — called via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _run_sync(cmd: str, timeout: int = 10) -> str:
    """Execute a tmux command synchronously and return output."""
    if _TMUX_BIN is None:
        return "Error: tmux binary not found"

    try:
        if cmd.startswith("tmux "):
            cmd = f'"{_TMUX_BIN}" {cmd[5:]}'
        env = dict(os.environ)
        env.pop("TMUX", None)
        env.pop("PSMUX_SESSION", None)
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, env=env,
        )
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()
        if r.returncode != 0 and stderr:
            return f"FAILED (exit {r.returncode}): {stderr}"
        out = (stdout + ("\n" + stderr if stderr else "")).strip()
        return out if out else "(ok)"
    except subprocess.TimeoutExpired:
        return "Error: tmux command timed out"
    except Exception as e:
        return f"Error: {e}"


async def _run(cmd: str, timeout: int = 10) -> str:
    """Async bridge: run a tmux command via ``asyncio.to_thread``."""
    return await asyncio.to_thread(_run_sync, cmd, timeout)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def _tmux_list_sessions(params: dict[str, Any], config: dict[str, Any]) -> str:
    return await _run("tmux list-sessions")


async def _tmux_new_session(params: dict[str, Any], config: dict[str, Any]) -> str:
    name = _safe(params.get("session_name", "feinn"))
    detach = "-d" if params.get("detached", True) else ""
    cmd = params.get("command", "")
    shell_part = f" {shlex.quote(cmd)}" if cmd else ""
    return await _run(f"tmux new-session {detach} -s {name}{shell_part}")


async def _tmux_split_window(params: dict[str, Any], config: dict[str, Any]) -> str:
    direction = "-v" if params.get("direction", "vertical") == "vertical" else "-h"
    cmd = params.get("command", "")
    shell_part = f" {shlex.quote(cmd)}" if cmd else ""
    return await _run(f"tmux split-window {direction}{_t(params)}{shell_part}")


async def _tmux_send_keys(params: dict[str, Any], config: dict[str, Any]) -> str:
    keys = params.get("keys", "")
    if not keys:
        return "Error: keys is required"
    enter = " Enter" if params.get("press_enter", True) else ""
    safe_keys = keys.replace("'", "'\\''")
    return await _run(f"tmux send-keys{_t(params)} '{safe_keys}'{enter}")


async def _tmux_capture_pane(params: dict[str, Any], config: dict[str, Any]) -> str:
    lines = int(params.get("lines", 50))
    return await _run(f"tmux capture-pane{_t(params)} -p -S -{lines}")


async def _tmux_list_panes(params: dict[str, Any], config: dict[str, Any]) -> str:
    fmt = (
        "#{{pane_index}}: #{{pane_current_command}} "
        "[#{{pane_width}}x#{{pane_height}}] "
        "#{{?pane_active,(active),}}"
    )
    return await _run(f"tmux list-panes{_t(params)} -F '{fmt}'")


async def _tmux_select_pane(params: dict[str, Any], config: dict[str, Any]) -> str:
    target = params.get("target", "")
    if not target:
        return "Error: target is required"
    return await _run(f"tmux select-pane -t {_safe(target)}")


async def _tmux_kill_pane(params: dict[str, Any], config: dict[str, Any]) -> str:
    return await _run(f"tmux kill-pane{_t(params)}")


async def _tmux_new_window(params: dict[str, Any], config: dict[str, Any]) -> str:
    t_flag = _t(params, "target_session")
    name = params.get("window_name", "")
    n_flag = f" -n {_safe(name)}" if name else ""
    cmd = params.get("command", "")
    shell_part = f" {shlex.quote(cmd)}" if cmd else ""
    return await _run(f"tmux new-window{t_flag}{n_flag}{shell_part}")


async def _tmux_list_windows(params: dict[str, Any], config: dict[str, Any]) -> str:
    fmt = (
        "#{{window_index}}: #{{window_name}} "
        "[#{{window_width}}x#{{window_height}}] "
        "#{{?window_active,(active),}}"
    )
    return await _run(
        f"tmux list-windows{_t(params, 'target_session')} -F '{fmt}'"
    )


async def _tmux_resize_pane(params: dict[str, Any], config: dict[str, Any]) -> str:
    direction = params.get("direction", "down")
    amount = int(params.get("amount", 10))
    d_flag = _RESIZE_FLAGS.get(direction, "-D")
    return await _run(f"tmux resize-pane{_t(params)} {d_flag} {amount}")


# ---------------------------------------------------------------------------
# Schema + registration
# ---------------------------------------------------------------------------

_TMUX_TOOLS: list[dict[str, Any]] = [
    {
        "name": "TmuxListSessions",
        "description": "List all active tmux sessions.",
        "handler": _tmux_list_sessions,
        "schema": {"type": "object", "properties": {}},
    },
    {
        "name": "TmuxNewSession",
        "description": "Create a new tmux session. Use detached=true (default) to keep it in the background.",
        "handler": _tmux_new_session,
        "schema": {
            "type": "object",
            "properties": {
                "session_name": {"type": "string", "description": "Session name (default: feinn)"},
                "detached": {"type": "boolean", "description": "Start detached (default: true)"},
                "command": {"type": "string", "description": "Optional command to run in the new session"},
            },
        },
    },
    {
        "name": "TmuxSplitWindow",
        "description": "Split the current tmux pane into two.",
        "handler": _tmux_split_window,
        "schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target pane (e.g. session:window.pane)"},
                "direction": {
                    "type": "string",
                    "enum": ["vertical", "horizontal"],
                    "description": "Split direction (default: vertical)",
                },
                "command": {"type": "string", "description": "Optional command to run in the new pane"},
            },
        },
    },
    {
        "name": "TmuxSendKeys",
        "description": "Send keystrokes/commands to a tmux pane.",
        "handler": _tmux_send_keys,
        "schema": {
            "type": "object",
            "properties": {
                "keys": {"type": "string", "description": "The text or command to send"},
                "target": {"type": "string", "description": "Target pane (e.g. session:window.pane)"},
                "press_enter": {"type": "boolean", "description": "Press Enter after sending keys (default: true)"},
            },
            "required": ["keys"],
        },
    },
    {
        "name": "TmuxCapture",
        "description": "Capture and return the visible text content of a tmux pane.",
        "handler": _tmux_capture_pane,
        "schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target pane (e.g. session:window.pane)"},
                "lines": {"type": "integer", "description": "Number of history lines to capture (default: 50)"},
            },
        },
    },
    {
        "name": "TmuxListPanes",
        "description": "List all panes in the current session/window with index, command, and size.",
        "handler": _tmux_list_panes,
        "schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target session or window"},
            },
        },
    },
    {
        "name": "TmuxSelectPane",
        "description": "Switch focus to a specific tmux pane.",
        "handler": _tmux_select_pane,
        "schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target pane (e.g. 0, 1, or session:window.pane)"},
            },
            "required": ["target"],
        },
    },
    {
        "name": "TmuxKillPane",
        "description": "Close/kill a tmux pane.",
        "handler": _tmux_kill_pane,
        "schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target pane to kill"},
            },
        },
    },
    {
        "name": "TmuxNewWindow",
        "description": "Create a new tmux window (tab) in a session.",
        "handler": _tmux_new_window,
        "schema": {
            "type": "object",
            "properties": {
                "target_session": {"type": "string", "description": "Session to add the window to"},
                "window_name": {"type": "string", "description": "Name for the new window"},
                "command": {"type": "string", "description": "Optional command to run"},
            },
        },
    },
    {
        "name": "TmuxListWindows",
        "description": "List all windows in a tmux session.",
        "handler": _tmux_list_windows,
        "schema": {
            "type": "object",
            "properties": {
                "target_session": {"type": "string", "description": "Session name"},
            },
        },
    },
    {
        "name": "TmuxResizePane",
        "description": "Resize a tmux pane in a given direction.",
        "handler": _tmux_resize_pane,
        "schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target pane"},
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "left", "right"],
                    "description": "Resize direction",
                },
                "amount": {"type": "integer", "description": "Number of cells to resize (default: 10)"},
            },
        },
    },
]


def register_tmux_tools() -> int:
    """Register all tmux tools if tmux is available.

    Returns the number of tools registered (0 if tmux is not found).
    """
    if not tmux_available():
        logger.info("tmux not found — tmux tools will not be registered")
        return 0

    count = 0
    for spec in _TMUX_TOOLS:
        register(
            ToolDef(
                name=spec["name"],
                description=spec["description"],
                input_schema=spec["schema"],
                handler=spec["handler"],
                read_only=spec["name"] in _READ_ONLY_TOOLS,
                concurrent_safe=True,
            )
        )
        count += 1

    logger.info("Registered %d tmux tools (binary: %s)", count, _TMUX_BIN)
    return count
