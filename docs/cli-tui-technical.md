# CLI TUI Enhancement — Technical Design Document

> Status: **Implemented** (src/feinn_agent/cli.py, src/feinn_agent/cli_tui.py, src/feinn_agent/display/)

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Main Thread                        │
│  prompt_toolkit Application(full_screen=False)       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Event Loop (asyncio)                          │ │
│  │  • Keyboard input processing                   │ │
│  │  • TUI rendering (incremental)                 │ │
│  │  • Key bindings dispatch                       │ │
│  └─────────────────────────────────────────────────┘ │
│                     │ call_soon_threadsafe            │
│                     ▼                                │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Agent Thread (threading.Thread)                │ │
│  │  • asyncio.run(agent.run(prompt))                │ │
│  │  • Pushes events → run_in_terminal() for output  │ │
│  │  • Calls app.invalidate() for spinner updates    │ │
│  │  • Blocks on queue for approval panel            │ │
│  └─────────────────────────────────────────────────┘ │
│                     │                                 │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Spinner Thread (threading.Thread)              │ │
│  │  • Every 0.1s: app.invalidate()                 │ │
│  │  • Updates spinner frame index                   │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

Two background threads + one main event loop:

| Thread | Role |
|--------|------|
| Main (asyncio) | Runs prompt_toolkit `Application` event loop, handles input, renders TUI chrome |
| Agent thread | Executes async `agent.run()` via `asyncio.run()`, pushes output through `run_in_terminal()` |
| Spinner thread | Periodically calls `app.invalidate()` to trigger TUI redraw |

## 2. Application Layout

```
┌─ Permission Panel ───────────────────┐  ← ConditionalContainer (hidden when no pending req)
│ Tool: Bash                           │
│ command: ls -la                      │
│ Allow? (y/n/A/s): _                  │
└──────────────────────────────────────┘
⠋ (｡◕‿◕｡) Thinking... (00:05)           ← Spinner widget (hidden when idle)

                                           ← Spacer (fills remaining scrollback area)

⚕ gpt-4o | ctx -- | --% | 00:01:23        ← Status bar (bottom)
───────────────────────────────────────    ← Input rule separator
feinn> _                                    ← TextArea (multi-line input)
```

Layout tree:
```
HSplit([
    Window(height=0),               ← top padding
    CONDITIONAL: approval_panel,    ← only when _approval_state is set
    spinner_widget,                  ← FormattedTextControl, hidden when idle
    spacer,                          ← Window(height=Dimension(min=1), fills space)
    status_bar,                      ← FormattedTextControl, always visible
    input_rule,                      ← Window(height=1, char="─")
    input_area,                      ← TextArea with Completer
    completions_menu,                ← CompletionsMenu overlay
])
```

### 2.1 Spinner Widget

- `FormattedTextControl` with a `get_spinner_text` callable
- Returns empty string when agent is not running
- Returns spinner frame + kawaii face + message + elapsed time when running
- Frame/face index incremented in spinner thread, rendered on invalidate

### 2.2 Status Bar

- `FormattedTextControl` with a `get_status_bar_text` callable
- Format: `⚕ {model} | {ctx_used}/{ctx_total} | {percent}% | {duration}`
- Auto-compacts on narrow terminals (< 52 cols)

### 2.3 Input Area

- `TextArea(height=3, multiline=True, wrap_lines=True)`
- Enter submits, Meta+Enter inserts newline
- `FeinnCompleter` for tab completion
- Ctrl+C clears buffer / exits

### 2.4 Approval Panel

- `ConditionalContainer` wrapping a bordered `Window`
- Visible when `self._approval_state is not None`
- Shows tool name, arguments, diff preview
- Options displayed as styled text at the bottom

## 3. Data Flow

### 3.1 User Input → Agent Execution

```
User types in TextArea, presses Enter
  → Key binding handler:
    1. Read text, clear TextArea
    2. Set _agent_running = True
    3. Start agent thread: threading.Thread(target=_run_agent, args=(text,))
    4. Start spinner thread: threading.Thread(target=_spinner_loop, daemon=True)
```

### 3.2 Agent Output → Terminal

```
Agent thread generates event (e.g. TextChunk)
  → _safe_output(text) is called
  → app.loop.call_soon_threadsafe(run_in_terminal, lambda: print(text))
  → Main thread pauses TUI chrome, prints text above input area, redraws
```

### 3.3 Spinner Updates

```
Spinner thread loop:
  while _agent_running:
    time.sleep(0.1)
    app.invalidate()  ← triggers FormattedTextControl._get_spinner_text()
```

### 3.4 Permission Approval

```
Agent calls _tui_permission_callback(request) [in agent thread]:
  1. Set _approval_state = {request, done: Event(), result: False}
  2. app.invalidate() → shows approval panel
  3. _approval_state["done"].wait()  ← blocks agent thread

User presses key [in main thread]:
  1. Key binding handler processes 'y'/'n'/'a'/'s'
  2. Sets _approval_state["result"] = True/False
  3. Sets _approval_state["done"].set()
  4. Clears _approval_state → panel hides
  5. app.invalidate()

Agent thread wakes up, returns result.
```

## 4. Thread-Safe Output

Two-tier mechanism:

1. **Background thread calls `_cprint(text)`:**
   - If app is running and caller is not on main thread:
     - `loop.call_soon_threadsafe(lambda: run_in_terminal(lambda: print(text)))`
   - If app is not running or caller is on main thread:
     - Direct `print(text)` is safe

2. **`run_in_terminal()` behavior:**
   - Temporarily hides the TUI input area
   - Prints text in the scrollback region (above the chrome)
   - Redraws the chrome cleanly

## 5. Error Handling

| Scenario | Handling |
|----------|----------|
| Agent thread raises exception | Set `_agent_running = False`, `_spinner_text = ""`, show error via `_cprint()` |
| Ctrl+C during agent execution | Set `_interrupt_requested = True`, agent checks this flag and stops |
| Terminal resize | prompt_toolkit handles automatically; `_status_bar_suppressed_after_resize` flag prevents duplicate chrome |
| TUI import errors | Graceful fallback to legacy `PromptSession` mode |
| Spinner thread crash | Daemon thread, doesn't block main execution |

## 6. Module API

### `cli_tui.py`

```
FeinnTUI(config: dict)
  .run(prompt: str | None = None) → None
  ._build_layout() → Layout
  ._build_key_bindings() → KeyBindings
  ._run_agent(user_input: str) → None          [agent thread entry]
  ._spinner_loop() → None                       [spinner thread entry]
  ._safe_output(text: str) → None               [cross-thread safe print]
  ._tui_permission_callback(request) → bool
  ._get_spinner_text() → list[StyleAndTextTuples]
  ._get_status_bar_text() → list[StyleAndTextTuples]
  ._invalidat() → None
```

## 7. Dependencies

- `prompt_toolkit >= 3.0` — `Application`, `Layout`, `HSplit`, `Window`, `FormattedTextControl`, `ConditionalContainer`, `TextArea`, `CompletionsMenu`, `KeyBindings`, `run_in_terminal`
- `threading` — Agent thread, spinner thread
- `queue` — Approval panel synchronization
- `asyncio` — Agent event loop in background thread

## 8. Implementation Order

1. Create `FeinnTUI` class with layout builder, key bindings, spinner/status bar rendering
2. Wire agent execution into background thread with event output
3. Implement approval panel with queue-based synchronization
4. Refactor `cli.py` `_run_interactive()` → `FeinnTUI.run()`
5. Graceful fallback: if prompt_toolkit unavailable, fall back to original PromptSession mode
6. Tests: mock-based tests for layout, spinner rendering, key bindings, approval flow
