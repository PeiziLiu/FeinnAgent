"""FeinnAgent CLI — interactive terminal interface.

Usage:
    feinn                          # Start interactive REPL
    feinn "Fix the bug"            # One-shot query
    feinn --model gpt-4o "..."    # Specify model
    feinn --serve                  # Start API server
    feinn --accept-all "..."       # Auto-approve all tools
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from .config import load_config, setup_logging
from .context import build_system_prompt
from .display import (
    Colors,
    SpinnerEngine,
    render_diff_summary,
    render_diff_text,
    render_tool_card,
)

if TYPE_CHECKING:
    from .agent import FeinnAgent
from .display import KawaiiDisplay
from .mcp import init_mcp, shutdown_mcp
from .memory import store as _memory_store  # noqa: F401 — register memory tools
from .subagent import manager as _subagent  # noqa: F401 — register agent tools
from .task import store as _task_store  # noqa: F401 — register task tools
from .tools import builtins  # noqa: F401 — register built-in tools
from .types import (
    AgentDone,
    PermissionMode,
    TextChunk,
    ThinkingChunk,
    ToolEnd,
    ToolStart,
    TurnDone,
)

display = KawaiiDisplay()

# ── Thread-safe printing ────────────────────────────────────────────

_cprint_use_pt = False


def _init_cprint():
    """Initialize cross-thread safe printing via prompt_toolkit."""
    global _cprint_use_pt
    import importlib.util

    _cprint_use_pt = importlib.util.find_spec("prompt_toolkit") is not None


def _cprint(text: str, **kwargs: Any) -> None:
    """Thread-safe print that won't corrupt the TUI input area."""
    if _cprint_use_pt:
        try:
            from prompt_toolkit import print_formatted_text as _pt_print
            from prompt_toolkit.formatted_text import ANSI as _PT_ANSI

            _pt_print(_PT_ANSI(text), **kwargs)
        except Exception:
            click.echo(text, **kwargs)
    else:
        click.echo(text, **kwargs)


def _ensure_builtins() -> None:
    """Ensure built-in tools are registered. Called before agent creation."""
    pass  # Registration happens at import time via from .tools import builtins


try:
    from prompt_toolkit.completion.base import Completer as _CompleterBase
except ImportError:
    _CompleterBase = object


class FeinnCompleter(_CompleterBase):
    """Completes slash commands, skill activators, @-references, and file paths.

    Used as the ``completer`` for prompt_toolkit's PromptSession.
    """

    COMMANDS = [
        "/quit",
        "/help",
        "/clear",
        "/save",
        "/model",
        "/tasks",
        "/memory",
        "/skills",
        "/config",
        "/accept-all",
        "/auto",
        "/manual",
        "/plan",
        "/checkpoint",
        "/interrupt",
        "/resume",
        "/trajectory",
    ]

    SKILL_ACTIVATORS: list[str] = []

    @classmethod
    def refresh_skills(cls) -> None:
        """Reload skill activators from disk."""
        try:
            from .skill.loader import load_skills

            skills = load_skills()
            cls.SKILL_ACTIVATORS = [a for s in skills if s.visible_to_user for a in s.activators]
        except Exception:
            pass

    def get_completions(self, document: Any, complete_event: Any) -> Any:
        """Yield completions for the current word."""
        try:
            from prompt_toolkit.completion import Completion
        except ImportError:
            return

        word = document.get_word_before_cursor()
        if not word:
            return

        word_lower = word.lower()

        if word.startswith("/"):
            candidates = self.COMMANDS + self.SKILL_ACTIVATORS
            for c in candidates:
                if c.lower().startswith(word_lower):
                    yield Completion(c, -len(word))
        elif word.startswith("@"):
            refs = ["@file:", "@folder:", "@git:", "@diff", "@staged"]
            for r in refs:
                if r.lower().startswith(word_lower):
                    yield Completion(r, -len(word))
        elif any(word.startswith(p) for p in ("./", "../", "~/", "/")):
            try:
                base = word
                dir_part = os.path.dirname(base) or "."
                prefix = os.path.basename(base)
                expanded = os.path.expanduser(dir_part)
                if os.path.isdir(expanded):
                    for entry in sorted(os.listdir(expanded)):
                        if entry.startswith(prefix):
                            full = os.path.join(dir_part, entry)
                            if os.path.isdir(os.path.expanduser(full)):
                                entry += "/"
                            yield Completion(entry, -len(prefix))
            except Exception:
                pass


# ── Permission callback with session allowlist ──────────────────────

_session_allowlist: set[str] = set()


def _make_permission_callback(config: dict[str, Any]) -> Any:
    """Create a permission callback with session allowlist and diff preview."""

    async def _callback(request: Any) -> bool:
        if request.name in _session_allowlist:
            return True

        _cprint("")
        _cprint(
            f"{Colors.YELLOW}  ┌─ Permission Request{Colors.RESET}\n"
            f"  │ {Colors.BRIGHT_BLACK}Tool:{Colors.RESET} {request.name}\n"
        )

        for key, val in request.inputs.items():
            if isinstance(val, str) and len(val) > 80:
                val = val[:80] + "..."
            _cprint(f"  │ {Colors.BRIGHT_BLACK}{key}:{Colors.RESET} {val}")

        # Diff preview for Write/Edit
        if request.name in ("Write", "Edit") and "file_path" in request.inputs:
            fpath = request.inputs.get("file_path", "")
            old_content = request.inputs.get("content", "") or request.inputs.get("new_string", "")
            try:
                expanded = os.path.expanduser(fpath)
                old_lines: list[str] = []
                if os.path.isfile(expanded):
                    with open(expanded, encoding="utf-8", errors="replace") as f:
                        old_lines = f.read().splitlines()
                new_lines = old_content.splitlines()
                if old_lines or new_lines:
                    import difflib

                    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
                    if diff:
                        _cprint(f"  │ {Colors.BRIGHT_BLACK}diff preview:{Colors.RESET}")
                        for line in diff[:10]:
                            _cprint(f"  │  {render_diff_text(line)}")
                        if len(diff) > 10:
                            _cprint(f"  │  {Colors.BRIGHT_BLACK}... ({len(diff) - 10} more lines){Colors.RESET}")
            except Exception:
                pass

        _cprint(f"  {Colors.YELLOW}└─{Colors.RESET}")

        try:
            from prompt_toolkit import PromptSession

            session = PromptSession()
            answer = await session.prompt_async("  Allow? (y/n/A/s): ")
        except ImportError:
            answer = input("  Allow? (y/n/A/s): ")

        answer = answer.strip().lower()
        if answer == "a":
            config["permission_mode"] = PermissionMode.ACCEPT_ALL.value
            _cprint(f"  {Colors.GREEN}→ Permission mode set to accept-all{Colors.RESET}")
            return True
        elif answer == "s":
            _session_allowlist.add(request.name)
            _cprint(f"  {Colors.GREEN}→ {request.name} allowed for this session{Colors.RESET}")
            return True
        elif answer == "d":
            _cprint(f"  {Colors.RED}→ Denied{Colors.RESET}")
            return False
        return answer in ("y", "yes")

    return _callback


# ── Spinner background task ──────────────────────────────────────────

_CLEAR_LINE = "\r" + " " * 100 + "\r"


async def _run_spinner(spinner: SpinnerEngine, start_time: float, message: str = "") -> None:
    """Animate spinner on its own line using \r until cancelled."""
    try:
        while True:
            elapsed = time.time() - start_time
            frame = spinner.render(elapsed, message)
            print(f"\r{frame}", end="", flush=True)
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        print(_CLEAR_LINE, end="", flush=True)
        raise


async def _stop_spinner(spinner_task: asyncio.Task[None] | None) -> None:
    """Cancel spinner task and wait for its cleanup (clear line) to finish."""
    if spinner_task is None:
        return
    spinner_task.cancel()
    try:
        await spinner_task
    except asyncio.CancelledError:
        pass


def _run_interactive(config: dict[str, Any]) -> None:
    """Run the interactive REPL loop.

    Uses FeinnTUI when prompt_toolkit is available (primary path),
    falls back to legacy PromptSession-based async REPL.
    """
    _ensure_builtins()

    try:
        from .cli_tui import FeinnTUI

        tui = FeinnTUI(config)
        tui._init_mcp = _init_mcp_for_tui
        tui._shutdown_mcp = shutdown_mcp
        tui.run()
    except ImportError:
        asyncio.run(_run_interactive_legacy_async(config))


def _init_mcp_for_tui(config: dict[str, Any]) -> None:
    """Initialize MCP for the TUI's agent thread."""
    init_mcp(config)


async def _run_interactive_legacy_async(config: dict[str, Any]) -> None:
    """Legacy interactive REPL using PromptSession (fallback path)."""
    from .agent import FeinnAgent

    _ensure_builtins()
    init_mcp(config)

    system = build_system_prompt(config)

    _cprint(display.show_welcome(config.get("model", "?")))

    perm_callback = _make_permission_callback(config)
    agent = FeinnAgent(config=config, system_prompt=system, permission_callback=perm_callback)

    FeinnCompleter.refresh_skills()

    # Initialize prompt_toolkit PromptSession with multi-line, completions, history
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.key_binding import KeyBindings

        history_dir = Path.home() / ".feinn"
        history_dir.mkdir(parents=True, exist_ok=True)
        history = FileHistory(str(history_dir / "history"))

        kb = KeyBindings()

        @kb.add("c-c")
        def _cancel_or_clear(event: Any) -> None:
            """Ctrl+C: clear buffer if not empty, otherwise exit."""
            buf = event.current_buffer
            if buf.text:
                buf.text = ""
            else:
                raise KeyboardInterrupt()

        session = PromptSession(
            history=history,
            completer=FeinnCompleter(),
            complete_while_typing=True,
            multiline=True,
            key_bindings=kb,
        )
        prompt_msg = HTML("<cyan><b>feinn> </b></cyan>")
        use_pt = True
    except ImportError:
        session = None
        use_pt = False
        prompt_msg = None

    while True:
        try:
            if use_pt:
                user_input = await session.prompt_async(prompt_msg)
            else:
                user_input = input(click.style("feinn> ", fg="cyan", bold=True))
        except (EOFError, KeyboardInterrupt):
            _cprint("\nBye!")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            handled = _handle_command(user_input, agent, config)
            if handled:
                continue

        skill_prompt = _try_handle_skill(user_input)
        if skill_prompt:
            user_input = skill_prompt

        spinner_task: asyncio.Task[None] | None = None
        spinner: SpinnerEngine | None = None
        spinner_start = 0.0

        try:
            thinking_content = ""

            async for event in agent.run(user_input):
                if isinstance(event, ThinkingChunk):
                    thinking_content += event.thinking
                    if spinner_task is None:
                        spinner = SpinnerEngine()
                        spinner_start = time.time()
                        spinner_task = asyncio.create_task(_run_spinner(spinner, spinner_start, "Thinking..."))

                elif isinstance(event, TextChunk):
                    await _stop_spinner(spinner_task)
                    spinner_task = None
                    print(event.text, end="", flush=True)

                elif isinstance(event, ToolStart):
                    await _stop_spinner(spinner_task)
                    print(render_tool_card(event.name, event.inputs, "running"))
                    spinner = SpinnerEngine()
                    spinner_start = time.time()
                    spinner_task = asyncio.create_task(_run_spinner(spinner, spinner_start, f"Running {event.name}..."))

                elif isinstance(event, ToolEnd):
                    await _stop_spinner(spinner_task)
                    spinner_task = None
                    status = "success" if event.permitted else "error"
                    print(render_tool_card(event.name, status=status))

                    if event.name in ("Write", "Edit") and event.permitted and event.result:
                        for line in event.result.splitlines():
                            if line.startswith("@@"):
                                diff_summary = render_diff_summary(event.result)
                                print(f"  {Colors.BRIGHT_BLACK}diff:{Colors.RESET} {diff_summary}")
                                break

                elif isinstance(event, TurnDone):
                    await _stop_spinner(spinner_task)
                    spinner_task = None

                elif isinstance(event, AgentDone):
                    await _stop_spinner(spinner_task)
                    spinner_task = None
                    print()
                    cost = 0.0
                    try:
                        from .providers import estimate_cost

                        cost = estimate_cost(
                            config["model"],
                            event.total_input_tokens,
                            event.total_output_tokens,
                        )
                    except Exception:
                        pass
                    print(
                        display.show_status_summary(
                            turn_count=event.turn_count,
                            input_tokens=event.total_input_tokens,
                            output_tokens=event.total_output_tokens,
                            cost=cost,
                        )
                    )
                    if thinking_content:
                        print(display.show_thinking_collapsed(thinking_content))

        except asyncio.CancelledError:
            print(f"{Colors.YELLOW}⏹  Interrupted{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")

    shutdown_mcp()


def _handle_command(cmd: str, agent: FeinnAgent, config: dict[str, Any]) -> bool:
    """Handle slash commands. Returns True if command was handled."""
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command in ("/quit", "/q", "/exit"):
        raise KeyboardInterrupt

    elif command in ("/help", "/h"):
        click.echo(click.style("\n  Commands:", fg="cyan", bold=True))
        for name, desc in [
            ("/help", "Show this help"),
            ("/quit", "Exit FeinnAgent"),
            ("/model", "Show or switch model"),
            ("/clear", "Clear conversation history"),
            ("/save", "Save session to file"),
            ("/tasks", "Show task list"),
            ("/memory", "Show memory list"),
            ("/skills", "List available skills"),
            ("/config", "Show current config"),
            ("/accept-all", "Auto-approve all tool calls"),
            ("/auto", "Auto-approve reads, ask for writes"),
            ("/manual", "Ask for every tool call"),
            ("/plan", "Show execution plan"),
            ("/checkpoint", "Manage checkpoints"),
            ("/interrupt", "Interrupt current execution"),
            ("/resume", "Resume interrupted execution"),
            ("/trajectory", "Show execution trajectory"),
        ]:
            click.echo(f"  {name:16s} {desc}")
        click.echo()
        click.echo(click.style("  Skills:", fg="cyan", bold=True))
        click.echo("  /commit          Create a git commit")
        click.echo("  /review          Review code or PR")
        click.echo("  /explain         Explain code in detail")
        click.echo("  /test            Generate tests for code")
        click.echo("  /doc             Generate documentation")
        click.echo()

    elif command == "/model":
        if args:
            config["model"] = args
            click.echo(f"Model set to: {args}")
        else:
            click.echo(f"Current model: {config['model']}")

    elif command == "/clear":
        agent.state.messages.clear()
        agent.state.turn_count = 0
        agent.state.total_input_tokens = 0
        agent.state.total_output_tokens = 0
        click.echo("Conversation cleared.")

    elif command == "/save":
        import json
        from pathlib import Path

        save_dir = Path.home() / ".feinn" / "sessions"
        save_dir.mkdir(parents=True, exist_ok=True)
        filepath = save_dir / f"{agent.state.session_id}.json"
        data = {
            "session_id": agent.state.session_id,
            "messages": [m.to_dict() for m in agent.state.messages],
            "config": {k: v for k, v in config.items() if not k.startswith("_")},
        }
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        click.echo(f"Session saved to {filepath}")

    elif command == "/tasks":
        from .task.store import task_list

        click.echo(task_list())

    elif command == "/memory":
        from .memory.store import list_memories

        for scope in ("user", "project"):
            names = list_memories(scope)
            if names:
                click.echo(f"\n  {scope} scope:")
                for n in names:
                    click.echo(f"    - {n}")
        if not any(list_memories(s) for s in ("user", "project")):
            click.echo("No memories saved.")

    elif command == "/skills":
        from .skill import load_skills

        skills = load_skills()
        if not skills:
            click.echo("No skills available.")
            return True

        click.echo(click.style("\n  Available Skills:", fg="cyan", bold=True))
        builtin_skills = []
        user_skills = []

        for skill in skills:
            if skill.origin_type == "builtin":
                builtin_skills.append(skill)
            else:
                user_skills.append(skill)

        if builtin_skills:
            click.echo(click.style("\n  Built-in:", fg="yellow"))
            for skill in builtin_skills:
                activators = ", ".join(skill.activators[:2])
                click.echo(f"  {activators:20s} {skill.summary}")

        if user_skills:
            click.echo(click.style("\n  Custom:", fg="yellow"))
            for skill in user_skills:
                activators = ", ".join(skill.activators[:2]) if skill.activators else f"/{skill.skill_id}"
                origin = f" ({skill.origin_type})" if skill.origin_type != "user" else ""
                click.echo(f"  {activators:20s} {skill.summary}{origin}")
        click.echo()

    elif command == "/config":
        import json

        safe = {k: v for k, v in config.items() if not k.startswith("_") and "key" not in k}
        click.echo(json.dumps(safe, indent=2, default=str))

    elif command == "/accept-all":
        config["permission_mode"] = PermissionMode.ACCEPT_ALL.value
        click.echo("Permission mode: accept-all")

    elif command == "/auto":
        config["permission_mode"] = PermissionMode.AUTO.value
        click.echo("Permission mode: auto")

    elif command == "/manual":
        config["permission_mode"] = PermissionMode.MANUAL.value
        click.echo("Permission mode: manual")

    elif command == "/plan":
        from .plan import PlanManager

        manager = PlanManager()
        plans = manager.list_plans()
        if not plans:
            click.echo("No execution plans found.")
        else:
            click.echo(click.style("\n  Execution Plans:", fg="cyan", bold=True))
            for plan in plans[:10]:
                status_color = {
                    "draft": "yellow",
                    "approved": "green",
                    "in_progress": "blue",
                    "completed": "green",
                    "aborted": "red",
                }.get(plan.status.value, "white")
                status_str = f"{click.style('[', fg='white')}"
                status_str += f"{click.style(plan.status.value, fg=status_color)}"
                status_str += f"{click.style(']', fg='white')}"
                click.echo(f"  {status_str} {plan.title}")
                click.echo(f"    ID: {plan.id}")
                click.echo(f"    Steps: {len(plan.steps)} | Created: {plan.created_at.strftime('%Y-%m-%d %H:%M')}")
            if len(plans) > 10:
                click.echo(f"\n  ... and {len(plans) - 10} more plans")

    elif command == "/checkpoint":
        import os

        from .checkpoint import CheckpointManager

        manager = CheckpointManager()
        working_dir = os.getcwd()
        checkpoints = manager.list_checkpoints(working_dir)
        if not checkpoints:
            click.echo("No checkpoints found for current directory.")
            click.echo("Use '/checkpoint save' to create a checkpoint.")
        else:
            click.echo(click.style("\n  Checkpoints:", fg="cyan", bold=True))
            for ckpt in checkpoints[-10:]:
                click.echo(f"  {ckpt.id} | {ckpt.message[:40]}")
                click.echo(f"    Files: {ckpt.file_count} | Created: {ckpt.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

    elif command == "/interrupt":
        from .interrupt import set_interrupt

        set_interrupt("User requested interrupt")
        click.echo(click.style("🛑 Execution interrupted", fg="red"))
        click.echo("Use '/resume' to continue or start a new task.")

    elif command == "/resume":
        click.echo(click.style("⏳ To resume execution, start a new query.", fg="yellow"))
        click.echo("Note: Resume functionality requires session state preservation.")

    elif command == "/trajectory":
        from .trajectory import TrajectoryRecorder

        trajectories = TrajectoryRecorder.list_trajectories()
        if not trajectories:
            click.echo("No execution trajectories found.")
        else:
            click.echo(click.style("\n  Recent Trajectories:", fg="cyan", bold=True))
            for traj_path in trajectories[:5]:
                click.echo(f"  {traj_path.name}")

    else:
        # Not a known command - let caller check for skill activator
        return False

    return True


def _try_handle_skill(user_input: str) -> str | None:
    """Check if input matches a skill activator and return rendered template.

    Args:
        user_input: Raw user input

    Returns:
        Rendered skill template if matched, None otherwise
    """
    from .skill import find_skill, render_template

    skill = find_skill(user_input)
    if skill:
        # Extract params after the activator
        parts = user_input.split(maxsplit=1)
        params = parts[1] if len(parts) > 1 else ""

        # Render template with params
        rendered = render_template(skill.template, params, skill.param_names)
        return rendered

    return None


# ── Click CLI ───────────────────────────────────────────────────────


@click.command()
@click.argument("prompt", required=False)
@click.option("--model", "-m", default=None, help="Model to use")
@click.option("--accept-all", is_flag=True, help="Auto-approve all tool calls")
@click.option("--interactive", "-i", is_flag=True, help="Start interactive REPL mode")
@click.option("--serve", is_flag=True, help="Start API server instead of REPL")
@click.option("--host", default=None, help="Server host")
@click.option("--port", default=None, type=int, help="Server port")
@click.option("--thinking", is_flag=True, help="Enable extended thinking")
@click.option("--config-file", default=None, help="Path to config file")
def main(
    prompt: str | None,
    model: str | None,
    accept_all: bool,
    interactive: bool,
    serve: bool,
    host: str | None,
    port: int | None,
    thinking: bool,
    config_file: str | None,
) -> None:
    """FeinnAgent — Enterprise-grade async AI agent.

    Usage:
        feinn "your question"     # One-shot mode
        feinn -i                  # Interactive REPL mode
        feinn --serve             # Start API server
    """
    config = load_config()

    if serve:
        setup_logging(config)
    else:
        setup_logging(config, quiet=True)

    # Apply CLI overrides
    if model:
        config["model"] = model
    if accept_all:
        config["permission_mode"] = PermissionMode.ACCEPT_ALL.value
    if thinking:
        config["thinking_enabled"] = True
    if host:
        config["server_host"] = host
    if port:
        config["server_port"] = port

    if serve:
        from .server import run_server

        run_server(config)
    elif interactive or (not prompt and not serve):
        # Interactive REPL (default when no prompt provided)
        _run_interactive(config)
    else:
        # One-shot mode
        _run_oneshot(prompt, config)


def _run_oneshot(prompt: str, config: dict[str, Any]) -> None:
    """Run a single query with enhanced display (tool cards, diff, spinner).

    Uses FeinnTUI for the TUI chrome, then exits after agent completes.
    """
    _ensure_builtins()

    try:
        from .cli_tui import FeinnTUI

        tui = FeinnTUI(config)
        tui._init_mcp = _init_mcp_for_tui
        tui._shutdown_mcp = shutdown_mcp
        tui.run(prompt)
    except ImportError:
        asyncio.run(_run_oneshot_legacy(prompt, config))


async def _run_oneshot_legacy(prompt: str, config: dict[str, Any]) -> None:
    """Legacy one-shot mode using async print (fallback path)."""
    from .agent import FeinnAgent

    _ensure_builtins()
    init_mcp(config)

    system = build_system_prompt(config)
    agent = FeinnAgent(config=config, system_prompt=system)

    spinner_task: asyncio.Task[None] | None = None
    spinner: SpinnerEngine | None = None
    spinner_start = 0.0

    try:
        async for event in agent.run(prompt):
            if isinstance(event, ThinkingChunk):
                if spinner_task is None:
                    spinner = SpinnerEngine()
                    spinner_start = time.time()
                    spinner_task = asyncio.create_task(_run_spinner(spinner, spinner_start, "Thinking..."))

            elif isinstance(event, TextChunk):
                await _stop_spinner(spinner_task)
                spinner_task = None
                print(event.text, end="", flush=True)

            elif isinstance(event, ToolStart):
                await _stop_spinner(spinner_task)
                spinner_task = None
                print(render_tool_card(event.name, event.inputs, "running"))
                spinner = SpinnerEngine()
                spinner_start = time.time()
                spinner_task = asyncio.create_task(_run_spinner(spinner, spinner_start, f"Running {event.name}..."))

            elif isinstance(event, ToolEnd):
                await _stop_spinner(spinner_task)
                spinner_task = None
                status = "success" if event.permitted else "error"
                print(render_tool_card(event.name, status=status))

            elif isinstance(event, AgentDone):
                await _stop_spinner(spinner_task)
                spinner_task = None
                print()
    except Exception as e:
        print(f"\nError: {e}")

    if spinner_task is not None:
        spinner_task.cancel()
    shutdown_mcp()


if __name__ == "__main__":
    main()
