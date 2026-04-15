"""Process management — subprocess execution with safety harnesses.

Provides robust command execution with process-group isolation, tree cleanup,
ANSI stripping, and exit-code semantics.  Applies Harness Engineering patterns:

* **Guides** (pre-execution): start_new_session isolates the child process group
  so runaway children cannot outlive the agent.
* **Sensors** (post-execution): exit-code semantic hints give the LLM actionable
  context instead of raw integers.
* **Guardrails** (boundary): timeout + kill_process_tree ensures no zombie leaks.

Reference: CheetahClaws tools.py:453-495
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import sys

# ---------------------------------------------------------------------------
# Exit-code semantics — give the LLM a human-readable hint for common codes.
# ---------------------------------------------------------------------------
_EXIT_CODE_MEANINGS: dict[int, str] = {
    # Universal
    1: "general error",
    2: "misuse of shell builtin / invalid argument",
    126: "command found but not executable (permission denied?)",
    127: "command not found",
    128: "invalid exit argument",
    130: "terminated by Ctrl-C (SIGINT)",
    137: "killed (SIGKILL / OOM killer?)",
    139: "segmentation fault (SIGSEGV)",
    143: "terminated (SIGTERM)",
    # grep
    # 0 = match found, 1 = no match, 2 = error
    # diff
    # 0 = identical, 1 = differences found, 2 = error
    # pytest / unittest
    # 0 = all passed, 1 = some failed, 2 = interrupted, 5 = no tests collected
}


def exit_code_hint(code: int, command: str = "") -> str:
    """Return a human-readable hint for a non-zero exit code.

    For ambiguous codes (e.g. 1) that differ by tool, use the command prefix
    to disambiguate.
    """
    if code == 0:
        return ""

    cmd_lower = command.strip().split()[0] if command.strip() else ""

    # Tool-specific overrides for exit code 1
    if code == 1:
        if cmd_lower in ("grep", "rg", "ag"):
            return "no matches found"
        if cmd_lower == "diff":
            return "files differ (this is normal for diff)"
        if cmd_lower in ("pytest", "python", "py"):
            return "tests failed"

    meaning = _EXIT_CODE_MEANINGS.get(code)
    if meaning:
        return meaning

    if code > 128:
        sig_num = code - 128
        try:
            sig_name = signal.Signals(sig_num).name
            return f"killed by {sig_name}"
        except ValueError:
            return f"killed by signal {sig_num}"

    return ""


# ---------------------------------------------------------------------------
# ANSI escape stripping
# ---------------------------------------------------------------------------
_ANSI_ESCAPE = re.compile(
    r"""
    \x1b      # ESC character
    (?:       # followed by either ...
      \[      #   CSI: [
      [0-9;]* #   parameter bytes
      [A-Za-z]#   final byte
    |
      \]      #   OSC: ]
      .*?     #   payload
      (?:\x07|\x1b\\)  # terminated by BEL or ST
    |
      [()][AB012]  # Character set selection
    )
    """,
    re.VERBOSE,
)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return _ANSI_ESCAPE.sub("", text)


# ---------------------------------------------------------------------------
# Process tree cleanup
# ---------------------------------------------------------------------------

def kill_process_tree(pid: int) -> None:
    """Kill a process and all its children (cross-platform).

    On Unix, kills the entire process group via ``os.killpg``.
    On Windows, uses ``taskkill /F /T``.

    Reference: CheetahClaws tools.py:453-468
    """
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
        )
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


# ---------------------------------------------------------------------------
# Core command runner
# ---------------------------------------------------------------------------

async def run_command(
    command: str,
    timeout: int = 120,
    cwd: str | None = None,
) -> tuple[str, int]:
    """Execute a shell command with process-group isolation and tree cleanup.

    Returns ``(output, exit_code)`` where *output* is the combined
    stdout + stderr (ANSI-stripped) and *exit_code* is the process return code.

    Key improvements over a bare ``create_subprocess_shell``:

    * ``start_new_session=True`` — child gets its own process group so that
      ``kill_process_tree`` can reap the whole tree on timeout.
    * ANSI escape codes are stripped so the LLM sees clean text.
    * Exit-code semantic hints are appended for non-zero codes.
    """
    if not command:
        return "Error: command is required", 1

    effective_cwd = cwd or os.getcwd()

    # Build kwargs; process-group isolation is Unix-only.
    kwargs: dict = dict(
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=effective_cwd,
    )
    if sys.platform != "win32":
        kwargs["start_new_session"] = True

    try:
        proc = await asyncio.create_subprocess_shell(command, **kwargs)
    except Exception as e:
        return f"Error starting command: {e}", 1

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except TimeoutError:
        # Kill the entire process tree, then reap the leader.
        kill_process_tree(proc.pid)
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
        return f"Error: command timed out after {timeout}s (process tree killed)", -1

    stdout = strip_ansi(stdout_bytes.decode("utf-8", errors="replace")) if stdout_bytes else ""
    stderr = strip_ansi(stderr_bytes.decode("utf-8", errors="replace")) if stderr_bytes else ""

    exit_code: int = proc.returncode or 0

    # Assemble output
    parts: list[str] = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append(f"[stderr]\n{stderr}")

    output = "\n".join(parts) or "(no output)"

    # Append exit-code info for non-zero codes
    if exit_code != 0:
        hint = exit_code_hint(exit_code, command)
        hint_str = f" ({hint})" if hint else ""
        output += f"\n[exit code: {exit_code}{hint_str}]"

    return output, exit_code
