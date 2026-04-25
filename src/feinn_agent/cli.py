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
from typing import TYPE_CHECKING, Any

import click

from .config import load_config, setup_logging
from .context import build_system_prompt

if TYPE_CHECKING:
    from .agent import FeinnAgent
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


def _ensure_builtins() -> None:
    """Ensure all tool modules are imported so they register."""
    # Import and register builtin skills
    from .skill import register_builtin_skills

    register_builtin_skills()


async def _run_interactive(config: dict[str, Any]) -> None:
    """Run the interactive REPL loop."""
    from .agent import FeinnAgent

    _ensure_builtins()
    init_mcp(config)

    system = build_system_prompt(config)

    # Welcome banner
    click.echo(click.style("\n  FeinnAgent v0.1.0", fg="cyan", bold=True))
    click.echo(click.style(f"  Model: {config['model']}", fg="yellow"))
    click.echo(click.style("  Type '/quit' to exit, '/help' for commands\n", fg="bright_black"))

    agent = FeinnAgent(config=config, system_prompt=system)

    while True:
        try:
            # Read input
            user_input = input(click.style("feinn> ", fg="cyan", bold=True))
        except (EOFError, KeyboardInterrupt):
            click.echo("\nBye!")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            handled = _handle_command(user_input, agent, config)
            if handled:
                continue

        # Check for skill activator (e.g., "/weather", "/commit")
        skill_prompt = _try_handle_skill(user_input)
        if skill_prompt:
            # Replace user input with rendered skill template
            user_input = skill_prompt

        # Run agent
        try:
            tool_depth = 0
            thinking_shown = False
            thinking_content = ""
            
            async for event in agent.run(user_input):
                if isinstance(event, TextChunk):
                    click.echo(event.text, nl=False)
                elif isinstance(event, ThinkingChunk):
                    if not thinking_shown:
                        thinking_shown = True
                        thinking_content = event.thinking
                elif isinstance(event, ToolStart):
                    tool_depth += 1
                    if tool_depth == 1:
                        click.echo(click.style("\n⚡ ", fg="yellow"), nl=False)
                        click.echo(click.style(f"[{event.name}]", fg="cyan", bold=True), nl=False)
                        first_val = next(iter(event.inputs.values()), "")
                        if isinstance(first_val, str) and len(first_val) > 50:
                            first_val = first_val[:50] + "..."
                        if first_val:
                            click.echo(click.style(f" {first_val}", fg="bright_black"), nl=False)
                elif isinstance(event, ToolEnd):
                    tool_depth -= 1
                    if tool_depth == 0:
                        click.echo(click.style(" ✅", fg="green"), nl=False)
                elif isinstance(event, TurnDone):
                    pass
                elif isinstance(event, AgentDone):
                    click.echo()
                    if thinking_content:
                        click.echo(click.style(f"💭 {thinking_content[:200]}...", fg="bright_black"))
                        thinking_content = ""
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
                    tokens_str = f"{event.total_input_tokens}in + {event.total_output_tokens}out"
                    if cost > 0:
                        tokens_str += f" (${cost:.4f})"
                    click.echo(
                        click.style(f"📊 {tokens_str} | {event.turn_count} turns", fg="bright_black")
                    )
        except Exception as e:
            click.echo(click.style(f"\n❌ Error: {e}", fg="red"))

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
                status_color = {"draft": "yellow", "approved": "green", "in_progress": "blue", "completed": "green", "aborted": "red"}.get(plan.status.value, "white")
                click.echo(f"  {click.style('[', fg='white')}{click.style(plan.status.value, fg=status_color)}{click.style(']', fg='white')} {plan.title}")
                click.echo(f"    ID: {plan.id}")
                click.echo(f"    Steps: {len(plan.steps)} | Created: {plan.created_at.strftime('%Y-%m-%d %H:%M')}")
            if len(plans) > 10:
                click.echo(f"\n  ... and {len(plans) - 10} more plans")

    elif command == "/checkpoint":
        from .checkpoint import CheckpointManager
        import os
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
        from .trajectory import TrajectoryRecorder, TrajectoryAnalyzer
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
        asyncio.run(_run_interactive(config))
    else:
        # One-shot mode
        asyncio.run(_run_oneshot(prompt, config))


async def _run_oneshot(prompt: str, config: dict[str, Any]) -> None:
    """Run a single query and print the result."""
    from .agent import FeinnAgent

    _ensure_builtins()
    init_mcp(config)

    system = build_system_prompt(config)
    agent = FeinnAgent(config=config, system_prompt=system)

    try:
        async for event in agent.run(prompt):
            if isinstance(event, TextChunk):
                click.echo(event.text, nl=False)
            elif isinstance(event, AgentDone):
                click.echo()  # final newline
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)

    shutdown_mcp()


if __name__ == "__main__":
    main()
