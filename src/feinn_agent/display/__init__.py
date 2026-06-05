"""Display utilities for FeinnAgent CLI.

Provides Kawaii-style interface, diff display, tool preview,
and other visualization utilities.
"""

from __future__ import annotations

import difflib
import json
import shutil
from typing import Optional


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


class KawaiiDisplay:
    """Kawaii-style display for FeinnAgent."""

    STATUS_EMOJI = {
        "thinking": "🤔",
        "executing": "⚡",
        "success": "✨",
        "error": "😢",
        "warning": "🤨",
        "waiting": "⏳",
        "completed": "🎉",
        "interrupted": "🛑",
        "planning": "📋",
        "checkpoint": "📸",
        "restoring": "⏪",
        "file": "📄",
        "folder": "📁",
        "robot": "🤖",
        "rocket": "🚀",
        "lightning": "⚡",
        "gear": "⚙️",
        "star": "⭐",
        "heart": "❤️",
    }

    def __init__(self, use_color: bool = True):
        self.use_color = use_color

    def _color(self, text: str, color: str) -> str:
        """Apply color to text."""
        if not self.use_color:
            return text
        return f"{color}{text}{Colors.RESET}"

    def _bold(self, text: str) -> str:
        """Make text bold."""
        if not self.use_color:
            return text
        return f"{Colors.BOLD}{text}{Colors.RESET}"

    def show_status(self, status: str, message: str) -> str:
        """Show a status message with emoji.

        Args:
            status: Status type (from STATUS_EMOJI keys)
            message: Message to display

        Returns:
            Formatted string
        """
        emoji = self.STATUS_EMOJI.get(status, "❓")
        return f"{emoji} {message}"

    def show_progress(
        self,
        current: int,
        total: int,
        message: str = "",
        width: int = 30,
    ) -> str:
        """Show a progress bar.

        Args:
            current: Current progress value
            total: Total value
            message: Optional message to show
            width: Width of progress bar in characters

        Returns:
            Formatted progress bar string
        """
        if total == 0:
            percentage = 100
        else:
            percentage = min(int(current / total * 100), 100)

        filled = int(width * percentage / 100)
        bar = "█" * filled + "░" * (width - filled)

        emoji = "⚡" if percentage < 100 else "🎉"
        msg_part = f" {message}" if message else ""

        return f"{emoji} [{bar}] {percentage}%{msg_part}"

    def show_tool_start(
        self,
        tool_name: str,
        arguments: Optional[dict] = None,
    ) -> str:
        """Show tool execution start.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Formatted string
        """
        emoji = self.STATUS_EMOJI.get("executing", "⚡")
        output = [f"{emoji} {self._bold(tool_name)}("]

        if arguments:
            args_str = self._format_arguments(arguments)
            output.append(f"  {args_str}")

        output.append(")")
        return "\n".join(output)

    def show_tool_end(
        self,
        tool_name: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> str:
        """Show tool execution end.

        Args:
            tool_name: Name of the tool
            success: Whether execution was successful
            error: Optional error message

        Returns:
            Formatted string
        """
        if success:
            emoji = self.STATUS_EMOJI.get("success", "✨")
            status = self._color("✓", Colors.GREEN)
        else:
            emoji = self.STATUS_EMOJI.get("error", "😢")
            status = self._color("✗", Colors.RED)

        output = [f"{emoji} {self._bold(tool_name)} {status}"]

        if error:
            output.append(f"  {self._color(error, Colors.RED)}")

        return "\n".join(output)

    def _format_arguments(self, arguments: dict, max_length: int = 60) -> str:
        """Format tool arguments for display.

        Args:
            arguments: Arguments dictionary
            max_length: Maximum line length

        Returns:
            Formatted arguments string
        """
        lines = []
        for key, value in arguments.items():
            if isinstance(value, str) and len(value) > max_length:
                value = value[: max_length - 3] + "..."
            elif isinstance(value, dict):
                value = json.dumps(value)[:max_length] + "..."
            elif isinstance(value, list):
                value = str(value)[:max_length] + "..."

            lines.append(f"{key}={repr(value)}")

        return ", ".join(lines)

    def show_plan_step(
        self,
        step_number: int,
        description: str,
        status: str = "pending",
        index: Optional[int] = None,
    ) -> str:
        """Show a plan step.

        Args:
            step_number: Step number
            description: Step description
            status: Step status ('pending', 'in_progress', 'completed', 'skipped', 'failed')
            index: Optional index for ordering

        Returns:
            Formatted string
        """
        status_icons = {
            "pending": "○",
            "in_progress": "◐",
            "completed": "●",
            "skipped": "◌",
            "failed": "✗",
        }

        icon = status_icons.get(status, "○")

        if status == "completed":
            icon = self._color(icon, Colors.GREEN)
        elif status == "failed":
            icon = self._color(icon, Colors.RED)
        elif status == "in_progress":
            icon = self._color(icon, Colors.YELLOW)

        index_str = f"[{index}] " if index is not None else ""
        return f"  {icon} {index_str}{description}"

    def show_checkpoint(
        self,
        checkpoint_id: str,
        message: str,
        file_count: int = 0,
    ) -> str:
        """Show checkpoint information.

        Args:
            checkpoint_id: Checkpoint ID
            message: Checkpoint message
            file_count: Number of files in checkpoint

        Returns:
            Formatted string
        """
        emoji = self.STATUS_EMOJI.get("checkpoint", "📸")
        return f"{emoji} Checkpoint {checkpoint_id}: {message} ({file_count} files)"

    def show_interrupt(self, reason: str = "") -> str:
        """Show interrupt message.

        Args:
            reason: Interrupt reason

        Returns:
            Formatted string
        """
        emoji = self.STATUS_EMOJI.get("interrupted", "🛑")
        msg = "Execution interrupted"
        if reason:
            msg += f": {reason}"
        return f"{emoji} {self._color(msg, Colors.RED)}"

    def show_welcome(self, model: str) -> str:
        """Show welcome banner.

        Args:
            model: Model being used

        Returns:
            Formatted welcome string
        """
        lines = [
            "",
            self._color("  ╔═══════════════════════════════════════════╗", Colors.CYAN),
            "  ║" + self._color("     ✨ FeinnAgent", Colors.CYAN) + " " * 30 + "║",
            f"  ║  Model: {model}" + " " * (38 - len(model)) + "║",
            "  ║  Type '/help' for commands" + " " * 20 + "║",
            self._color("  ╚═══════════════════════════════════════════╝", Colors.CYAN),
            "",
        ]
        return "\n".join(lines)

    def show_todo_list(
        self,
        items: list[dict],
        current_index: int = -1,
        title: str = "📋 任务规划",
    ) -> str:
        """Show a todo list with progress."""
        status_map = {
            "pending": ("☐", Colors.BRIGHT_BLACK),
            "in_progress": ("▶", Colors.YELLOW),
            "completed": ("✅", Colors.GREEN),
            "skipped": ("⏭", Colors.BRIGHT_BLACK),
            "failed": ("❌", Colors.RED),
        }
        lines = [f"┌─ {title} {'─' * 20}┐"]
        for i, item in enumerate(items):
            status = item.get("status", "pending")
            content = item.get("content", str(item))
            box, color = status_map.get(status, ("☐", Colors.BRIGHT_BLACK))
            idx_str = f"[{i + 1}]"
            current_marker = "▶ " if i == current_index else "  "
            if i == current_index:
                lines.append(f"│ {box} {self._bold(idx_str + current_marker + content[:40])}")
            else:
                lines.append(f"│ {box} {idx_str} {self._color(content[:40], color)}")
        lines.append("└" + "─" * 40 + "┘")
        return "\n".join(lines)

    def show_progress_detailed(
        self,
        current: int,
        total: int,
        step_name: str = "",
        width: int = 20,
    ) -> str:
        """Show a detailed progress bar."""
        if total == 0:
            percentage = 100
            progress_bar = "█" * width
        else:
            percentage = min(int(current / total * 100), 100)
            filled = int(width * current / total)
            progress_bar = "█" * filled + "░" * (width - filled)
        emoji = "🎉" if current == total else ("⏳" if current == 0 else "⚡")
        status = "完成" if current == total else ("等待开始" if current == 0 else "处理中")
        box_content = f" [{current}/{total}] {percentage}% [{progress_bar}]"
        if step_name:
            box_content += f" {step_name[:20]}"
        lines = [
            f"┌─ {emoji} 执行进度 {box_content} {'─' * 10}┐",
            f"│ {status}: {step_name or '无'}",
            "└" + "─" * 40 + "┘",
        ]
        return "\n".join(lines)

    def show_tool_execution(
        self,
        tool_name: str,
        status: str = "start",
        args: dict | None = None,
    ) -> str:
        """Show tool execution status."""
        if status == "start":
            first_arg = ""
            if args:
                first_val = next(iter(args.values()), "")
                if isinstance(first_val, str) and len(first_val) > 30:
                    first_val = first_val[:30] + "..."
                first_arg = f" {first_val}"
            return f"⚡ {self._bold(tool_name)}{first_arg}"
        elif status == "success":
            return f"  └─ {self._color('✅', Colors.GREEN)}"
        return ""

    def show_thinking_collapsed(self, thinking: str, max_lines: int = 8) -> str:
        """Show thinking/reasoning content in collapsed form.

        Args:
            thinking: The full thinking content.
            max_lines: Max lines to show before truncation.

        Returns:
            Formatted collapsed thinking string.
        """
        lines = thinking.strip().split("\n")
        truncated = len(lines) > max_lines
        shown = lines[:max_lines]

        output = [
            self._color("┌─ 🤔 Thinking", Colors.BRIGHT_BLACK),
        ]
        for line in shown:
            output.append(f"│ {self._color(line, Colors.BRIGHT_BLACK)}")
        if truncated:
            output.append(f"│ {self._color(f'... ({len(lines) - max_lines} more lines)', Colors.BRIGHT_BLACK)}")
        output.append(self._color("└" + "─" * 40, Colors.BRIGHT_BLACK))
        return "\n".join(output)

    def show_status_summary(
        self,
        turn_count: int,
        input_tokens: int,
        output_tokens: int,
        cost: float = 0.0,
    ) -> str:
        """Show execution status summary."""
        total = input_tokens + output_tokens
        tokens_str = f"{input_tokens}↓ + {output_tokens}↑ = {total}"
        if cost > 0:
            tokens_str += f" (${cost:.4f})"
        lines = [
            f"┌─ 📊 执行统计 {'─' * 30}┐",
            f"│ {self._color('Turns:', Colors.BRIGHT_BLACK)} {turn_count}",
            f"│ {self._color('Tokens:', Colors.BRIGHT_BLACK)} {tokens_str}",
            "└" + "─" * 40 + "┘",
        ]
        return "\n".join(lines)


class DiffDisplay:
    """Display file diffs."""

    def __init__(self, use_color: bool = True):
        self.use_color = use_color

    def _color(self, text: str, color: str) -> str:
        """Apply color to text."""
        if not self.use_color:
            return text
        return f"{color}{text}{Colors.RESET}"

    def format_unified_diff(
        self,
        old_lines: list[str],
        new_lines: list[str],
        from_file: str = "a",
        to_file: str = "b",
        context: int = 3,
    ) -> str:
        """Generate unified diff output.

        Args:
            old_lines: Original lines
            new_lines: New lines
            from_file: Original file name
            to_file: New file name
            context: Number of context lines

        Returns:
            Formatted diff string
        """
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=from_file,
            tofile=to_file,
            n=context,
        )

        lines = []
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                lines.append(self._color(line, Colors.GREEN))
            elif line.startswith("-") and not line.startswith("---"):
                lines.append(self._color(line, Colors.RED))
            elif line.startswith("@@"):
                lines.append(self._color(line, Colors.CYAN))
            else:
                lines.append(line)

        return "".join(lines)

    def show_file_diff(
        self,
        old_content: str,
        new_content: str,
        filename: str,
        max_lines: int = 100,
    ) -> str:
        """Show a file diff.

        Args:
            old_content: Original file content
            new_content: New file content
            filename: File name
            max_lines: Maximum lines to show

        Returns:
            Formatted diff string
        """
        old_lines = old_content.splitlines()[:max_lines]
        new_lines = new_content.splitlines()[:max_lines]

        header = self._color(f"--- {filename}", Colors.RED) + "\n"
        header += self._color(f"+++ {filename}", Colors.GREEN)

        diff = self.format_unified_diff(old_lines, new_lines, from_file=filename, to_file=filename)

        return header + "\n" + diff

    def show_changes_summary(
        self,
        added: int,
        modified: int,
        deleted: int,
    ) -> str:
        """Show a summary of changes.

        Args:
            added: Number of added files
            modified: Number of modified files
            deleted: Number of deleted files

        Returns:
            Formatted summary string
        """
        parts = []
        if added > 0:
            parts.append(self._color(f"+{added}", Colors.GREEN))
        if modified > 0:
            parts.append(self._color(f"~{modified}", Colors.YELLOW))
        if deleted > 0:
            parts.append(self._color(f"-{deleted}", Colors.RED))

        return f"Changes: {' | '.join(parts)}" if parts else "No changes"


class ToolPreview:
    """Generate tool call previews."""

    def __init__(self, use_color: bool = True):
        self.use_color = use_color

    def _color(self, text: str, color: str) -> str:
        """Apply color to text."""
        if not self.use_color:
            return text
        return f"{color}{text}{Colors.RESET}"

    def preview_tool_call(
        self,
        tool_name: str,
        arguments: dict,
    ) -> str:
        """Generate a preview of a tool call.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Formatted preview string
        """
        lines = [
            self._color("┌─ Tool Preview", Colors.CYAN),
            f"│ {self._color('Name:', Colors.BRIGHT_BLACK)} {tool_name}",
            f"│ {self._color('Args:', Colors.BRIGHT_BLACK)}",
        ]

        for key, value in arguments.items():
            value_str = self._format_value(value)
            lines.append(f"│   {self._color(key + ':', Colors.YELLOW)} {value_str}")

        lines.append(self._color("└" + "─" * 40, Colors.CYAN))

        return "\n".join(lines)

    def _format_value(self, value, max_length: int = 50) -> str:
        """Format a value for display.

        Args:
            value: Value to format
            max_length: Maximum length

        Returns:
            Formatted value string
        """
        if isinstance(value, str):
            if len(value) > max_length:
                return f'"{value[: max_length - 3]}..."'
            return f'"{value}"'
        elif isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)[:max_length]
        elif isinstance(value, list):
            return f"[{len(value)} items]"
        else:
            return str(value)


# ── Spinner Engine ──────────────────────────────────────────────────


class SpinnerEngine:
    """Animated spinner with kawaii faces and elapsed time.

    Usage:
        spinner = SpinnerEngine()
        frame = spinner.render(elapsed=5.2, message="Working...")
        # "⠋ (｡◕‿◕｡) Working... (00:05)"
    """

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    FACES_WAITING = [
        "(｡◕‿◕｡)",
        "(◕‿◕✿)",
        "(◠‿◠)",
        "(ᵔ◡ᵔ)",
        "(•‿•)",
    ]

    FACES_THINKING = [
        "(◕ ◡ ◕)",
        "(◉ ◡ ◉)",
        "(ﾉ◕ヮ◕)ﾉ",
        "(⌒ ‿ ⌒)",
    ]

    def __init__(self, use_color: bool = True):
        self.use_color = use_color
        self._frame_index = 0
        self._face_index = 0

    def render(self, elapsed: float, message: str = "", thinking: bool = False) -> str:
        """Render the current spinner frame.

        Args:
            elapsed: Seconds elapsed.
            message: Status message.
            thinking: Whether showing "thinking" vs "waiting" face set.

        Returns:
            Formatted spinner line.
        """
        self._frame_index = (self._frame_index + 1) % len(self.SPINNER_FRAMES)
        spinner = self.SPINNER_FRAMES[self._frame_index]

        faces = self.FACES_THINKING if thinking else self.FACES_WAITING
        self._face_index = (self._face_index + 1) % len(faces)
        face = faces[self._face_index]

        elapsed_str = self._format_elapsed(elapsed)
        parts = [spinner, face]
        if message:
            parts.append(message)
        parts.append(f"({elapsed_str})")
        return " ".join(parts)

    def _format_elapsed(self, seconds: float) -> str:
        """Format elapsed time as MM:SS or HH:MM:SS."""
        secs = int(seconds)
        if secs < 3600:
            return f"{secs // 60:02d}:{secs % 60:02d}"
        return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"


# ── Tool emoji map ──────────────────────────────────────────────────

TOOL_EMOJI: dict[str, str] = {
    "Bash": "⚡",
    "Read": "📖",
    "Write": "📝",
    "Edit": "✏️",
    "Glob": "🔍",
    "Grep": "🔎",
    "WebFetch": "🌐",
    "Skill": "🧠",
    "SkillList": "📋",
    "SkillManage": "🔧",
    "MemorySave": "💾",
    "MemorySearch": "🔎",
    "MemoryDelete": "🗑️",
    "MemoryList": "📋",
    "SessionSearch": "🔍",
    "AskUserQuestion": "💬",
}


def get_tool_emoji(tool_name: str) -> str:
    """Get emoji for a tool name."""
    return TOOL_EMOJI.get(tool_name, "⚙️")


# ── Tool card rendering ─────────────────────────────────────────────


def render_tool_card(tool_name: str, args: dict | None = None, status: str = "running") -> str:
    """Render a tool execution card.

    Args:
        tool_name: Name of the tool.
        args: Tool arguments.
        status: "running" | "success" | "error" | "denied".

    Returns:
        Formatted tool card string.
    """
    emoji = get_tool_emoji(tool_name)
    if status == "running":
        return f"  {emoji} {Colors.BOLD}{tool_name}{Colors.RESET}{_format_args_summary(args)}"
    elif status == "success":
        return f"  └─ {Colors.GREEN}✓{Colors.RESET} {tool_name} completed"
    elif status == "denied":
        return f"  └─ {Colors.RED}✗{Colors.RESET} {tool_name} denied"
    elif status == "error":
        return f"  └─ {Colors.RED}✗{Colors.RESET} {tool_name} failed"
    return f"  {emoji} {tool_name}"


def render_tool_line(tool_name: str, args: dict | None = None, duration: float = 0.0, status: str = "completed") -> str:
    """Render a compact Hermes-style tool output line.

    Format: ``┊ {emoji} {action:9} {detail}  {duration:.1f}s``

    Args:
        tool_name: Name of the tool.
        args: Tool arguments (first value is used as detail).
        duration: Execution duration in seconds.
        status: "completed" | "error" | "denied".

    Returns:
        Formatted tool line string.
    """
    emoji = get_tool_emoji(tool_name)
    dur = f"{duration:.1f}s"
    first_val = ""
    if args:
        first_val = next(iter(args.values()), "")
        if isinstance(first_val, str) and len(first_val) > 42:
            first_val = first_val[:42] + "..."

    action = tool_name[:9].lower()

    if status == "error":
        return f"  ┊ {Colors.RED}{emoji} {action:9} {first_val}  {dur}{Colors.RESET}"
    elif status == "denied":
        return f"  ┊ {Colors.RED}{emoji} {action:9} {first_val}  {dur} {Colors.DIM}(denied){Colors.RESET}"
    else:
        return f"  ┊ {emoji} {action:9} {first_val}  {dur}"


def render_response_box_header(model_name: str) -> str:
    """Render a Hermes-style response box header.

    Format: ``╭─ ⚕ model ────────────────────────────╮``
    """
    cols, _ = shutil.get_terminal_size()
    label = f" ⚕ {model_name} "
    fill = max(cols - len(label) - 2, 1)
    return f"\n{Colors.BRIGHT_BLACK}╭─{label}{'─' * fill}╮{Colors.RESET}"


def _format_args_summary(args: dict | None) -> str:
    """Format tool args as a one-line summary."""
    if not args:
        return ""
    first_val = next(iter(args.values()), "")
    if isinstance(first_val, str) and len(first_val) > 40:
        first_val = first_val[:40] + "..."
    return f" {first_val}"


# ── Enhanced diff display ───────────────────────────────────────────


def render_diff_text(diff_text: str, max_lines: int = 20) -> str:
    """Render a unified diff with color coding.

    Args:
        diff_text: Raw unified diff text.
        max_lines: Max lines to show before truncation.

    Returns:
        Color-coded diff string.
    """
    lines = diff_text.splitlines()
    truncated = len(lines) > max_lines
    shown = lines[:max_lines]

    result: list[str] = []
    for line in shown:
        if line.startswith("+") and not line.startswith("+++"):
            result.append(f"{Colors.GREEN}{line}{Colors.RESET}")
        elif line.startswith("-") and not line.startswith("---"):
            result.append(f"{Colors.RED}{line}{Colors.RESET}")
        elif line.startswith("@@"):
            result.append(f"{Colors.CYAN}{line}{Colors.RESET}")
        elif line.startswith("---") or line.startswith("+++"):
            result.append(f"{Colors.BOLD}{Colors.BRIGHT_BLACK}{line}{Colors.RESET}")
        else:
            result.append(line)

    if truncated:
        result.append(f"{Colors.BRIGHT_BLACK}... ({len(lines) - max_lines} more lines){Colors.RESET}")

    return "\n".join(result)


def render_diff_summary(diff_text: str) -> str:
    """Render a one-line diff summary.

    Args:
        diff_text: Raw unified diff text.

    Returns:
        Summary like "+5 | ~3 | -1".
    """
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    parts: list[str] = []
    if added:
        parts.append(f"{Colors.GREEN}+{added}{Colors.RESET}")
    if removed:
        parts.append(f"{Colors.RED}-{removed}{Colors.RESET}")
    if not parts:
        return f"{Colors.BRIGHT_BLACK}no changes{Colors.RESET}"
    return " | ".join(parts)


def render_status_bar(
    model_name: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    duration: int = 0,
) -> str:
    """Render a compact framed status bar line (no ANSI codes).

    Format: ``╭─ ⚕ model │ tokens │ duration ─────────────────╮``
    """
    dur_str = f"{duration}s" if duration < 60 else f"{duration // 60}m{duration % 60:02d}s"
    tokens = f"{input_tokens}↓ {output_tokens}↑"
    label = f" ⚕ {model_name} | {tokens} | {dur_str} "
    cols, _ = shutil.get_terminal_size()
    fill = max(cols - len(label) - 2, 1)
    return f"╭─{label}{'─' * fill}╮"
