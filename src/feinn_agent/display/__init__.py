"""Display utilities for FeinnAgent CLI.

Provides Kawaii-style interface, diff display, tool preview,
and other visualization utilities.
"""

import difflib
import json
import sys
from dataclasses import dataclass
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
                value = value[:max_length - 3] + "..."
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
                return f'"{value[:max_length-3]}..."'
            return f'"{value}"'
        elif isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)[:max_length]
        elif isinstance(value, list):
            return f"[{len(value)} items]"
        else:
            return str(value)
