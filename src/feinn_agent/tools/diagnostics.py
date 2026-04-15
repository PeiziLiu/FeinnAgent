"""Diagnostics tool — LSP-style file diagnostics for multiple languages.

Detects the file language and runs available linting/type-checking tools
(pyright, mypy, flake8, tsc, eslint, shellcheck, etc.) to surface errors
and warnings.

Uses ``asyncio.to_thread()`` to bridge synchronous checker invocations
into FeinnAgent's async handler interface.

Harness Engineering "Sensors" pattern: provides structured diagnostic
feedback so the agent can self-correct code issues.

Reference: CheetahClaws tools.py:696-805
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from ..types import ToolDef
from .registry import register

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".sh": "shellscript",
    ".bash": "shellscript",
    ".zsh": "shellscript",
    ".go": "go",
    ".rs": "rust",
}


def _detect_language(file_path: str) -> str:
    """Detect the programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    return _EXT_TO_LANGUAGE.get(ext, "unknown")


# ---------------------------------------------------------------------------
# Low-level runner
# ---------------------------------------------------------------------------

def _run_quietly(
    cmd: list[str], cwd: str | None = None, timeout: int = 30,
) -> tuple[int, str]:
    """Run a command and return ``(returncode, combined_output)``."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=cwd or os.getcwd(),
        )
        out = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip()
        return r.returncode, out
    except FileNotFoundError:
        return -1, f"(command not found: {cmd[0]})"
    except subprocess.TimeoutExpired:
        return -1, f"(timed out after {timeout}s)"
    except Exception as e:
        return -1, f"(error: {e})"


# ---------------------------------------------------------------------------
# Core diagnostics logic (sync)
# ---------------------------------------------------------------------------

def _get_diagnostics_sync(file_path: str, language: str | None = None) -> str:
    """Run diagnostics on a file, returning human-readable results."""
    p = Path(file_path)
    if not p.exists():
        return f"Error: file not found: {file_path}"

    lang = language or _detect_language(file_path)
    abs_path = str(p.resolve())
    results: list[str] = []

    if lang == "python":
        # Try pyright first (most comprehensive)
        rc, out = _run_quietly(["pyright", "--outputjson", abs_path])
        if rc != -1:
            try:
                data = json.loads(out)
                diags = data.get("generalDiagnostics", [])
                if not diags:
                    results.append("pyright: no diagnostics")
                else:
                    lines = [f"pyright ({len(diags)} issue(s)):"]
                    for d in diags[:50]:
                        rng = d.get("range", {}).get("start", {})
                        ln = rng.get("line", 0) + 1
                        ch = rng.get("character", 0) + 1
                        sev = d.get("severity", "error")
                        msg = d.get("message", "")
                        rule = d.get("rule", "")
                        lines.append(
                            f"  {ln}:{ch} [{sev}] {msg}"
                            + (f" ({rule})" if rule else "")
                        )
                    results.append("\n".join(lines))
            except json.JSONDecodeError:
                if out:
                    results.append(f"pyright:\n{out[:3000]}")
        else:
            # Try mypy
            rc2, out2 = _run_quietly(["mypy", "--no-error-summary", abs_path])
            if rc2 != -1:
                results.append(
                    f"mypy:\n{out2[:3000]}" if out2 else "mypy: no diagnostics"
                )
            else:
                # Fall back to flake8
                rc3, out3 = _run_quietly(["flake8", abs_path])
                if rc3 != -1:
                    results.append(
                        f"flake8:\n{out3[:3000]}" if out3 else "flake8: no diagnostics"
                    )
                else:
                    # Last resort: py_compile syntax check
                    rc4, out4 = _run_quietly(
                        ["python3", "-m", "py_compile", abs_path]
                    )
                    if out4:
                        results.append(f"py_compile (syntax check):\n{out4}")
                    else:
                        results.append(
                            "py_compile: syntax OK (no further tools available)"
                        )

    elif lang in ("javascript", "typescript"):
        # Try tsc
        rc, out = _run_quietly(["tsc", "--noEmit", "--strict", abs_path])
        if rc != -1:
            results.append(
                f"tsc:\n{out[:3000]}" if out else "tsc: no errors"
            )
        else:
            # Try eslint
            rc2, out2 = _run_quietly(["eslint", abs_path])
            if rc2 != -1:
                results.append(
                    f"eslint:\n{out2[:3000]}" if out2 else "eslint: no issues"
                )
            else:
                results.append(
                    "No TypeScript/JavaScript checker found (install tsc or eslint)"
                )

    elif lang == "shellscript":
        rc, out = _run_quietly(["shellcheck", abs_path])
        if rc != -1:
            results.append(
                f"shellcheck:\n{out[:3000]}" if out else "shellcheck: no issues"
            )
        else:
            rc2, out2 = _run_quietly(["bash", "-n", abs_path])
            results.append(
                f"bash -n (syntax check):\n{out2}"
                if out2
                else "bash -n: syntax OK"
            )

    elif lang == "go":
        rc, out = _run_quietly(["go", "vet", abs_path])
        if rc != -1:
            results.append(
                f"go vet:\n{out[:3000]}" if out else "go vet: no issues"
            )
        else:
            results.append("No Go checker found (install go)")

    elif lang == "rust":
        # For Rust, check the parent project instead of single file
        cargo_dir = p.resolve().parent
        rc, out = _run_quietly(
            ["cargo", "check", "--message-format=short"], cwd=str(cargo_dir)
        )
        if rc != -1:
            results.append(
                f"cargo check:\n{out[:3000]}" if out else "cargo check: no issues"
            )
        else:
            results.append("No Rust checker found (install cargo)")

    else:
        results.append(
            f"No diagnostic tool available for language: "
            f"{lang or 'unknown'} (ext: {Path(file_path).suffix})"
        )

    return "\n\n".join(results) if results else "(no diagnostics output)"


# ---------------------------------------------------------------------------
# Async handler + registration
# ---------------------------------------------------------------------------

async def _get_diagnostics(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Async handler for GetDiagnostics tool."""
    file_path = params.get("file_path", "")
    if not file_path:
        return "Error: file_path is required"
    language = params.get("language")
    return await asyncio.to_thread(_get_diagnostics_sync, file_path, language)


register(
    ToolDef(
        name="GetDiagnostics",
        description=(
            "Get LSP-style diagnostics (errors, warnings, hints) for a source "
            "file. Auto-detects language and runs the best available checker "
            "(pyright/mypy/flake8, tsc/eslint, shellcheck, go vet, cargo check)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to check",
                },
                "language": {
                    "type": "string",
                    "description": "Override language detection (python, typescript, etc.)",
                },
            },
            "required": ["file_path"],
        },
        handler=_get_diagnostics,
        read_only=True,
        concurrent_safe=True,
    )
)
