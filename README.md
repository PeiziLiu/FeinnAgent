# FeinnAgent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License: Apache 2.0">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-2.0+-e92063.svg" alt="Pydantic 2.0+">
</p>

<p align="center">
  <b>Enterprise-Grade Multi-Concurrency AI Agent Framework</b><br>
  Built with Python, supporting multiple models, multi-concurrency, context compression, task orchestration, and sub-agent collaboration
:</p>

<p align="center">
  <a href="README.zh.md">中文</a> | <strong>English</strong>
</p>

---

FeinnAgent is an enterprise-grade, multi-concurrency AI Agent framework built with Python, designed for both local development and server-side deployment. It offers out-of-the-box multi-model integration (supporting 10+ LLM providers including OpenAI, Anthropic, SiliconFlow, Azure, Gemini, DeepSeek, and more), intelligent context compression, DAG task orchestration, concurrent sub-agent collaboration, and a dual-scope memory system. With 20+ built-in tools, reusable Skill templates, and MCP protocol extensions, FeinnAgent efficiently handles a wide range of scenarios from simple Q&A to complex multi-step tasks. The framework provides three usage modes — interactive CLI, one-shot commands, and a production-ready RESTful API server — making it equally suited for rapid prototyping on a developer's machine and scalable deployment behind enterprise infrastructure.

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Model Support** | 10+ LLM providers (OpenAI, Anthropic, Gemini, DeepSeek, SiliconFlow, Azure, vLLM, Ollama, LM Studio) |
| **Async Architecture** | High-performance asyncio-based concurrency |
| **Context Compaction** | Intelligent context window management with multi-level compression |
| **DAG Task System** | Task orchestration with blocks/blocked_by dependency edges |
| **Sub-Agent Collaboration** | Concurrent sub-agents with tool restrictions and depth control |
| **Dual-Scope Memory** | User (global) and Project (repo-local) memory scopes |
| **Skill Templates** | Reusable prompt templates with activators and parameter substitution |
| **Permission Control** | Four modes: accept-all, auto, manual, plan |
| **MCP Integration** | Native Model Context Protocol support (stdio/sse/http transport) |
| **20+ Built-in Tools** | File ops, search, bash, diagnostics, tmux, memory, tasks |

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Modes](#usage-modes)
- [Command Reference](#command-reference)
- [Supported Models](#supported-models)
- [Architecture Features](#architecture-features)
- [Project Structure](#project-structure)
- [Skill System](#skill-system)
- [Development Guide](#development-guide)
- [Documentation](#documentation)

---

## Installation

### Requirements

- Python 3.11+
- macOS / Linux / Windows

### Installation Steps

```bash
# 1. Clone the repository
git clone https://github.com/PeiziLiu/FeinnAgent.git
cd feinn-agent

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
python3.11 -m pip install -e .

# 4. Configure environment variables
cp .env.example .env
# Edit .env file with your API keys
```

---

## Quick Start

### 1. Configure API Keys

Edit `.env` file and select your model provider:

```bash
# SiliconFlow (recommended, available in China)
SILICONFLOW_API_KEY=sk-your-key
DEFAULT_MODEL=siliconflow/Pro/zai-org/GLM-5.1

# Or OpenAI
OPENAI_API_KEY=sk-your-key
DEFAULT_MODEL=openai/gpt-4o

# Or Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
DEFAULT_MODEL=anthropic/claude-sonnet-4

# Or Azure OpenAI
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_URL=https://your-resource.openai.azure.com/...
DEFAULT_MODEL=azure/gpt-4

# Or vLLM self-hosted
VLLM_BASE_URL=http://localhost:8000/v1
DEFAULT_MODEL=vllm/Qwen2.5-72B-Instruct
```

### 2. Start Interactive Mode

```bash
# Start interactive session (recommended)
feinn -i

# Or one-shot query
feinn "Analyze the code structure in current directory"

# Start API server
feinn --serve
```

### 3. Interactive Mode Usage

After starting `feinn -i`, you'll see:

```
  FeinnAgent v0.1.0
  Model: siliconflow/Pro/zai-org/GLM-5.1
  Type '/quit' to exit, '/help' for commands

feinn> Hello
```

Type your questions directly, and the Agent maintains conversation context.

---

## Configuration

### Environment Variables (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `DEFAULT_MODEL` | Default model to use | `siliconflow/Pro/zai-org/GLM-5.1` |
| `SILICONFLOW_API_KEY` | SiliconFlow API key | `sk-...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `GEMINI_API_KEY` | Google Gemini API key | `...` |
| `DEEPSEEK_API_KEY` | DeepSeek API key | `sk-...` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key | `...` |
| `AZURE_OPENAI_URL` | Azure OpenAI endpoint | `https://...` |
| `VLLM_BASE_URL` | vLLM service URL | `http://localhost:8000/v1` |
| `VLLM_API_KEY` | vLLM API key (optional) | `sk-...` |
| `OLLAMA_BASE_URL` | Ollama service URL | `http://localhost:11434/v1` |
| `LOG_LEVEL` | Log level | `INFO` / `DEBUG` |
| `LOG_FILE` | Log file path | `~/.feinn/feinn.log` |
| `PERMISSION_MODE` | Permission mode | `accept-all` / `auto` / `manual` / `plan` |
| `SERVER_HOST` | API server host | `0.0.0.0` |
| `SERVER_PORT` | API server port | `8000` |
| `FEINN_HOME` | Feinn config directory | `~/.feinn` |

### Permission Modes

| Mode | Description |
|------|-------------|
| `accept-all` | Auto-accept all tool calls (default) |
| `auto` | Smart judgment, destructive operations require confirmation |
| `manual` | All tool calls require manual confirmation |
| `plan` | Read-only mode, only plan file writes allowed |

---

## Usage Modes

### Mode 1: Interactive CLI (Recommended)

Best for multi-turn conversations and complex tasks:

```bash
feinn -i
```

**Features:**
- Maintains conversation context
- Supports multi-turn follow-ups
- Real-time tool execution display
- Built-in command shortcuts

**Example Session:**
```
feinn> Read the README.md file
[Tool: Read] Reading...
File content: ...

feinn> Summarize what this project does
Based on the content, this is a...

feinn> Create a simple example for me
[Tool: Write] Writing file example.py...
Example file created.
```

### Mode 2: One-Shot Command

Best for simple queries and script calls:

```bash
feinn "Your question or instruction"
```

**Examples:**
```bash
feinn "Explain Python asyncio principles"
feinn "Check code style issues in current directory"
feinn "Generate a Dockerfile for Flask project"
```

### Mode 3: API Server

Best for integration with other applications:

```bash
# Start server
feinn --serve --host 0.0.0.0 --port 8000

# Or use environment variables
SERVER_HOST=0.0.0.0 SERVER_PORT=8000 feinn --serve
```

**API Endpoints:**
- `POST /chat` - Send message
- `GET /health` - Health check
- `GET /models` - List supported models

---

## Command Reference

### Global Options

```bash
feinn [OPTIONS] [PROMPT]

Options:
  -i, --interactive    Start interactive REPL mode
  --serve              Start API server
  --model TEXT         Specify model
  --accept-all         Auto-approve all tool calls
  --thinking           Enable extended thinking mode
  --host TEXT          Server host address
  --port INTEGER       Server port
  --help               Show help information
```

### Interactive Mode Commands

In `feinn -i` interactive mode, use these commands:

| Command | Description |
|---------|-------------|
| `/quit` or `/q` | Exit program |
| `/help` or `/h` | Show help |
| `/clear` | Clear conversation history |
| `/model [model]` | View or switch model |
| `/save` | Save session to file |
| `/tasks` | Show task list |
| `/memory` | Show memory list |
| `/skills` | List available skills |
| `/config` | Show current configuration |
| `/accept-all` | Switch to auto-accept mode |
| `/auto` | Switch to smart judgment mode |
| `/manual` | Switch to manual confirmation mode |

### Usage Examples

```bash
# Interactive mode
feinn -i

# One-shot query
feinn "How to optimize this code?"

# Specify model
feinn --model openai/gpt-4o "Explain quantum computing"

# Auto-accept all operations
feinn -i --accept-all

# Start API server
feinn --serve --port 8080

# Use vLLM local model
feinn --model vllm/Qwen2.5-72B-Instruct -i

# Use with DeepSeek
feinn --model deepseek/deepseek-chat "Write a Python decorator"

# Interactive commands
feinn> /help          # Show help
feinn> /skills        # List available skills
feinn> /tasks         # Show task list
feinn> /memory        # Show memory list
feinn> /model [name]  # Switch model
feinn> /clear         # Clear conversation
feinn> /quit          # Exit
```

---

## Supported Models

### Cloud Providers

| Provider | Model Format | Example |
|----------|--------------|---------|
| SiliconFlow | `siliconflow/{model}` | `siliconflow/Pro/zai-org/GLM-5.1` |
| OpenAI | `openai/{model}` | `openai/gpt-4o` |
| Anthropic | `anthropic/{model}` | `anthropic/claude-sonnet-4` |
| Azure OpenAI | `azure/{deployment}` | `azure/gpt-4` |
| Gemini | `gemini/{model}` | `gemini/gemini-2.5-pro` |
| DeepSeek | `deepseek/{model}` | `deepseek/deepseek-v3` |

### Local Deployment

| Method | Model Format | Configuration |
|--------|--------------|---------------|
| vLLM | `vllm/{model}` | `VLLM_BASE_URL` |
| Ollama | `ollama/{model}` | `OLLAMA_BASE_URL` |
| LM Studio | `lmstudio/{model}` | Auto-detect |

---

## Architecture Features

### Core Features

- **Multi-Model Support**: Native support for 10+ LLM providers
- **Enterprise-Grade Concurrency**: High-performance async architecture based on asyncio
- **Intelligent Context Compression**: Auto-detect context window, intelligently compress history
- **Task Orchestration System**: Built-in DAG task management with dependency tracking
- **Sub-Agent Collaboration**: Support concurrent sub-agent spawning for complex parallel task decomposition
- **Dual-Scope Memory**: Workspace-level and Agent-level memory isolation
- **Skill System**: Reusable prompt templates with activators and parameter substitution
- **Permission Control**: Fine-grained tool permission management
- **MCP Integration**: Native Model Context Protocol support

### Built-in Tools (20+)

| Category | Tools | Description | File |
|----------|-------|-------------|------|
| File Operations | `Read`, `Write`, `Edit` | File read/write/edit with unified diff | `tools/builtins.py` |
| Search | `Glob`, `Grep` | File pattern matching and regex search | `tools/builtins.py` |
| Execution | `Bash` | Shell command with process isolation | `tools/builtins.py`, `tools/process.py` |
| Web | `WebFetch` | HTTP content fetching | `tools/builtins.py` |
| User Interaction | `AskUserQuestion` | Clarifying questions | `tools/builtins.py` |
| Tmux | `TmuxNewSession`, `TmuxSendKeys`, `TmuxCapture` | Persistent session management | `tools/tmux.py` |
| Diagnostics | `GetDiagnostics` | Code linting (pyright/eslint/shellcheck) | `tools/diagnostics.py` |
| Memory | `MemorySave`, `MemorySearch`, `MemoryList`, `MemoryDelete` | Knowledge management | `memory/store.py` |
| Task Management | `TaskCreate`, `TaskGet`, `TaskList`, `TaskUpdate` | DAG task orchestration | `task/store.py` |
| Sub-Agent | `Agent`, `CheckAgentResult`, `ListAgentTasks`, `ListAgentTypes` | Concurrent sub-agent collaboration | `subagent/manager.py` |
| Skill | `Skill`, `SkillList` | Reusable prompt templates | `skill/executor.py` |

---

## Project Structure

```
feinn-agent/
├── src/feinn_agent/          # Main package
│   ├── __init__.py           # Public API exports
│   ├── agent.py              # Core agent loop (async generator)
│   ├── cli.py                # CLI entry point (Click-based)
│   ├── config.py             # Configuration loading (.env + JSON)
│   ├── types.py              # Core type definitions (dataclasses)
│   ├── providers.py          # LLM provider adapters (10+ providers)
│   ├── context.py            # Context window management
│   ├── compaction.py         # Context compression engine
│   ├── server.py             # FastAPI REST API server
│   ├── tools/                # Tool system
│   │   ├── __init__.py
│   │   ├── registry.py       # Tool registration and dispatch
│   │   ├── builtins.py       # Built-in tools (Read/Write/Edit/Bash/Glob/Grep)
│   │   ├── process.py        # Process tree management
│   │   ├── tmux.py           # Tmux persistent session tools
│   │   ├── diagnostics.py    # Code diagnostics (pyright/eslint/shellcheck)
│   │   ├── output.py         # Output processing (truncation/ANSI cleanup)
│   │   └── skills.py         # Skill tool wrappers
│   ├── memory/               # Dual-scope memory system
│   │   └── store.py          # Memory storage with YAML frontmatter
│   ├── task/                 # DAG task orchestration
│   │   └── store.py          # Task state machine and dependency management
│   ├── skill/                # Skill template system
│   │   ├── loader.py         # Skill file discovery and parsing
│   │   ├── executor.py       # Skill execution engine
│   │   └── builtin.py        # Built-in skill definitions
│   ├── subagent/             # Concurrent sub-agent system
│   │   └── manager.py        # Sub-agent lifecycle management
│   ├── permission/           # Permission control
│   │   └── __init__.py       # Permission checking (4 modes)
│   ├── mcp/                  # MCP protocol integration
│   │   └── client.py         # MCP client (stdio/sse/http transport)
│   └── plugin/               # Plugin system
│       └── __init__.py       # Plugin loading interface
├── tests/                    # Test suite
│   ├── test_agent.py         # Agent loop tests
│   ├── test_compaction.py    # Context compression tests
│   ├── test_config.py        # Configuration tests
│   ├── test_core.py          # Core integration tests
│   ├── test_execution_engine.py  # Execution engine tests
│   ├── test_memory.py        # Memory system tests
│   ├── test_providers.py     # Provider adapter tests
│   ├── test_skill.py         # Skill system tests
│   └── test_tools.py         # Tool system tests
├── docs/                     # Documentation
│   ├── requirements.md       # Requirements design document
│   ├── architecture.md       # Architecture design document
│   ├── technical.md          # Technical design document
│   ├── roadmap.md            # Development roadmap
│   ├── execution-engine-requirements.md
│   ├── execution-engine-technical.md
│   └── *.md                  # Deployment guides
├── .feinn/                   # Project-level config
│   └── skills/               # Project-level custom skills
├── pyproject.toml            # Project metadata and dependencies
├── DEVELOPMENT_WORKFLOW.md   # Development workflow and standards
├── wiki.md / wiki.zh.md      # Wiki documentation (EN/ZH)
└── README.md / README.zh.md  # README (EN/ZH)
```
feinn-agent/
├── src/feinn_agent/          # Main package
│   ├── __init__.py           # Public API exports
│   ├── agent.py              # Core agent loop (async generator)
│   ├── cli.py                # CLI entry point (Click-based)
│   ├── config.py             # Configuration loading (.env + YAML)
│   ├── types.py              # Core type definitions (dataclasses)
│   ├── providers.py          # LLM provider adapters (OpenAI, Anthropic, etc.)
│   ├── context.py            # Context window management
│   ├── compaction.py         # Context compression engine
│   ├── server.py             # FastAPI REST API server
│   ├── tools/                # Tool system
│   │   ├── registry.py       # Tool registration and dispatch
│   │   ├── builtins.py       # Built-in tools (Read/Write/Edit/Bash/Glob/Grep)
│   │   ├── process.py        # Process tree management
│   │   ├── tmux.py           # Tmux persistent session tools
│   │   ├── diagnostics.py    # Code diagnostics (pyright/eslint/shellcheck)
│   │   ├── output.py         # Output processing (truncation/ANSI cleanup)
│   │   └── skills.py         # Skill tool wrappers
│   ├── memory/               # Dual-scope memory system
│   │   └── store.py          # Memory storage and retrieval
│   ├── task/                 # DAG task orchestration
│   │   └── store.py          # Task state machine and dependency management
│   ├── skill/                # Skill template system
│   │   ├── loader.py         # Skill file discovery and parsing
│   │   ├── executor.py       # Skill execution engine
│   │   └── builtin.py        # Built-in skill definitions
│   ├── subagent/             # Concurrent sub-agent system
│   │   └── manager.py        # Sub-agent lifecycle management
│   ├── permission/           # Permission control
│   │   └── __init__.py       # Permission checking (4 modes)
│   ├── mcp/                  # MCP protocol integration
│   │   └── client.py         # MCP client (stdio/sse transport)
│   └── plugin/               # Plugin system
│       └── __init__.py       # Plugin loading interface
├── tests/                    # Test suite
│   ├── test_agent.py         # Agent loop tests
│   ├── test_compaction.py    # Context compression tests
│   ├── test_config.py        # Configuration tests
│   ├── test_core.py          # Core integration tests
│   ├── test_execution_engine.py  # Execution engine tests
│   ├── test_memory.py        # Memory system tests
│   ├── test_providers.py     # Provider adapter tests
│   ├── test_skill.py         # Skill system tests
│   └── test_tools.py         # Tool system tests
├── docs/                     # Documentation
│   ├── requirements.md       # Requirements design document
│   ├── architecture.md       # Architecture design document
│   ├── technical.md          # Technical design document
│   ├── roadmap.md            # Development roadmap
│   └── execution-engine-*.md # Execution engine upgrade docs
├── .feinn/skills/            # Project-level custom skills
├── pyproject.toml            # Project metadata and dependencies
├── DEVELOPMENT_WORKFLOW.md   # Development workflow and standards
├── wiki.md / wiki.zh.md      # Wiki documentation (EN/ZH)
└── README.md / README.zh.md  # README (EN/ZH)
```

---

## Sub-Agent System

FeinnAgent supports spawning concurrent sub-agents for parallel task decomposition:

| Agent Type | Description | Tools |
|------------|-------------|-------|
| `general-purpose` | Versatile agent for research and multi-step tasks | All tools |
| `coder` | Code implementation specialist | All tools |
| `reviewer` | Code quality, security, correctness analysis | Read, Glob, Grep, Bash |
| `researcher` | Web search and documentation lookup | Read, Glob, Grep, WebFetch |
| `tester` | Test generation and execution | Read, Write, Edit, Bash, Glob, Grep |

**Features:**
- Asyncio-based concurrent execution with semaphore control
- Maximum depth limit to prevent infinite recursion
- Tool restrictions per agent type
- Model override support
- Wait/polling modes for result collection

```python
# Example: Spawn a reviewer sub-agent
[Tool: Agent] Spawning sub-agent: type=reviewer
[Tool: Agent] Sub-agent (reviewer) result:
## Summary
Code review complete...
```

---

## Skill System

Skill is FeinnAgent's reusable prompt template system for encapsulating common workflows. Invoke predefined prompt templates via activators (e.g., "/commit").

### Built-in Skills

| Skill | Activator | Description |
|-------|-----------|-------------|
| `commit` | `/commit` | Review staged changes and create a well-structured git commit |
| `review` | `/review`, `/review-pr` | Review code or PR and provide structured feedback |
| `explain` | `/explain` | Explain code in detail for learning purposes |
| `test` | `/test` | Generate comprehensive tests for specified code |
| `doc` | `/doc` | Generate or update documentation for code |

### Using Skills

In interactive mode, type the activator directly:

```
feinn> /commit
[Agent will review git state and create a commit]

feinn> /explain src/feinn_agent/agent.py
[Agent will explain the code in detail]

feinn> /test src/feinn_agent/tools.py
[Agent will generate tests for this module]

feinn> /review
[Agent will review current branch changes]
```

### Custom Skills

Create `.md` files in `~/.feinn/skills/` or project `.feinn/skills/` directory:

```markdown
---
id: my-skill
summary: My custom skill
activators: ["/my", "do my thing"]
tools: ["Read", "Write"]
param-guide: "[filename]"
param-names: ["filename"]
---

Please process file: $FILENAME

Context: $PARAMS
```

**Frontmatter Fields:**

| Field | Description | Required |
|-------|-------------|----------|
| `id` | Unique skill identifier | Yes |
| `summary` | Short description | Yes |
| `activators` | Trigger word list | No (defaults to `/id`) |
| `tools` | Allowed tools | No |
| `param-guide` | Parameter hint | No |
| `param-names` | Parameter name list (for `$NAME` substitution) | No |
| `exec-mode` | Execution mode: `direct` or `isolated` | No |
| `visible` | Whether to show in list | No |

**Template Placeholders:**

- `$PARAMS` or `$ARGUMENTS` - Complete parameter string from user
- `$NAME` - Named parameter corresponding to `param-names` (uppercase)

---

## Development Guide

### Running Tests

```bash
# Run all tests
python3.11 -m pytest tests/ -v

# Run specific tests
python3.11 -m pytest tests/test_core.py -v

# Run with coverage
python3.11 -m pytest tests/ --cov=src/feinn_agent --cov-report=term-missing

# Run without integration tests
python3.11 -m pytest tests/ -m "not integration"
```

### Code Quality

```bash
# Format code
python3.11 -m ruff format src/

# Check code
python3.11 -m ruff check src/

# Fix auto-fixable issues
python3.11 -m ruff check src/ --fix
```

### Project Structure

```
src/feinn_agent/
├── __init__.py           # Public API exports
├── agent.py              # Core agent loop (async generator)
├── cli.py                # CLI entry point
├── config.py             # Configuration loading
├── context.py            # Context management
├── compaction.py         # Context compression
├── providers.py          # LLM provider adapters
├── server.py             # FastAPI REST API server
├── types.py              # Core type definitions
├── tools/
│   ├── __init__.py
│   ├── registry.py       # Tool registration
│   ├── builtins.py       # Built-in tools
│   ├── process.py        # Process tree
│   ├── tmux.py           # Tmux integration
│   ├── diagnostics.py     # Code diagnostics
│   ├── output.py         # Output processing
│   └── skills.py         # Skill tools
├── memory/
│   └── store.py          # Dual-scope memory
├── task/
│   └── store.py          # DAG task system
├── skill/
│   ├── loader.py         # Skill loading
│   ├── executor.py       # Skill execution
│   └── builtin.py        # Built-in skills
├── subagent/
│   └── manager.py        # Sub-agent system
├── permission/
│   └── __init__.py       # Permission control
├── mcp/
│   └── client.py         # MCP client
└── plugin/
    └── __init__.py       # Plugin system
```

### Adding New Tools

```python
from feinn_agent.types import ToolDef
from feinn_agent.tools.registry import register

async def my_tool(params: dict, config: dict) -> str:
    """Tool implementation"""
    return f"Result: {params.get('param')}"

register(
    ToolDef(
        name="my_tool",
        description="Tool description",
        input_schema={
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Parameter description"}
            },
            "required": ["param"]
        },
        handler=my_tool,
        read_only=True,  # or False for destructive
    )
)
```

---

## Documentation

### Design Documents

- [Requirements Design](docs/requirements.md) - Functional and non-functional requirements
- [Architecture Design](docs/architecture.md) - System architecture, layered design, data flow
- [Technical Design](docs/technical.md) - Detailed module implementation and API design
- [Development Roadmap](docs/roadmap.md) - Version planning and milestones

### Execution Engine Upgrade

- [Execution Engine Requirements](docs/execution-engine-requirements.md) - Harness Engineering-based upgrade requirements
- [Execution Engine Technical Design](docs/execution-engine-technical.md) - Detailed implementation design

### Deployment Guides

- [vLLM Deployment Guide](docs/vllm-deployment.md) - Self-hosted model deployment
- [vLLM + Qwen3.5 Demo](docs/vllm-qwen35-demo.md) - Qwen3.5 deployment example
- [SiliconFlow Setup](docs/siliconflow-setup.md) - China API platform usage
- [Azure OpenAI Setup](docs/azure-openai-setup.md) - Enterprise Azure deployment

### Development

- [Contributing Guide](CONTRIBUTING.md) - Contribution guidelines, code standards, and PR process
- [Development Workflow](DEVELOPMENT_WORKFLOW.md) - Git workflow, coding standards, and release process
- [Wiki](wiki.md) / [Wiki (Chinese)](wiki.zh.md) - General reference documentation

---

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details

---

## Contact & Support

- **Email**: hanfazy@126.com
- **Issues**: [GitHub Issues](https://github.com/PeiziLiu/FeinnAgent/issues)

### Donate

If you find this project helpful, consider supporting its development:

<p align="center">
  <img src="docs/images/wechat-donate.png" width="200" alt="WeChat Donate">
  <br>
  <sub>WeChat QR Code</sub>
</p>

---

<p align="center">
  Built with ❤️ by Feinn Team
</p>
