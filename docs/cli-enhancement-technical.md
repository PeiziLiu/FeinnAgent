# CLI Enhancement — Technical Design Document

> Status: **Implemented** (src/feinn_agent/cli.py, src/feinn_agent/cli_tui.py, src/feinn_agent/display/)

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│  cli.py (main entry point)                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │  _run_interactive()                                 │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │  │
│  │  │ Input    │  │ Agent    │  │ Display          │ │  │
│  │  │ Handler  │→│ Loop     │→│ Renderer         │ │  │
│  │  │          │  │          │  │                  │ │  │
│  │  │ prompt_  │  │ Feinn    │  │ click.echo()     │ │  │
│  │  │ toolkit  │  │ Agent    │  │ prompt_toolkit   │ │  │
│  │  │ Session  │  │ .run()   │  │ print_formatted  │ │  │
│  │  └──────────┘  └──────────┘  └──────────────────┘ │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  display/__init__.py                                │  │
│  │  ┌────────────┐ ┌──────────┐ ┌──────────────────┐ │  │
│  │  │ Kawaii     │ │ Spinner  │ │ DiffDisplay      │ │  │
│  │  │ Display    │ │ Engine   │ │ (enhanced)       │ │  │
│  │  └────────────┘ └──────────┘ └──────────────────┘ │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Module Changes

### 1. `agent.py` — Emit ToolStart/ToolEnd Events

**Problem**: `ToolStart` and `ToolEnd` events are defined in `types.py` but
never yielded by `FeinnAgent.run()`. The CLI has dead code to handle them.

**Fix**: In `_execute_tools()` (the synchronous dispatcher), wrap each tool
call with `ToolStart`/`ToolEnd` yields. Since `_execute_tools` currently
runs tools synchronously (dispatches all at once), we need to change the
dispatch to emit events per-tool.

**Key changes**:
- `_execute_tools()` yields `ToolStart(name, inputs, call_id)` before each tool
- `_execute_tools()` yields `ToolEnd(name, result, call_id)` after each tool
- `ToolEnd.permitted` is `False` when permission denied

### 2. `display/__init__.py` — Spinner, Rich Display, Enhanced Diff

#### SpinnerEngine class

```python
class SpinnerEngine:
    """Animated spinner with kawaii faces and elapsed time."""

    FACES_WAITING = ["(｡◕‿◕｡)", "(◕‿◕✿)", "(◠‿◠)", "(ᵔ◡ᵔ)", "(•‿•)"]
    FACES_THINKING = ["(◕ ◡ ◕)", "(◉ ◡ ◉)", "(ﾉ◕ヮ◕)ﾉ", "(⌒ ‿ ⌒)"]
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def render(self, elapsed: float, message: str = "") -> str:
        """Return the current frame as a formatted string."""
```

Renders: `⠋ (｡◕‿◕｡) Searching files... (00:05)`

#### Enhanced tool display

- `show_tool_card(name, args, status="running")` — bordered box with emoji
- `show_tool_result(name, result, truncated=False)` — collapsible output
- Emoji map: `Bash→⚡`, `Read→📖`, `Write→📝`, `Edit→✏️`, `Glob→🔍`, etc.

#### Enhanced DiffDisplay

- `show_diff(diff_text)` — color-coded with file headers
- `show_diff_summary(diff_text)` — `+5 | ~3 | -1` one-liner
- Collapsible: summary by default, full on demand

### 3. `cli.py` — Full Prompt Toolkit TUI

#### Input Area

```python
class FeinnInput:
    """Multi-line input with completion, history, and @-path."""

    def __init__(self):
        self.history = FileHistory(Path.home() / ".feinn" / "history")
        self.completer = FeinnCompleter()  # commands + skills + @paths
        self.session = PromptSession(
            history=self.history,
            completer=self.completer,
            complete_while_typing=True,
            multiline=True,
            vi_mode=False,
        )
```

#### Completion

```python
class FeinnCompleter(Completer):
    """Completes: /commands, skills, @-references, file paths."""

    COMMANDS = ["/quit", "/help", "/clear", "/commit", "/review", "/explain",
                "/test", "/doc", "/accept-all", "/auto", "/manual", "/model"]
    SKILL_ACTIVATORS = [...]  # loaded from SkillLoader

    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor()
        if word.startswith("/"):
            yield from self._complete_command(word)
        elif word.startswith("@"):
            yield from self._complete_ref(word)
        elif any(word.startswith(p) for p in ("./", "../", "~/", "/")):
            yield from self._complete_path(word)
```

#### Event Loop Rewrite

Replace the current `async for event in agent.run():` + `click.echo()` pattern
with an event-driven approach:

```python
async for event in agent.run(user_input):
    if isinstance(event, TextChunk):
        _cprint(event.text, end="")
    elif isinstance(event, ThinkingChunk):
        _buffer_thinking(event.thinking)
    elif isinstance(event, ToolStart):
        _display_tool_card(event)
    elif isinstance(event, ToolEnd):
        _display_tool_result(event)
    elif isinstance(event, AgentDone):
        _display_summary(event)
        _display_thinking()
```

The `_cprint()` function routes output through prompt_toolkit's
`print_formatted_text(ANSI(...))` to avoid TUI corruption. Cross-thread calls
use `run_in_terminal()`.

#### Bottom Toolbar

```python
def _get_bottom_toolbar():
    """Show status: model name, elapsed time, token count."""
    if _thinking:
        return f" 🤔 {_spinner.render(_elapsed())}"
    if _running_tool:
        return f" {_tool_emoji} {_running_tool} {_spinner.render(_elapsed())}"
    return f" Model: {_model} | Tokens: {_tokens_in}↓ {_tokens_out}↑"
```

#### Key Bindings

| Key | Action |
|-----|--------|
| Enter | Submit (when input not empty) |
| Alt+Enter | Insert newline |
| Tab | Accept completion → complete |
| Ctrl+R | Reverse history search (built-in) |
| Ctrl+C | Interrupt agent / cancel |
| Ctrl+L | Clear screen |
| Ctrl+D | Exit (on empty input) |

### 4. Permission UI

```python
async def _approval_panel(request: PermissionRequest) -> bool:
    """Show interactive approval panel with preview."""
    choices = [
        ("1", "Allow once"),
        ("2", "Allow for this session"),
        ("3", "Show diff preview"),
        ("4", "Deny"),
    ]
    # Show bordered panel via click.echo
    # Wait for keypress via prompt_toolkit
    # Return True/False based on choice
```

**Diff preview** for Write/Edit: Before showing permission prompt, read the
current file content and generate a unified diff. Show it in a collapsed
format (`[±5 lines changed]`), expandable with `3`.

**Session allowlist**: A `set[str]` of tool names per session. Tools in the
allowlist are auto-approved without prompting.

## Implementation Order

1. **agent.py**: Emit ToolStart/ToolEnd events (independent, testable)
2. **display/__init__.py**: Add SpinnerEngine, enhance DiffDisplay
3. **cli.py**: Rewrite input handling (multi-line, Tab completion, FileHistory)
4. **cli.py**: Rewrite event loop with _cprint() and spinner
5. **cli.py**: Add permission UI with diff preview + session allowlist
6. **Write tests**: Test spinner, completions, permissions, events
7. **Regression check**: Run full test suite

## Testing Strategy

| Test Area | Approach |
|-----------|----------|
| ToolStart/ToolEnd events | Unit test agent with mock LLM, verify event sequence |
| SpinnerEngine | Snapshot test frame output at known elapsed times |
| FeinnCompleter | Test completions for /commands, @paths, file paths |
| Permission panel | Mock prompt_toolkit input, verify True/False routing |
| Inline diff | Feed sample diffs, verify color-coded output |
| CLI integration | Subprocess test: `echo "input" | feinn` one-shot mode |
