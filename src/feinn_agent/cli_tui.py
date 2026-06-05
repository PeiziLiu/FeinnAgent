"""FeinnAgent TUI — prompt_toolkit Application with background-thread agent.

Architecture
────────────
Main thread:  prompt_toolkit Application event loop (input, rendering)
Agent thread: asyncio.run(agent.run(prompt)) → pushes output via run_in_terminal()
Spinner thread: periodic app.invalidate() for live animation

Usage:
    tui = FeinnTUI(config)
    tui.run()           # Interactive REPL
    tui.run("prompt")   # One-shot query
"""

from __future__ import annotations

import asyncio
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .display import (
    Colors,
    SpinnerEngine,
    render_diff_summary,
    render_diff_text,
    render_tool_line,
)
from .types import (
    AgentDone,
    AgentEvent,
    PermissionMode,
    TextChunk,
    ThinkingChunk,
    ToolEnd,
    ToolStart,
    TurnDone,
)

if TYPE_CHECKING:
    from .agent import FeinnAgent

_CLEAR_LINE = "\r" + " " * 100 + "\r"

# ── lazily-imported prompt_toolkit symbols ──────────────────────────


def _import_pt():
    """Import prompt_toolkit symbols lazily. Returns module or None."""
    try:
        from prompt_toolkit.patch_stdout import patch_stdout
        from prompt_toolkit import print_formatted_text as _pt_print
        from prompt_toolkit.application import Application
        from prompt_toolkit.formatted_text import ANSI as _PT_ANSI
        from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl, ConditionalContainer, Dimension
        from prompt_toolkit.layout.menus import CompletionsMenu
        from prompt_toolkit.widgets import TextArea
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.styles import Style as PTStyle
        from prompt_toolkit.history import FileHistory

        return {
            "patch_stdout": patch_stdout,
            "print_formatted_text": _pt_print,
            "Application": Application,
            "ANSI": _PT_ANSI,
            "Layout": Layout,
            "HSplit": HSplit,
            "Window": Window,
            "FormattedTextControl": FormattedTextControl,
            "ConditionalContainer": ConditionalContainer,
            "Dimension": Dimension,
            "CompletionsMenu": CompletionsMenu,
            "TextArea": TextArea,
            "KeyBindings": KeyBindings,
            "Condition": Condition,
            "PTStyle": PTStyle,
            "FileHistory": FileHistory,
        }
    except ImportError:
        return None


class FeinnTUI:
    """Interactive TUI using prompt_toolkit Application(full_screen=False).

    Manages the layout, agent execution thread, spinner animation,
    status bar, input area, and approval panel.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

        # ── Lazy prompt_toolkit imports ──────────────────────────
        pt = _import_pt()
        if pt is None:
            raise ImportError("prompt_toolkit is required for FeinnTUI. Install with: pip install prompt_toolkit")
        self._pt = pt

        # ── Agent state ──────────────────────────────────────────
        self._agent: FeinnAgent | None = None
        self._agent_running = False
        self._agent_thread: threading.Thread | None = None
        self._interrupt_requested = False
        self._agent_result: str | None = None

        # ── Spinner state ────────────────────────────────────────
        self._spinner = SpinnerEngine()
        self._spinner_text = ""
        self._spinner_running = False
        self._spinner_thread: threading.Thread | None = None
        self._tool_start_time: float = 0.0
        self._tool_state: dict[str, dict] = {}
        self._thinking_mode = False
        self._response_box_open = False
        self._response_md_buffer: str = ""

        # ── Status bar state ─────────────────────────────────────
        self._session_start = time.time()
        self._model_name: str = config.get("model", "?")
        self._turn_count = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._status_bar_visible = True

        # ── Approval state ───────────────────────────────────────
        self._approval_state: dict[str, Any] | None = None

        # ── Application ──────────────────────────────────────────
        self._app: Any = None
        self._input_area: Any = None
        self._spinner_widget: Any = None
        self._status_bar_widget: Any = None
        self._approval_panel: Any = None

        # ── History ──────────────────────────────────────────────
        history_dir = Path.home() / ".feinn"
        history_dir.mkdir(parents=True, exist_ok=True)
        self._history_file = str(history_dir / "history")

        # ── Permission state ─────────────────────────────────────
        self._session_allowlist: set[str] = set()
        self._permission_mode = config.get("permission_mode", PermissionMode.AUTO.value)

        # ── Output buffer (batch streaming chunks to avoid per-chunk
        #    run_in_terminal round-trips) ───────────────────────────
        self._output_accumulator: str = ""
        self._output_lock = threading.Lock()
        self._flush_pending = False
        self._last_flush_time = time.time()

        # ── Externally set callbacks ─────────────────────────────
        self._on_exit: Callable[[], None] | None = None
        self._init_mcp: Callable[[dict], None] | None = None
        self._shutdown_mcp: Callable[[], None] | None = None

    # ── Public API ────────────────────────────────────────────────

    def run(self, prompt: str | None = None) -> None:
        """Run the TUI. If prompt is given, execute one-shot and exit.

        This is the main entry point — it blocks until the app exits.
        """
        layout = self._build_layout()
        kb = self._build_key_bindings()
        style = self._build_style()

        app = self._pt["Application"](
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=False,
            mouse_support=False,
        )
        self._app = app

        if prompt:
            self._run_one_shot(prompt)
        else:
            self._banner()
            with self._pt["patch_stdout"](app):
                app.run()

        self._join_threads()

    def stop(self) -> None:
        """Signal the TUI and agent to stop.

        Cancels the agent's main asyncio task so ``loop.run_until_complete``
        unblocks and the background thread can exit cleanly — avoids the
        "Task was destroyed but it is pending!" / ``aclose(): asynchronous
        generator is already running`` errors on shutdown.
        """
        self._agent_running = False
        self._spinner_running = False
        self._interrupt_requested = True

        # Cancel the agent's main task to unblock the event loop
        main_task = getattr(self, "_agent_main_task", None)
        if main_task is not None and not main_task.done():
            main_task.cancel()
        agent_loop = getattr(self, "_agent_loop", None)
        if agent_loop is not None and agent_loop.is_running():
            agent_loop.call_soon_threadsafe(agent_loop.stop)

        if self._app:
            try:
                self._app.exit()
            except Exception:
                pass

    # ── Layout ─────────────────────────────────────────────────────

    def _build_layout(self) -> Any:
        pt = self._pt

        self._spinner_widget = pt["Window"](
            content=pt["FormattedTextControl"](self._get_spinner_fragments),
            height=1,
            dont_extend_height=True,
        )

        self._status_bar_widget = pt["Window"](
            content=pt["FormattedTextControl"](self._get_status_bar_fragments),
            height=1,
            dont_extend_height=True,
        )

        self._input_area = pt["TextArea"](
            height=3,
            prompt="feinn> ",
            style="class:input-area",
            completer=self._build_completer(),
            complete_while_typing=True,
            multiline=True,
            wrap_lines=True,
        )

        input_rule = pt["Window"](height=1, char="─", style="class:input-rule")

        spacer = pt["Window"](height=pt["Dimension"](min=1))

        completions_menu = pt["CompletionsMenu"]()

        self._approval_panel = pt["ConditionalContainer"](
            content=pt["Window"](
                content=pt["FormattedTextControl"](self._get_approval_fragments),
                height=self._get_approval_height(),
                dont_extend_height=True,
            ),
            filter=pt["Condition"](lambda: self._approval_state is not None),
        )

        root = pt["HSplit"](
            [
                pt["Window"](height=0),
                pt["Window"](height=0),
                self._approval_panel,
                self._spinner_widget,
                spacer,
                self._status_bar_widget,
                input_rule,
                self._input_area,
                completions_menu,
            ]
        )

        return pt["Layout"](root)

    def _build_completer(self) -> Any:
        """Build a FeinnCompleter for the input area."""
        from .cli import FeinnCompleter

        FeinnCompleter.refresh_skills()
        return FeinnCompleter()

    # ── Key bindings ───────────────────────────────────────────────

    def _build_key_bindings(self) -> Any:
        pt = self._pt
        kb = pt["KeyBindings"]()

        @kb.add("enter", filter=pt["Condition"](self._is_input_mode))
        def _submit(event: Any) -> None:
            text = self._input_area.text.strip()
            if not text:
                return
            self._input_area.text = ""
            self._on_submit(text)

        @kb.add("escape", "enter", filter=pt["Condition"](self._is_input_mode))
        def _newline(event: Any) -> None:
            buf = self._input_area.buffer
            buf.insert_text("\n")

        @kb.add("c-c", filter=pt["Condition"](self._is_input_mode))
        def _cancel_or_clear(event: Any) -> None:
            buf = self._input_area.buffer
            if buf.text:
                buf.text = ""
            else:
                self.stop()

        @kb.add("c-c", filter=pt["Condition"](self._is_approval_mode))
        def _approval_interrupt(event: Any) -> None:
            if self._approval_state:
                self._approval_state["result"] = False
                self._approval_state["done"].set()
                self._approval_state = None
                self._invalidate()

        @kb.add("y", filter=pt["Condition"](self._is_approval_mode))
        def _approval_yes(event: Any) -> None:
            if self._approval_state:
                self._approval_state["result"] = True
                self._approval_state["done"].set()
                self._approval_state = None
                self._invalidate()

        @kb.add("n", filter=pt["Condition"](self._is_approval_mode))
        def _approval_no(event: Any) -> None:
            if self._approval_state:
                self._approval_state["result"] = False
                self._approval_state["done"].set()
                self._approval_state = None
                self._invalidate()

        @kb.add("a", filter=pt["Condition"](self._is_approval_mode))
        def _approval_always(event: Any) -> None:
            if self._approval_state:
                self._permission_mode = PermissionMode.ACCEPT_ALL.value
                self._approval_state["result"] = True
                self._approval_state["done"].set()
                self._approval_state = None
                self._invalidate()
                self._safe_output(f"{Colors.GREEN}→ Permission mode set to accept-all{Colors.RESET}")

        @kb.add("s", filter=pt["Condition"](self._is_approval_mode))
        def _approval_session(event: Any) -> None:
            if self._approval_state:
                tool_name = self._approval_state["request"].name
                self._session_allowlist.add(tool_name)
                self._approval_state["result"] = True
                self._approval_state["done"].set()
                self._approval_state = None
                self._invalidate()
                self._safe_output(f"{Colors.GREEN}→ {tool_name} allowed for this session{Colors.RESET}")

        @kb.add("c-c", filter=pt["Condition"](self._is_agent_running))
        def _interrupt_agent(event: Any) -> None:
            """Ctrl+C during agent execution: interrupt and return to prompt."""
            self._safe_output(f"{Colors.YELLOW}⏹  Interrupting...{Colors.RESET}")
            self.stop()

        return kb

    def _is_input_mode(self) -> bool:
        return not self._agent_running and self._approval_state is None

    def _is_approval_mode(self) -> bool:
        return self._approval_state is not None

    def _is_agent_running(self) -> bool:
        return self._agent_running

    # ── Style ──────────────────────────────────────────────────────

    def _build_style(self) -> Any:
        return self._pt["PTStyle"].from_dict(
            {
                "input-area": "bg:#1a1a2e #e0e0e0",
                "input-rule": "bg:#1a1a2e #4a4a6a",
                "status-bar": "bg:#1a1a2e #c0c0c0",
                "status-bar.text": "bg:#1a1a2e #888888",
                "spinner": "bg:#1a1a2e #87CEEB",
                "approval-border": "#CD7F32",
                "approval-title": "#FF8C00 bold",
                "approval-desc": "#FFF8DC bold",
                "approval-cmd": "#AAAAAA italic",
                "approval-choice": "#AAAAAA",
                "approval-selected": "#FFD700 bold",
                "completion-menu": "bg:#222244 #e0e0e0",
                "completion-menu.completion": "bg:#222244 #e0e0e0",
                "completion-menu.completion.current": "bg:#444488 #ffffff",
            }
        )

    # ── Banner ─────────────────────────────────────────────────────

    def _banner(self) -> None:
        from .display import KawaiiDisplay

        display = KawaiiDisplay()
        welcome = display.show_welcome(self._model_name)
        print(welcome)

    # ── Input submission ───────────────────────────────────────────

    def _flush_md_buffer(self) -> None:
        """Render accumulated markdown buffer through rich and flush to output."""
        if not self._response_md_buffer:
            return
        text = self._response_md_buffer
        self._response_md_buffer = ""
        try:
            from io import StringIO
            from rich.console import Console
            from rich.markdown import Markdown

            buf = StringIO()
            console = Console(file=buf, width=80, highlight=False, color_system="truecolor")
            console.print(Markdown(text.strip()))
            rendered = buf.getvalue()
            if rendered.strip():
                self._safe_output(f"\n{rendered}")
        except Exception:
            self._safe_output(text)

    def _on_submit(self, user_input: str) -> None:
        user_input = user_input.strip()
        if not user_input:
            return

        if user_input.startswith("/"):
            handled = self._handle_command(user_input)
            if handled:
                return

        skill_prompt = self._try_handle_skill(user_input)
        if skill_prompt:
            user_input = skill_prompt

        self._start_agent(user_input)

    def _start_agent(self, prompt: str) -> None:
        """Start the agent in a background thread."""
        from .agent import FeinnAgent
        from .context import build_system_prompt

        if self._agent is None:
            if self._init_mcp:
                self._init_mcp(self.config)
            system = build_system_prompt(self.config)
            self._agent = FeinnAgent(
                config=self.config,
                system_prompt=system,
                permission_callback=self._tui_permission_callback,
            )

        self._agent_running = True
        self._spinner_text = "Thinking..."
        self._thinking_mode = True
        self._tool_start_time = time.time()
        self._spinner_running = True

        self._agent_thread = threading.Thread(
            target=self._run_agent_thread,
            args=(prompt,),
            daemon=True,
        )
        self._agent_thread.start()

        self._spinner_thread = threading.Thread(
            target=self._spinner_loop,
            daemon=True,
        )
        self._spinner_thread.start()

    def _run_agent_thread(self, prompt: str) -> None:
        """Run the async agent in a background thread with its own event loop.

        Stores a reference to the main task so ``stop()`` can cancel it
        from the main thread.  On exit, cancels any remaining pending
        tasks and lets cancellations propagate before closing the loop.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        main_task = loop.create_task(self._async_run_agent(prompt))
        self._agent_main_task = main_task
        self._agent_loop = loop

        try:
            loop.run_until_complete(main_task)
        except asyncio.CancelledError:
            pass  # Expected on intentional interrupt
        except Exception as e:
            self._safe_output(f"{Colors.RED}❌ Agent error: {e}{Colors.RESET}")
        finally:
            # Cancel any remaining orphan tasks (should be none after
            # _safe_output fix, but be defensive)
            leftover = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for t in leftover:
                t.cancel()
            if leftover:
                try:
                    loop.run_until_complete(asyncio.gather(*leftover, return_exceptions=True))
                except Exception:
                    pass

            self._agent_running = False
            self._spinner_running = False
            self._spinner_text = ""
            self._invalidate()
            loop.close()
            self._agent_loop = None
            self._agent_main_task = None

    async def _async_run_agent(self, prompt: str) -> None:
        """Iterate over async generator events from agent.run()."""
        if self._agent is None:
            return

        thinking_content = ""

        try:
            async for event in self._agent.run(prompt):
                if self._interrupt_requested:
                    self._safe_output(f"{Colors.YELLOW}⏹  Interrupted{Colors.RESET}")
                    break

                if isinstance(event, ThinkingChunk):
                    thinking_content += event.thinking
                    self._spinner_text = "Thinking..."
                    self._thinking_mode = True
                    self._invalidate()

                elif isinstance(event, TextChunk):
                    if not self._response_box_open:
                        from .display import render_response_box_header

                        self._safe_output(render_response_box_header(self._model_name))
                        self._response_box_open = True
                    self._spinner_text = ""
                    # Accumulate for markdown rendering; flush on paragraph breaks
                    self._response_md_buffer += event.text
                    while "\n\n" in self._response_md_buffer:
                        parts = self._response_md_buffer.split("\n\n", 1)
                        self._response_md_buffer = parts[1]
                        completed = parts[0].strip()
                        if completed:
                            try:
                                from io import StringIO
                                from rich.console import Console
                                from rich.markdown import Markdown

                                buf = StringIO()
                                console = Console(file=buf, width=80, highlight=False, color_system="truecolor")
                                console.print(Markdown(completed))
                                rendered = buf.getvalue()
                                self._safe_output(rendered)
                            except Exception:
                                self._safe_output(completed + "\n")

                elif isinstance(event, ToolStart):
                    # Flush any pending markdown text before tool output
                    if self._response_md_buffer:
                        self._flush_md_buffer()
                    self._tool_state[event.name] = {
                        "time": time.time(),
                        "inputs": event.inputs,
                    }
                    self._spinner_text = f"Running {event.name}..."
                    self._thinking_mode = False
                    self._tool_start_time = time.time()
                    self._invalidate()

                elif isinstance(event, ToolEnd):
                    from .display import render_tool_line

                    stored = self._tool_state.pop(event.name, {})
                    start = stored.get("time", 0.0) or 0.0
                    duration = time.time() - start if start else 0.0
                    tool_status = "success" if event.permitted else "denied"
                    self._safe_output(render_tool_line(event.name, stored.get("inputs"), duration, tool_status))
                    self._spinner_text = ""
                    self._invalidate()

                    if event.name in ("Write", "Edit") and event.permitted and event.result:
                        for line in event.result.splitlines():
                            if line.startswith("@@"):
                                summary = render_diff_summary(event.result)
                                self._safe_output(f"  {Colors.BRIGHT_BLACK}diff:{Colors.RESET} {summary}")
                                break

                elif isinstance(event, TurnDone):
                    self._turn_count += 1
                    self._spinner_text = ""

                elif isinstance(event, AgentDone):
                    # Flush any remaining markdown text
                    self._flush_md_buffer()
                    self._total_input_tokens = event.total_input_tokens
                    self._total_output_tokens = event.total_output_tokens
                    self._spinner_text = ""
                    self._safe_output("")

                    cost = 0.0
                    try:
                        from .providers import estimate_cost

                        cost = estimate_cost(
                            self._model_name,
                            event.total_input_tokens,
                            event.total_output_tokens,
                        )
                    except Exception:
                        pass

                    from .display import KawaiiDisplay

                    display = KawaiiDisplay()
                    self._safe_output(
                        display.show_status_summary(
                            turn_count=event.turn_count,
                            input_tokens=event.total_input_tokens,
                            output_tokens=event.total_output_tokens,
                            cost=cost,
                        )
                    )
                    if thinking_content:
                        self._safe_output(display.show_thinking_collapsed(thinking_content))

        except asyncio.CancelledError:
            # Task cancellation from stop() — clean exit, no error message
            pass

        # If agent completed with empty spinner, clear it
        self._spinner_text = ""

    # ── One-shot mode ──────────────────────────────────────────────

    def _run_one_shot(self, prompt: str) -> None:
        """Run a single query with TUI chrome, then exit."""
        self._banner()
        self._start_agent(prompt)
        try:
            with self._pt["patch_stdout"](self._app):
                self._app.run()
        except KeyboardInterrupt:
            self._interrupt_requested = True

    # ── Spinner loop (background thread) ───────────────────────────

    def _spinner_loop(self) -> None:
        """Periodically invalidate the app & flush buffered output."""
        while self._spinner_running:
            time.sleep(0.1)
            self._invalidate()
            self._maybe_flush_buffered()
        self._invalidate()
        self._flush_output()

    def _maybe_flush_buffered(self) -> None:
        """Flush buffered output if it has been sitting >500 ms."""
        if not self._output_accumulator:
            return
        if time.time() - self._last_flush_time < 0.5:
            return
        self._last_flush_time = time.time()
        app = self._app
        if app is None:
            return
        try:
            app.loop.call_soon_threadsafe(self._flush_output)
        except Exception:
            pass

    # ── Thread-safe output ─────────────────────────────────────────

    def _safe_output(self, text: str, end: str = "\n") -> None:
        """Print text safely from any thread.

        **Every** cross-thread output goes through ``run_in_terminal``
        — never ``print()`` directly — so the Application's screen state
        stays consistent (no spinner chrome leaking into the scrollback,
        no cursor-pos corruption).

        *Streaming chunks (end=""):* accumulated in ``_output_accumulator``
        and flushed in a single ``run_in_terminal`` batch.

        *Complete lines (end="\n"):* also aggregated but *always*
        trigger an immediate flush so tool-card lines appear without
        waiting for the next streaming chunk.
        """
        app = self._app
        is_main = threading.current_thread() is threading.main_thread()
        no_app = app is None or not getattr(app, "_is_running", False)

        if no_app or is_main:
            self._raw_print(text + (end or ""))
            return

        # Cross-thread: accumulate text + end, schedule one flush
        with self._output_lock:
            self._output_accumulator += text + (end or "")
            need_schedule = end == "\n" or not self._flush_pending
            if need_schedule:
                self._flush_pending = True

        if need_schedule:
            try:
                app.loop.call_soon_threadsafe(self._flush_output)
            except Exception:
                with self._output_lock:
                    self._flush_pending = False
                self._raw_print(text + (end or ""))

    def _flush_output(self) -> None:
        """Flush accumulated output.

        With ``patch_stdout=True`` on the Application, ``print()`` from
        any thread automatically routes through ``StdoutProxy`` which
        writes above the chrome — no ``run_in_terminal`` needed, and
        no risk of interleaving with spinner redraws.
        """
        with self._output_lock:
            text = self._output_accumulator
            self._output_accumulator = ""
            self._flush_pending = False

        if not text:
            return

        self._last_flush_time = time.time()
        print(text, end="", flush=True)

    def _raw_print(self, text: str) -> None:
        """Direct print fallback."""
        print(text, end="", flush=True)

    # ── Approval callback (called from agent thread) ───────────────

    def _tui_permission_callback(self, request: Any) -> bool:
        """Permission callback that shows an approval panel.

        Called from the agent thread. Blocks until user responds.
        """
        if request.name in self._session_allowlist:
            return True

        if self._permission_mode == PermissionMode.ACCEPT_ALL.value:
            return True

        done = threading.Event()
        self._approval_state = {
            "request": request,
            "done": done,
            "result": False,
        }
        self._invalidate()

        done.wait()

        if self._permission_mode == PermissionMode.ACCEPT_ALL.value:
            return True
        return self._approval_state["result"] if self._approval_state else False

    # ── TUI fragment generators ────────────────────────────────────

    def _get_spinner_fragments(self) -> list[tuple[str, str]]:
        """Return styled fragments for the spinner line."""
        if not self._agent_running:
            return []

        elapsed = time.time() - self._tool_start_time if self._tool_start_time > 0 else 0
        frame = self._spinner.render(elapsed, self._spinner_text, self._thinking_mode)
        return [("class:spinner", frame)]

    def _get_status_bar_fragments(self) -> list[tuple[str, str]]:
        """Return styled fragments for the status bar."""
        if not self._status_bar_visible:
            return []

        from .display import render_status_bar

        duration = int(time.time() - self._session_start)
        text = render_status_bar(
            self._model_name,
            self._total_input_tokens,
            self._total_output_tokens,
            duration,
        )
        return [("class:status-bar.text", f" {text} ")]

    def _get_approval_height(self) -> int:
        """Dynamic approval panel height based on the number of arguments."""
        if self._approval_state is None:
            return 0
        n = len(self._approval_state.get("request", object()).inputs or {})
        return min(n + 5, 20)

    def _get_approval_fragments(self) -> list[tuple[str, str]]:
        """Return styled fragments for the approval panel."""
        if self._approval_state is None:
            return []

        request = self._approval_state["request"]
        fragments: list[tuple[str, str]] = [
            ("class:approval-border", "┌─ Permission Request ──────────────────────┐"),
            ("class:approval-title", f"│ Tool: {request.name}"),
        ]

        for key, val in request.inputs.items():
            if isinstance(val, str) and len(val) > 60:
                val = val[:60] + "..."
            fragments.append(("class:approval-desc", f"│ {key}: {val}"))

        fragments.append(("class:approval-border", "│"))
        fragments.append(("class:approval-choice", "│ Allow? (y)es | (n)o | (A)lways | (S)ession  "))
        fragments.append(("class:approval-border", "└──────────────────────────────────────────┘"))
        return fragments

    # ── Slash commands ─────────────────────────────────────────────

    def _handle_command(self, cmd: str) -> bool:
        """Handle slash commands. Returns True if handled."""
        parts = cmd.strip().split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        agent = self._agent

        if command in ("/quit", "/q", "/exit"):
            self.stop()
            return True

        elif command in ("/help", "/h"):
            self._safe_output("\n  Commands:")
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
                self._safe_output(f"  {name:16s} {desc}")
            self._safe_output("")
            self._safe_output("  Skills:")
            self._safe_output("  /commit          Create a git commit")
            self._safe_output("  /review          Review code or PR")
            self._safe_output("  /explain         Explain code in detail")
            self._safe_output("  /test            Generate tests for code")
            self._safe_output("  /doc             Generate documentation")
            self._safe_output("")
            return True

        elif command == "/model":
            if args:
                self._model_name = args
                self.config["model"] = args
                self._safe_output(f"Model set to: {args}")
            else:
                self._safe_output(f"Current model: {self._model_name}")
            return True

        elif agent and command == "/clear":
            agent.state.messages.clear()
            agent.state.turn_count = 0
            agent.state.total_input_tokens = 0
            agent.state.total_output_tokens = 0
            self._safe_output("Conversation cleared.")
            return True

        elif agent and command == "/save":
            import json

            save_dir = Path.home() / ".feinn" / "sessions"
            save_dir.mkdir(parents=True, exist_ok=True)
            filepath = save_dir / f"{agent.state.session_id}.json"
            data = {
                "session_id": agent.state.session_id,
                "messages": [m.to_dict() for m in agent.state.messages],
                "config": {k: v for k, v in self.config.items() if not k.startswith("_")},
            }
            filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            self._safe_output(f"Session saved to {filepath}")
            return True

        elif command == "/tasks":
            try:
                from .task.store import task_list

                self._safe_output(task_list())
            except Exception:
                self._safe_output("Task store not available.")
            return True

        elif command == "/memory":
            try:
                from .memory.store import list_memories

                for scope in ("user", "project"):
                    names = list_memories(scope)
                    if names:
                        self._safe_output(f"\n  {scope} scope:")
                        for n in names:
                            self._safe_output(f"    - {n}")
                if not any(list_memories(s) for s in ("user", "project")):
                    self._safe_output("No memories saved.")
            except Exception:
                self._safe_output("Memory store not available.")
            return True

        elif command == "/skills":
            try:
                from .skill import load_skills

                skills = load_skills()
                if not skills:
                    self._safe_output("No skills available.")
                    return True
                self._safe_output("\n  Available Skills:")
                for skill in skills:
                    activators = ", ".join(skill.activators[:2]) if skill.activators else skill.skill_id
                    self._safe_output(f"  {activators:20s} {skill.summary}")
                self._safe_output("")
            except Exception:
                self._safe_output("Skills not available.")
            return True

        elif command == "/config":
            import json

            safe = {k: v for k, v in self.config.items() if not k.startswith("_") and "key" not in k}
            self._safe_output(json.dumps(safe, indent=2, default=str))
            return True

        elif command == "/accept-all":
            self._permission_mode = PermissionMode.ACCEPT_ALL.value
            self.config["permission_mode"] = PermissionMode.ACCEPT_ALL.value
            self._safe_output("Permission mode: accept-all")
            return True

        elif command == "/auto":
            self._permission_mode = PermissionMode.AUTO.value
            self.config["permission_mode"] = PermissionMode.AUTO.value
            self._safe_output("Permission mode: auto")
            return True

        elif command == "/manual":
            self._permission_mode = PermissionMode.MANUAL.value
            self.config["permission_mode"] = PermissionMode.MANUAL.value
            self._safe_output("Permission mode: manual")
            return True

        elif command == "/interrupt":
            self._interrupt_requested = True
            self._safe_output(f"{Colors.RED}🛑 Execution interrupted{Colors.RESET}")
            return True

        return False

    def _try_handle_skill(self, user_input: str) -> str | None:
        """Check if input matches a skill activator."""
        try:
            from .skill import find_skill, render_template

            skill = find_skill(user_input)
            if skill:
                parts = user_input.split(maxsplit=1)
                params = parts[1] if len(parts) > 1 else ""
                return render_template(skill.template, params, skill.param_names)
        except Exception:
            pass
        return None

    # ── Helpers ────────────────────────────────────────────────────

    def _invalidate(self) -> None:
        """Thread-safe app invalidation for TUI redraw."""
        if self._app:
            try:
                self._app.invalidate()
            except Exception:
                pass

    def _join_threads(self, timeout: float = 2.0) -> None:
        """Wait for background threads to finish and flush remaining output."""
        if self._spinner_thread and self._spinner_thread.is_alive():
            self._spinner_thread.join(timeout=timeout)
        if self._agent_thread and self._agent_thread.is_alive():
            self._agent_thread.join(timeout=timeout)
        # Final flush of any buffered streaming output
        self._flush_output()
        if self._shutdown_mcp:
            self._shutdown_mcp()
