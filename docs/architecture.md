# FeinnAgent Architecture

## 1. Overview

### 1.1 Design Philosophy

1. **Async-First**: All IO is asynchronous via asyncio
2. **Event-Driven**: Agent loop yields typed dataclass events
3. **Stateless Loop**: All state lives in `AgentState`; the loop itself is stateless
4. **Modular Registry**: Tools, providers, and skills self-register at import time
5. **Harness Engineering**: Guides (proactive) + Sensors (post-execution) + Guardrails (safety)

### 1.2 Layer Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Presentation Layer                        │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │ CLI (click) │  │ TUI (prompt  │  │ FastAPI Server      │  │
│  │ interactive │  │  _toolkit)   │  │ (SSE streaming)     │  │
│  │ + one-shot  │  │ full-screen  │  │                     │  │
│  └─────────────┘  └──────────────┘  └─────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                        Core Layer                             │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐   │
│  │ FeinnAgent   │  │ build_system_ │  │ maybe_compact()  │   │
│  │ (async gen)  │  │ prompt()      │  │ Snip/Compact/    │   │
│  │              │  │ (no class)    │  │ Collapse         │   │
│  └──────────────┘  └───────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                      Subsystem Layer                          │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐ ┌──────┐   │
│  │Tools │ │Memory│ │Tasks │ │Sub-  │ │Skill   │ │Learn │   │
│  │20+   │ │dual  │ │DAG   │ │agent │ │system  │ │closed│   │
│  │built-│ │scope │ │      │ │5     │ │5 built-│ │loop  │   │
│  │in    │ │YAML  │ │      │ │types │ │in      │ │      │   │
│  └──────┘ └──────┘ └──────┘ └──────┘ └────────┘ └──────┘   │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                        │
│  ┌────────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Providers  │  │ MCP      │  │ Storage  │  │ Display   │  │
│  │ (stream()) │  │ Client   │  │ SQLite   │  │ (Rich ANSI│  │
│  │            │  │ stdio/   │  │ JSON/YAML│  │  + kawaii)│  │
│  │            │  │ SSE/HTTP │  │          │  │           │  │
│  └────────────┘  └──────────┘  └──────────┘  └───────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 Core Components

| Component | File | Description |
|-----------|------|-------------|
| FeinnAgent | `agent.py` | Async generator loop: user msg → LLM → tools → loop/exit |
| System Prompt | `context.py` | `build_system_prompt()` — dynamic prompt assembly from tool schemas, git info, project context, memory |
| Compaction | `compaction.py` | `maybe_compact()` — Snip (trim tool outputs) → Compact (truncation) → Collapse (emergency) |
| Providers | `providers.py` | `stream()` — single entry point, two code paths (Anthropic native / OpenAI-compatible) |
| Tool Registry | `tools/registry.py` | Dict-based: `register()` / `dispatch()` / `dispatch_batch()` |
| Permission | `permission/__init__.py` | 4 modes: accept-all / auto / manual / plan |
| Sub-agent | `subagent/manager.py` | 5 built-in types, semaphore concurrency, depth limit |
| Memory | `memory/store.py` | Dual-scope, YAML frontmatter, keyword search |
| Task | `task/store.py` | DAG with blocks/blocked_by, JSON persistence |
| Skill | `skill/` | Templates with YAML frontmatter, activators, parameter substitution |
| Learning | `learning/` | Nudge counters, background review, SQLite FTS5 session store |
| MCP | `mcp/client.py` | stdio/SSE/HTTP transports, auto-register tools |

---

## 2. Data Flow

```
User Input
    │
    ▼
CLI / TUI / API Server
    │
    ▼
FeinnAgent.run(message)
    │
    ├─► AgentState.add_message(USER, content)
    │
    ├─► maybe_compact(state, config)
    │      ├─ Layer 1: Snip old tool outputs
    │      ├─ Layer 2: Compact (truncation)
    │      └─ Layer 3: Collapse (on context_length error)
    │
    ├─► _stream_with_retry()
    │      ├─ llm_stream(model, system, messages, tool_schemas, config)
    │      ├─ Streams TextChunk / ThinkingChunk in real-time
    │      └─ Yields final AssistantTurn
    │
    ├─► AgentState.add_message(ASSISTANT, text, tool_calls, reasoning)
    │
    ├─► yield TurnDone
    │
    ├─► [if no tool_calls] → yield AgentDone → return
    │
    ├─► yield ToolStart for each tool
    │
    ├─► _execute_tools(tool_calls)
    │      ├─ check_permission() per tool
    │      └─ dispatch_batch(permitted_calls, config)
    │             ├─ concurrent-safe + read-only → asyncio.gather (parallel)
    │             └─ everything else → sequential
    │
    ├─► yield ToolEnd for each tool
    │
    ├─► AgentState.add_message(TOOL, ...) for each result
    │
    ├─► Learning hooks:
    │      ├─ TrajectoryRecorder.record_turn()
    │      ├─ SessionStore.append_message()
    │      ├─ NudgeCounter.record_turn() / record_tool_iterations()
    │      └─ BackgroundReviewer.spawn() (if threshold reached)
    │
    └─► loop back to LLM
```

---

## 3. Component Details

### 3.1 Agent Loop (`agent.py`)

- `FeinnAgent` class with `run()` async generator
- Yields `AgentEvent` union: `TextChunk | ThinkingChunk | ToolStart | ToolEnd | PermissionRequest | TurnDone | AgentDone | AssistantTurn`
- 3 retries with exponential backoff (1s, 2s, 4s) for retryable errors (`overloaded`, `rate_limit`, `timeout`, `context_length`)
- On `context_length` error: forces compaction before retry
- Max iterations (default 50) prevents infinite loops

### 3.2 Providers (`providers.py`)

```
stream()
    ├── detect_provider(model) → ProviderInfo
    ├── _stream_anthropic()     — Anthropic SDK, native thinking
    └── _stream_openai_compat() — OpenAI SDK, 13 providers
```

**13 providers via OpenAI-compatible path**: openai, azure, gemini, qwen, deepseek, kimi, moonshot, siliconflow, openrouter, ollama, vllm, lmstudio, custom

### 3.3 Tool System

Tools self-register at import time in `tools/registry.py`.

**20+ built-in tools**:

| Tool | Type | Safety | Parallel-safe |
|------|------|--------|---------------|
| Read | File | read_only | yes |
| Write | File | destructive | no |
| Edit | File | destructive | no |
| Bash | Exec | destructive* | no |
| Glob | Search | read_only | yes |
| Grep | Search | read_only | yes |
| WebFetch | Web | read_only | yes |
| AskUserQuestion | Interactive | read_only | no |
| Agent | Sub-agent | concurrent_safe | no |
| CheckAgentResult | Sub-agent | read_only | yes |
| MemorySave | Memory | concurrent_safe | yes |
| MemorySearch | Memory | read_only | yes |
| MemoryDelete | Memory | concurrent_safe | yes |
| MemoryList | Memory | read_only | yes |
| TaskCreate/TaskUpdate/TaskList/TaskGet | Task | concurrent_safe | yes |
| Skill/SkillList/SkillManage | Skill | concurrent_safe | yes |
| SessionSearch | Learning | read_only | yes |
| Browser* | Browser | concurrent_safe | no |
| Tmux* | Tmux | concurrent_safe | no |
| GetDiagnostics | Diagnostic | read_only | yes |

*\*safe Bash commands are auto-approved in auto mode*

### 3.4 Permission System

```
check_permission(tool_name, tool_input, config, callback)
    │
    ├─ ACCEPT_ALL → always True
    │
    ├─ MANUAL → ask callback for everything
    │
    ├─ PLAN → read_only auto-approved
    │         Write/Edit only for plan file path
    │         Bash safe commands auto-approved
    │         everything else denied
    │
    └─ AUTO → read_only auto-approved
               Bash: check safe patterns + unsafe patterns
               destructive: ask callback
               other writes: ask callback
```

### 3.5 Sub-agent System

**5 built-in types**:

| Type | Tools | System Prompt |
|------|-------|---------------|
| general-purpose | all | — (none, default) |
| coder | all | Code implementation specialist |
| reviewer | Read/Glob/Grep/Bash | Code quality, security, correctness |
| researcher | Read/Glob/Grep/WebFetch/MemorySearch/SessionSearch | Information gathering |
| tester | Read/Glob/Grep/Bash/Write/Edit | Test writing |

- Semaphore: default 5 concurrent sub-agents
- Max depth: default 3
- Model override: per-agent-type or inherit from parent

### 3.6 Memory System

```
~/.feinn/memory/      ← user scope (cross-project)
.feinn/memory/        ← project scope (repo-local)
```

- Format: Markdown with YAML frontmatter
- Search: keyword match with `confidence × recency` scoring
- Types: user, feedback, project, reference

### 3.7 Task System

```
tasks.json  ← DAG with blocks/blocked_by edges
Status: pending → in_progress → completed | cancelled
```

### 3.8 Skill System

- Templates: Markdown with YAML frontmatter
- Scopes: `~/.feinn/skills/` (global) + `.feinn/skills/` (project)
- Activation: `/command` style activators with parameter substitution (`$PARAMS`, `$NAMED_PARAM`)
- Execution modes: `direct` (current context) or `isolated` (sub-agent)
- Built-in: commit, review, explain, test, doc

### 3.9 MCP Integration

- Transports: stdio (subprocess), SSE (HTTP stream), HTTP (direct POST)
- JSON-RPC 2.0 protocol
- Auto-discovers and registers MCP tools
- Thread-safe transport management

### 3.10 Learning System

```
per-turn hooks:
  NudgeCounter.record_turn()
  NudgeCounter.record_tool_iterations(N)
  SessionStore.append_message(...)
  BackgroundReviewer.spawn()   [daemon thread, every N turns]

SessionStore schema: SQLite + FTS5
  Search modes: DISCOVER (FTS5), SCROLL (±N window), BROWSE (recent)
```

### 3.11 Checkpoint System

- Git-based shadow repository in `.feinn/checkpoints/`
- Auto-checkpoint before file mutations
- Rollback: `checkpoint rollback <id>`

---

## 4. Configuration

Three-layer priority:
1. **Environment variables** (highest, loaded via python-dotenv)
2. **Config file** (`~/.feinn/config.json`)
3. **Defaults** (hardcoded in `config.py`)

Config is a plain `dict[str, Any]`.

---

## 5. Extension Points

### Adding New Tools

```python
from feinn_agent.tools.registry import register
from feinn_agent.types import ToolDef

async def my_handler(params: dict, config: dict) -> str:
    return "result"

register(ToolDef(
    name="MyTool",
    description="Description for LLM",
    input_schema={"type": "object", "properties": {...}},
    handler=my_handler,
    read_only=True,
    concurrent_safe=True,
))
```

### Adding New Agent Types

Add to `_BUILTIN_AGENTS` dict in `subagent/manager.py`.

### Adding New LLM Providers

Add pattern + context limit to `providers.py`:
- `_PROVIDER_RULES` — model name pattern
- `_CONTEXT_LIMITS` — context window size
- `_OPENAI_COMPAT_PROVIDERS` — add to set
- `get_base_url()` — add URL

---

## 6. Deployment

### Single Node

```
┌──────────────────────────────────────┐
│           Single Node                │
│  ┌──────────────────────────────┐   │
│  │     FeinnAgent Server         │   │
│  │  ┌─────┐ ┌──────┐ ┌───────┐ │   │
│  │  │ CLI │ │ TUI  │ │ API   │ │   │
│  │  │     │ │      │ │ SSE   │ │   │
│  │  └─────┘ └──────┘ └───────┘ │   │
│  │         │                    │   │
│  │    ┌────▼────┐              │   │
│  │    │  Agent  │              │   │
│  │    │  Engine │              │   │
│  │    └────┬────┘              │   │
│  │         ▼                   │   │
│  │    ┌──────────┐             │   │
│  │    │ Storage  │             │   │
│  │    │ SQLite + │             │   │
│  │    │ JSON/YAML│             │   │
│  │    └──────────┘             │   │
│  └──────────────────────────────┘   │
└──────────────────────────────────────┘
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["feinn", "--serve", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 7. Glossary

| Term | Definition |
|------|------------|
| AgentEvent | Union type for all stream events from `FeinnAgent.run()` |
| AgentState | Mutable session state (messages, tokens, turn count) |
| ToolDef | Tool definition: name, description, schema, handler, safety flags |
| PermissionMode | accept-all / auto / manual / plan |
| Compaction | Three-layer context compression (Snip / Compact / Collapse) |
| AgentDefinition | Template for spawning sub-agents |
| SkillTemplate | Reusable prompt with YAML frontmatter, activators, parameter substitution |
| NudgeCounter | Tracks intervals for triggering memory/skill review |
| SessionStore | SQLite FTS5 session persistence for cross-session search |
| Trajectory | Compressed JSON log of agent execution turns |
| Checkpoint | Git-based file system snapshot for rollback |
