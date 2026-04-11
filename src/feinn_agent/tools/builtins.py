"""FeinnAgent built-in tools — file I/O, shell, search, web."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from ..types import ToolDef
from .registry import register

# ── Read ────────────────────────────────────────────────────────────


async def _read_file(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Read file contents with line numbers."""
    file_path = params.get("file_path", "")
    offset = params.get("offset", 0)
    limit = params.get("limit")

    if not file_path:
        return "Error: file_path is required"

    try:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"Error: file not found: {file_path}"
        if path.is_dir():
            return f"Error: {file_path} is a directory, not a file"

        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        end = offset + limit if limit else len(lines)
        selected = lines[offset:end]

        result_lines = []
        for i, line in enumerate(selected, start=offset + 1):
            result_lines.append(f"{i:6d}\t{line.rstrip()}")

        return "\n".join(result_lines)

    except Exception as e:
        return f"Error reading {file_path}: {e}"


register(
    ToolDef(
        name="Read",
        description="Read a file's contents with line numbers. Supports offset and limit for large files.",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-indexed)",
                    "default": 0,
                },
                "limit": {"type": "integer", "description": "Maximum number of lines to read"},
            },
            "required": ["file_path"],
        },
        handler=_read_file,
        read_only=True,
        concurrent_safe=True,
    )
)


# ── Write ───────────────────────────────────────────────────────────


async def _write_file(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Write content to a file, creating parent directories as needed."""
    file_path = params.get("file_path", "")
    content = params.get("content", "")

    if not file_path:
        return "Error: file_path is required"

    try:
        path = Path(file_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Successfully wrote {len(content)} chars to {file_path}"

    except Exception as e:
        return f"Error writing {file_path}: {e}"


register(
    ToolDef(
        name="Write",
        description="Write content to a file. Creates the file and parent directories if they don't exist.",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["file_path", "content"],
        },
        handler=_write_file,
        read_only=False,
        destructive=False,
    )
)


# ── Edit ────────────────────────────────────────────────────────────


async def _edit_file(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Replace an exact string in a file."""
    file_path = params.get("file_path", "")
    old_string = params.get("old_string", "")
    new_string = params.get("new_string", "")
    replace_all = params.get("replace_all", False)

    if not file_path or not old_string:
        return "Error: file_path and old_string are required"

    try:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"Error: file not found: {file_path}"

        content = path.read_text(encoding="utf-8")

        if old_string not in content:
            return f"Error: old_string not found in {file_path}"

        count = content.count(old_string)
        if count > 1 and not replace_all:
            return (
                f"Error: old_string found {count} times in {file_path}. "
                "Use replace_all=true to replace all occurrences, or provide more context."
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        path.write_text(new_content, encoding="utf-8")

        replaced = count if replace_all else 1
        return f"Successfully replaced {replaced} occurrence(s) in {file_path}"

    except Exception as e:
        return f"Error editing {file_path}: {e}"


register(
    ToolDef(
        name="Edit",
        description="Replace exact string matches in a file. Use replace_all for multiple occurrences.",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "old_string": {"type": "string", "description": "Exact string to find and replace"},
                "new_string": {"type": "string", "description": "Replacement string"},
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences",
                    "default": False,
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        },
        handler=_edit_file,
        read_only=False,
    )
)


# ── Bash ────────────────────────────────────────────────────────────


async def _bash(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Execute a shell command and return output."""
    command = params.get("command", "")
    timeout = params.get("timeout", 120)
    cwd = params.get("cwd", os.getcwd())

    if not command:
        return "Error: command is required"

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            return f"Error: command timed out after {timeout}s"

        output_parts = []
        if stdout:
            output_parts.append(stdout.decode("utf-8", errors="replace"))
        if stderr:
            output_parts.append(f"[stderr]\n{stderr.decode('utf-8', errors='replace')}")

        result = "\n".join(output_parts) or f"[exit code: {proc.returncode}]"

        if proc.returncode != 0:
            result += f"\n[exit code: {proc.returncode}]"

        return result

    except Exception as e:
        return f"Error executing command: {e}"


register(
    ToolDef(
        name="Bash",
        description="Execute a shell command. Use for running tests, builds, git operations, etc.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 120},
                "cwd": {"type": "string", "description": "Working directory for the command"},
            },
            "required": ["command"],
        },
        handler=_bash,
        read_only=False,
    )
)


# ── Glob ────────────────────────────────────────────────────────────


async def _glob(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Find files matching a glob pattern."""
    pattern = params.get("pattern", "**/*")
    path = params.get("path", os.getcwd())

    try:
        base = Path(path).expanduser().resolve()
        matches = sorted(base.glob(pattern))

        # Limit results
        max_results = 200
        results = []
        for m in matches[:max_results]:
            rel = m.relative_to(base) if m.is_relative_to(base) else m
            results.append(str(rel))

        if len(matches) > max_results:
            results.append(f"... and {len(matches) - max_results} more files")

        return "\n".join(results) if results else f"No files matching '{pattern}'"

    except Exception as e:
        return f"Error: {e}"


register(
    ToolDef(
        name="Glob",
        description="Find files matching a glob pattern. Returns relative paths from the search directory.",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '**/*.py', 'src/**/*.ts')",
                },
                "path": {
                    "type": "string",
                    "description": "Base directory to search in",
                    "default": ".",
                },
            },
            "required": ["pattern"],
        },
        handler=_glob,
        read_only=True,
        concurrent_safe=True,
    )
)


# ── Grep ────────────────────────────────────────────────────────────


async def _grep(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Search for a pattern in files using regex."""
    pattern = params.get("pattern", "")
    path = params.get("path", os.getcwd())
    glob_filter = params.get("glob", "")
    case_insensitive = params.get("case_insensitive", False)
    max_results = params.get("max_results", 100)

    if not pattern:
        return "Error: pattern is required"

    try:
        flags = re.IGNORECASE if case_insensitive else 0
        regex = re.compile(pattern, flags)
        base = Path(path).expanduser().resolve()

        results: list[str] = []
        file_pattern = glob_filter or None
        files = base.rglob(file_pattern) if file_pattern else base.rglob("*")

        for file_path in files:
            if not file_path.is_file():
                continue
            # Skip binary / large files
            if file_path.stat().st_size > 1_000_000:
                continue

            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        rel = (
                            file_path.relative_to(base)
                            if file_path.is_relative_to(base)
                            else file_path
                        )
                        results.append(f"{rel}:{i}: {line.strip()}")
                        if len(results) >= max_results:
                            break
            except (OSError, UnicodeDecodeError):
                continue

            if len(results) >= max_results:
                break

        return "\n".join(results) if results else f"No matches for '{pattern}'"

    except re.error as e:
        return f"Invalid regex: {e}"
    except Exception as e:
        return f"Error: {e}"


register(
    ToolDef(
        name="Grep",
        description="Search file contents with regex. Returns matching lines with file:line: format.",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "Directory to search in", "default": "."},
                "glob": {"type": "string", "description": "File glob filter (e.g. '*.py', '*.ts')"},
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Case-insensitive search",
                    "default": False,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results",
                    "default": 100,
                },
            },
            "required": ["pattern"],
        },
        handler=_grep,
        read_only=True,
        concurrent_safe=True,
    )
)


# ── WebFetch ────────────────────────────────────────────────────────


async def _web_fetch(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Fetch content from a URL."""
    url = params.get("url", "")
    if not url:
        return "Error: url is required"

    try:
        import httpx

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.text
            # Truncate large responses
            if len(content) > 50_000:
                content = (
                    content[:25_000]
                    + f"\n... [{len(content) - 50_000} chars truncated] ...\n"
                    + content[-25_000:]
                )
            return content
    except ImportError:
        return "Error: httpx package required for WebFetch"
    except Exception as e:
        return f"Error fetching {url}: {e}"


register(
    ToolDef(
        name="WebFetch",
        description="Fetch content from a URL. Returns the raw response body.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
            },
            "required": ["url"],
        },
        handler=_web_fetch,
        read_only=True,
        concurrent_safe=True,
    )
)


# ── AskUserQuestion ─────────────────────────────────────────────────


async def _ask_user(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Ask the user a clarifying question."""
    question = params.get("question", "")
    if not question:
        return "Error: question is required"
    # In API mode, this returns the question as-is for the caller to handle.
    # In CLI mode, the permission callback will intercept and show a prompt.
    return f"[User question: {question}]"


register(
    ToolDef(
        name="AskUserQuestion",
        description="Ask the user a clarifying question when you need more information.",
        input_schema={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question to ask the user"},
            },
            "required": ["question"],
        },
        handler=_ask_user,
        read_only=True,
    )
)
