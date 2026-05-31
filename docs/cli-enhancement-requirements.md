# CLI Enhancement — Requirements Document

## Harness Engineering Framework

### Guide (前置引导)

The FeinnAgent CLI (`feinn`) is the primary user interface for the agent.
Currently it uses a minimal `prompt_toolkit.PromptSession` for input and
`click.echo()` for output. User feedback and comparison with Hermes Python CLI
have identified the following gaps:

| Area | Current State | Target State |
|------|---------------|--------------|
| Input | Single-line, no completion, no history persistence | Multi-line, Tab completion, Ctrl-R history search, @path completion |
| Tool Display | Raw text, no structure, no spinner | Rich tool cards with spinner, elapsed time, collapsible output |
| Permission | Plain `y/n/A` prompt, no diff preview | Interactive approval panel with diff preview, session allowlist |
| Error Recovery | Bare `[Error]` text | Structured errors with recovery suggestions, crash logs |
| Diff Display | Raw unified-diff text in tool output | Formatted inline diff with syntax highlighting, collapsible |
| Status | Static text | Animated kawaii face spinner + elapsed timer + bottom status bar |

### Sensor (后置检测)

The following quality gates must pass before marking this feature complete:

1. **Correctness**: All existing tests pass (pre-existing failures: 14, same count).
2. **Robustness**: CLI survives terminal resize, SIGINT, SIGTERM without ghost output.
3. **Usability**: A new user can discover Tab completion, Ctrl-R history, and Alt-Enter multi-line without reading docs.
4. **Persistence**: History survives across sessions (`~/.feinn/history`).
5. **Permission**: Interactive approval correctly blocks dangerous commands (`rm -rf /`, etc.).
6. **Lint & Typecheck**: `ruff` passes with no new violations.

### Feedback Loop (反馈循环)

```
User types → Agent processes → Events emitted → Display renders
                                                  ↓
       User sees spinner + tool cards + status bar
                                                  ↓
       User hits Ctrl-C → Agent interrupted → Clean state
                                                  ↓
       User hits Tab → Completion suggestions shown
```

---

## Functional Requirements

### FR-1: Input Experience

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | **Multi-line input**: Alt+Enter inserts newline; Enter submits | P0 |
| FR-1.2 | **Tab completion**: Commands (`/commit`, `/help`), files (`./`, `~/`, `/`), skills, @-references | P0 |
| FR-1.3 | **History persistence**: `FileHistory` at `~/.feinn/history`; Ctrl-R reverse search | P0 |
| FR-1.4 | **@path completion**: `@file:` / `@folder:` / `@git:` prefixes trigger path completion | P1 |
| FR-1.5 | **Large paste handling**: Pastes >5 lines collapsed to `[Pasted text #N]` file reference | P1 |
| FR-1.6 | **Syntax highlighting**: Input area has a `Lexer` for basic highlighting | P2 |

### FR-2: Tool Display

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.1 | **ToolStart event**: Agent emits `ToolStart` with name + inputs | P0 |
| FR-2.2 | **ToolEnd event**: Agent emits `ToolEnd` with name + result | P0 |
| FR-2.3 | **Tool card**: Display tool name, args summary, and spinning indicator during execution | P0 |
| FR-2.4 | **Collapsible output**: Long tool results show first N lines with `[+N more lines]` toggle | P1 |
| FR-2.5 | **Tool emoji**: Each tool gets a contextual emoji (⚡ for Bash, 📝 for Write, etc.) | P1 |

### FR-3: Permission UI

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | **Interactive approval panel**: Bordered panel with tool name, args, and numbered choices | P0 |
| FR-3.2 | **Diff preview**: Before approving Write/Edit, show a unified diff | P1 |
| FR-3.3 | **Session allowlist**: "Allow for this session" option bypasses future prompts for same tool | P1 |
| FR-3.4 | **Countdown timer**: Auto-deny after configurable timeout (default 120s) | P2 |

### FR-4: Error Recovery

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | **Structured error display**: Error panel with icon + message + suggestion | P0 |
| FR-4.2 | **Animated spinner**: During LLM streaming and tool execution, show a spinning indicator | P0 |
| FR-4.3 | **Kawaii face rotation**: Rotate through faces `(｡◕‿◕｡) → (◕‿◕✿) → ...` | P1 |
| FR-4.4 | **Elapsed time**: Spinner shows `(MM:SS)` elapsed time | P1 |
| FR-4.5 | **Crash recovery**: SIGWINCH restores clean state; Ctrl+C interrupts agent cleanly | P1 |

### FR-5: Inline Diff

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | **Auto-diff**: After Write/Edit tool, extract and display unified diff | P0 |
| FR-5.2 | **Color-coded**: Additions green, deletions red, headers cyan | P0 |
| FR-5.3 | **Collapsible**: Show summary line; expand on demand | P2 |
| FR-5.4 | **File-scoped**: Each file's diff shown separately with file header | P1 |

---

## Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | **Backward compatibility** | All existing tests pass unchanged |
| NFR-2 | **Terminal width adaptation** | Graceful degradation down to 60 columns |
| NFR-3 | **Startup time** | CLI prompt appears within 500ms |
| NFR-4 | **Resource usage** | Idle CLI uses < 10MB RSS |
| NFR-5 | **Thread safety** | All display ops from agent thread via `run_in_terminal()` |

---

## Out of Scope (v1)

- Rich Markdown rendering (keep raw text for now)
- Image rendering in terminal (iTerm2/Kitty protocols)
- Fuzzy search for skills/memory
- `/bug-report` diagnostic command
- Plugin system for themes
