# FeinnAgent Technical Reference

> Auto-generated from source code. Last updated: 2026-06-06

---

## 1. Technology Stack

### 1.1 Runtime

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | >=3.11 | Runtime (uses `from __future__ import annotations`, StrEnum backport) |
| asyncio | built-in | Async concurrency for agent loop, tool dispatch, LLM streaming |
| httpx | >=0.27 | Async HTTP (used by WebFetch tool) |

### 1.2 LLM SDKs

| SDK | Version | Provider |
|-----|---------|----------|
| anthropic | >=0.42 | Anthropic Claude (native streaming + thinking) |
| openai | >=1.50 | OpenAI + 13 compatible providers (Gemini, DeepSeek, Qwen, etc.) |

### 1.3 CLI & Server

| Component | Version | Purpose |
|-----------|---------|---------|
| click | >=8.1 | CLI argument parsing and command routing |
| prompt-toolkit | >=3.0 | Interactive REPL with multi-line, tab-completion, history |
| rich | >=13.9 | Terminal ANSI rendering (spinners, progress, formatting) |
| fastapi | >=0.115 | REST API framework |
| uvicorn | >=0.30 | ASGI server for FastAPI |
| pydantic | >=2.9 | API request/response models (server.py only — core uses dataclasses) |

### 1.4 Storage & Data

| Component | Version | Purpose |
|-----------|---------|---------|
| pyyaml | >=6.0 | YAML frontmatter parsing (memory entries, skill templates) |
| aiofiles | >=24.1 | Async file I/O for non-blocking reads |
| python-dotenv | >=1.0 | `.env` file loading |

### 1.5 Development

| Component | Version | Purpose |
|-----------|---------|---------|
| pytest | >=8.3 | Testing framework |
| pytest-asyncio | >=0.24 | Async test support (auto mode) |
| pytest-cov | >=5.0 | Coverage reporting |
| ruff | >=0.6 | Linting + formatting |

### 1.6 What We DON'T Use

The following are **not used** — the codebase intentionally avoids them:

- ❌ SQLAlchemy / aiosqlite — storage uses sqlite3, JSON files, and YAML frontmatter directly
- ❌ tiktoken — token estimation uses `chars / 3.0` heuristic
- ❌ tenacity — retry logic is manual (3 attempts, exponential backoff)
- ❌ mypy — not currently configured (type hints are for documentation only)
- ❌ Pydantic for core types — core types are `dataclass` (Pydantic only in `server.py`)
- ❌ aiohttp — all HTTP uses `httpx`
- ❌ Prometheus / structlog — monitoring uses stdlib `logging`

---

## 2. Module Reference

### 2.1 Core Types (`types.py`)

All core data models use `dataclass` (not Pydantic):

```python
@dataclass
class Message:
    role: Role          # SYSTEM | USER | ASSISTANT | TOOL
    content: str
    tool_calls: list[ToolCall]
    tool_call_id: str
    tool_name: str
    images: list[dict[str, str]]
    reasoning: str      # thinking/reasoning content

@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]

@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable
    read_only: bool
    concurrent_safe: bool
    destructive: bool
    requires_env: list[str]
    max_result_chars: int
```

**Stream event types** (all `dataclass`, yielded by `FeinnAgent.run()`):

| Event | When | Fields |
|-------|------|--------|
| `TextChunk` | LLM streaming text | text: str |
| `ThinkingChunk` | Reasoning/thinking block | thinking: str |
| `ToolStart` | Before tool execution | name, inputs, call_id |
| `ToolEnd` | After tool execution | name, result, call_id, permitted |
| `PermissionRequest` | User needs to approve | name, inputs, call_id, granted |
| `AssistantTurn` | Complete LLM turn | text, reasoning, tool_calls, input_tokens, output_tokens |
| `TurnDone` | One turn (with tools) finished | input_tokens, output_tokens |
| `AgentDone` | Agent loop finished | total_input_tokens, total_output_tokens, turn_count |

Union type: `AgentEvent = Union[TextChunk, ThinkingChunk, ToolStart, ToolEnd, PermissionRequest, TurnDone, AgentDone, AssistantTurn]`

### 2.2 Configuration (`config.py`)

Three-layer priority (highest wins):

1. **Environment variables** — loaded from `.env` or `~/.feinn/.env` via `python-dotenv`
2. **Config file** — `~/.feinn/config.json` (JSON, not YAML)
3. **Hardcoded defaults** — `_DEFAULTS` dict in `config.py`

Config is a plain `dict[str, Any]` — no Settings class.

Key defaults:

```python
{
    "model": "anthropic/claude-sonnet-4-20250514",
    "max_tokens": 16384,
    "max_iterations": 50,
    "permission_mode": "accept-all",
    "compaction_threshold": 0.70,
    "compaction_preserve_last_n": 6,
    "max_tool_output_chars": 32_000,
    "max_concurrent_agents": 5,
    "max_agent_depth": 3,
    "thinking_enabled": False,
    "thinking_budget": 10_000,
    "server_host": "0.0.0.0",
    "server_port": 8000,
    "log_level": "INFO",
}
```

API keys are mapped via `_ENV_MAP` from config keys to `FEINN_*` environment variables:

```python
_ENV_MAP = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
    "siliconflow_api_key": "SILICONFLOW_API_KEY",
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "azure_api_key": "AZURE_OPENAI_API_KEY",
    # ... and more
}
```

### 2.3 Provider Layer (`providers.py`)

Single streaming entry point with two code paths:

```
stream(model, system, messages, tool_schemas, config)
    ├── detect_provider(model) → ProviderInfo
    ├── if anthropic → _stream_anthropic()
    │   └── AsyncAnthropic SDK → TextChunk | ThinkingChunk | AssistantTurn
    └── else → _stream_openai_compat()
        └── AsyncOpenAI SDK → TextChunk | ThinkingChunk (via reasoning_content) | AssistantTurn
```

**Provider auto-detection** maps model name → provider:

| Pattern | Provider | Context Limit |
|---------|----------|---------------|
| `claude` / `anthropic/` | anthropic | 200K |
| `gpt` / `o[1-4]` / `openai/` | openai | 128K |
| `gemini` / `google/` | gemini | 1M |
| `qwen` | qwen | 1M |
| `deepseek` | deepseek | 128K |
| `kimi` | kimi | 128K |
| `moonshot` | moonshot | 128K |
| `siliconflow/` | siliconflow | 128K |
| `openrouter/` | openrouter | 200K |
| `ollama/` | ollama | 128K |
| `vllm/` | vllm | 128K |
| `lmstudio/` | lmstudio | 128K |
| `custom/` | custom | 128K |

**Anthropic path features**:
- Tool calling via native SDK streaming
- Extended thinking via `thinking` parameter
- Image support (base64)

**OpenAI-compat path features**:
- Single code path for all 13 providers
- `reasoning_content` support (Kimi, DeepSeek R1)
- Provider-specific headers (OpenRouter, Kimi)
- Azure OpenAI and vLLM API key handling

**Cost estimation**:

```python
_PRICING = {
    "claude-opus-4":  (15.0, 75.0),
    "claude-sonnet-4": (3.0, 15.0),
    "gpt-4o":          (2.50, 10.0),
    "gpt-4o-mini":     (0.15, 0.60),
    "gemini-2.5-pro":  (1.25, 10.0),
    "deepseek-v3":     (0.27, 1.10),
}
```

### 2.4 Context Assembly (`context.py`)

**Not** a context manager class — a single function that builds the system prompt:

```python
def build_system_prompt(
    config: dict[str, Any],
    *,
    memory_context: str = "",
    project_context: str = "",
) -> str:
```

The prompt includes:
1. Base identity and core principles
2. Tool descriptions (auto-generated from registry)
3. Closed-loop learning guidance (configurable)
4. Environment info: date, cwd, platform
5. Git branch and status
6. Project context: `CLAUDE.md` / `FEINN.md` (project-level + user-level)
7. Memory context (from `memory/store.py`)

### 2.5 Compaction (`compaction.py`)

Three-layer strategy:

```
maybe_compact(state, config)
    │
    ├── Layer 1: Snip
    │   Trim old tool result messages to max_chars (head 50% + tail 25%)
    │   Preserves last N (default 6) tool messages untouched
    │   Cost: zero (no API call)
    │
    ├── Layer 2: Compact (truncation fallback)
    │   Keep first 2 messages (system/user) + last 30%
    │   Replace middle with summary marker
    │   Notifies on_compact callback with removed messages
    │
    └── Layer 3: Collapse (via force=True on context_length error)
        Same as Compact but triggered on LLM context_length error
```

Trigger: when estimated tokens exceed `compaction_threshold` (default 70%) of context limit.

Token estimation: `int(total_chars / 3.0) * 1.08` (8% safety buffer).

### 2.6 Tool Registry (`tools/registry.py`)

Simple dict-based registry:

```python
_tools: dict[str, ToolDef] = {}

register(tool_def: ToolDef)        # Register a tool
deregister(name: str)              # Remove a tool
get(name: str) → ToolDef | None    # Look up
all_tools() → list[ToolDef]        # All registered
tool_schemas() → list[dict]        # JSON schemas for LLM APIs

async dispatch(name, params, config) → str                     # Single tool
async dispatch_batch(calls, config) → list[str]                 # Batch with parallelization
```

**Batch dispatch optimization**:
- Tools with `concurrent_safe=True` AND `read_only=True` run in parallel via `asyncio.gather`
- All other tools run sequentially (one at a time)
- Results returned in call order

### 2.7 Permission System (`permission/__init__.py`)

Four modes, decided per-tool-call:

| Mode | Behavior |
|------|----------|
| `accept-all` | All tools auto-approved |
| `auto` | Read-only tools auto-approved; safe Bash commands auto-approved; destructive/write tools ask callback |
| `manual` | All tools ask callback |
| `plan` | Read-only auto-approved; Write/Edit allowed only for plan file; Bash safe commands auto-approved; everything else denied |

**Safe command whitelist**: 30+ patterns (ls, cat, git status, python --version, etc.)
**Unsafe command patterns**: 15+ patterns (rm -rf, git push --force, sudo, etc.)
**Bash auto-approval**: command must match a safe pattern AND not match any unsafe pattern.

### 2.8 Sub-agent System (`subagent/manager.py`)

Concurrent agent spawning with semaphore control:

```python
@dataclass
class AgentDefinition:
    name: str
    description: str
    system_prompt: str
    model: str           # empty = inherit from parent
    tools: list[str]     # empty = all tools
```

**5 built-in types**:

| Type | Purpose | Tool Restrictions |
|------|---------|-------------------|
| general-purpose | Versatile research and multi-step tasks | (all tools) |
| coder | Code implementation | (all tools) |
| reviewer | Code review | Read/Glob/Grep/Bash (read-only) |
| researcher | Information gathering | Read/Glob/Grep/WebFetch/Grep/MemorySearch/SessionSearch |
| tester | Test writing | Read/Glob/Grep/Bash/Write/Edit |

**Lifecycle**:
- `spawn()` → creates asyncio task → returns SubAgentTask (PENDING)
- Sub-agent runs isolated FeinnAgent with own state
- `check_result()` → polls for DONE/ERROR
- Semaphore (default 5) controls max concurrency
- Max depth (default 3) prevents infinite recursion

### 2.9 Memory System (`memory/store.py`)

Dual-scope, YAML-frontmatter storage:

| Scope | Path | Persistence |
|-------|------|-------------|
| user | `~/.feinn/memory/` | Cross-project, persists across sessions |
| project | `.feinn/memory/` | Repo-local |

**Memory entry format** (Markdown + YAML frontmatter):
```yaml
---
name: coding_style
description: Python formatting preferences
type: feedback          # user | feedback | project | reference
confidence: 0.95
source: user
last_used_at: 2026-04-11
conflict_group: coding_style
---
Content body...
```

**Search**: keyword-based with `confidence × recency` scoring.

### 2.10 Task System (`task/store.py`)

DAG task orchestration:

```python
class Task:
    id, subject, description, status
    active_form, owner
    blocks: list[str]       # tasks this task blocks
    blocked_by: list[str]   # tasks blocking this task
    metadata, created_at, updated_at
```

**Status lifecycle**: `pending → in_progress → completed | cancelled`

**Storage**: `.feinn/tasks.json`

**Tools**: TaskCreate, TaskUpdate, TaskList, TaskGet

### 2.11 Agent Loop (`agent.py`)

```python
async for event in FeinnAgent(config=...).run("user message"):
    ...
```

**Per-turn flow**:
```
User message → append to state
    → maybe_compact() (check threshold)
    → _stream_with_retry() (3 attempts, exponential backoff)
        → yields TextChunk / ThinkingChunk / AssistantTurn
    → append assistant message to state
    → yield TurnDone
    → if no tool calls: yield AgentDone, return
    → yield ToolStart for each tool
    → _execute_tools(): permission check → dispatch_batch()
    → yield ToolEnd for each tool
    → append tool results to state
    → learning hooks: trajectory, session store, nudge counters
    → loop back to LLM
```

**Learning hooks** (after each turn):
- Trajectory recorder (optional)
- Session store (SQLite FTS5, non-blocking)
- Nudge counter update (memory/skill intervals)
- Background review spawn (daemon thread when threshold reached)

### 2.12 Learning System (`learning/`)

| Module | File | Purpose |
|--------|------|---------|
| NudgeCounter | `nudge.py` | Tracks turns/tool-iterations, triggers review at configurable intervals |
| BackgroundReviewer | `review.py` | Daemon thread spawns review agent to extract memory/skill learnings |
| SessionStore | `session_store.py` | SQLite + FTS5, per-turn persistence with cross-session search |
| SessionSearch tool | `session_search.py` | FTS5 DISCOVER / SCROLL / BROWSE search modes |

### 2.13 MCP Integration (`mcp/client.py`)

Model Context Protocol client supporting:
- **stdio** transport (local MCP servers as subprocess)
- **SSE** transport (remote MCP servers over HTTP)
- **HTTP** transport (direct POST)

Auto-discovers and registers MCP tools into the FeinnAgent tool registry.

### 2.14 Checkpoint System (`checkpoint/__init__.py`)

Git-based snapshots:
- Shadow git repository in `.feinn/checkpoints/`
- Auto-checkpoints before file mutations
- Rollback to any previous checkpoint
- File exclusion patterns

### 2.15 Plan System (`plan/__init__.py`)

Markdown-based execution plans:
- Plan CRUD in `.feinn/plans/`
- Status lifecycle: pending → in_progress → completed / cancelled / skipped
- `/plan` command for viewing and management

### 2.16 Display System (`display/__init__.py`)

CLI visualization:
- Kawaii-style emoji display
- Spinner engine (10fps, animated)
- Tool cards (name, status, elapsed time)
- Unified diff display with color
- Progress bars and status indicators

---

## 3. File Structure

```
src/feinn_agent/
├── __init__.py              # Public API exports
├── agent.py                 # Core agent loop (341 lines)
├── cli.py                   # CLI entry point (Click, 814 lines)
├── cli_tui.py               # Terminal UI (prompt_toolkit, 1003 lines)
├── config.py                # Configuration (dict-based, 160 lines)
├── context.py               # System prompt assembly (182 lines)
├── compaction.py            # Context compression (186 lines)
├── providers.py             # LLM streaming (567 lines)
├── server.py                # FastAPI server (295 lines)
├── types.py                 # Core type definitions (216 lines)
│
├── tools/
│   ├── __init__.py
│   ├── registry.py          # Tool registration & dispatch (136 lines)
│   ├── builtins.py          # Read/Write/Edit/Bash/Glob/Grep/WebFetch/AskUser (449 lines)
│   ├── process.py           # Process execution & process-tree cleanup (210 lines)
│   ├── output.py            # Output truncation & diff generation (64 lines)
│   ├── tmux.py              # Tmux persistent session control (376 lines)
│   ├── diagnostics.py       # LSP-style code diagnostics (250 lines)
│   ├── skills.py            # Skill tool wrappers (287 lines)
│   ├── browser.py           # Browser automation (633 lines)
│   └── browser_providers/   # Provider implementations (local, browserbase, browseruse, firecrawl)
│
├── memory/
│   └── store.py             # Dual-scope YAML frontmatter memory (396 lines)
│
├── task/
│   └── store.py             # DAG task orchestration (399 lines)
│
├── skill/
│   ├── __init__.py
│   ├── loader.py            # Skill discovery & parsing (289 lines)
│   ├── builtin.py           # Built-in skills: /commit, /review, /explain, /test, /doc (246 lines)
│   ├── executor.py          # Skill execution (119 lines)
│   ├── auto_create.py       # Auto skill creation
│   ├── curator.py           # Skill curation
│   └── usage.py             # Skill usage tracking
│
├── subagent/
│   └── manager.py           # Concurrent sub-agent system (465 lines)
│
├── mcp/
│   └── client.py            # MCP protocol client (314 lines)
│
├── learning/
│   ├── __init__.py
│   ├── nudge.py             # Nudge counters (132 lines)
│   ├── review.py            # Background review agent (504 lines)
│   ├── session_store.py     # SQLite FTS5 session persistence (417 lines)
│   └── session_search.py    # Cross-session search tool (147 lines)
│
├── permission/
│   └── __init__.py          # 4-mode permission system (193 lines)
│
├── checkpoint/
│   └── __init__.py          # Git-based snapshot & rollback (518 lines)
│
├── plan/
│   └── __init__.py          # Markdown-based execution plans (471 lines)
│
├── trajectory/
│   └── __init__.py          # Compressed JSON trajectory logs (407 lines)
│
├── interrupt/
│   └── __init__.py          # Interrupt signal management (106 lines)
│
├── display/
│   └── __init__.py          # CLI visualization (846 lines)
│
└── plugin/
    └── __init__.py           # Plugin system (placeholder)
```

---

## 4. REST API (`server.py`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Send message, get SSE stream |
| POST | `/sessions` | Create new session |
| GET | `/sessions/{id}` | Get session history |
| DELETE | `/sessions/{id}` | Delete session |
| GET | `/health` | Health check |

SSE event types match the agent stream events.

---

## 5. Testing

- Framework: pytest + pytest-asyncio (auto mode)
- 26 test files covering all major modules
- Async mocks for LLM calls (no external API dependency)
- `@pytest.mark.integration` for tests requiring network

```bash
pytest tests/ -v
pytest tests/ --cov=src/feinn_agent --cov-report=term-missing
```
