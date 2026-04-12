# FeinnAgent Wiki

<p align="center">
  <strong>English</strong> | <a href="wiki.zh.md">中文</a>
</p>

## Introduction

FeinnAgent is an **enterprise-grade multi-concurrency AI Agent framework** built with Python, designed for complex AI agent tasks. It supports multi-model integration, concurrent execution, intelligent context compression, DAG task orchestration, and sub-agent collaboration, suitable for both individual developers and enterprise applications.

---

## Core Features

| Feature | Description |
|---------|-------------|
| Multi-Model Support | Native support for 10+ LLM providers (OpenAI, Anthropic, SiliconFlow, Azure, Gemini, DeepSeek, etc.) |
| Enterprise Concurrency | High-performance async architecture based on asyncio |
| Smart Context Compression | Auto-detects context window limits and intelligently compresses message history |
| DAG Task Orchestration | Built-in directed acyclic graph task management with dependency and state tracking |
| Sub-Agent Collaboration | Concurrent sub-agent spawning for parallel task decomposition |
| Dual-Scope Memory | Workspace-level and Agent-level memory isolation with persistence |
| Skill System | Reusable prompt templates with triggers and parameter substitution |
| Permission Control | Fine-grained tool permission management (auto/manual/accept-all) |
| MCP Integration | Native Model Context Protocol support for extended tool ecosystem |

---

## Architecture

FeinnAgent follows a **layered architecture** with **modular design**:

```
┌───────────────────────────────────────────────────┐
│            Presentation Layer                       │
│      CLI  │  RESTful API  │  WebSocket (Future)    │
├───────────────────────────────────────────────────┤
│            Core Layer                              │
│   Agent Engine  │  Context Manager  │  Compaction  │
├───────────────────────────────────────────────────┤
│            Subsystem Layer                          │
│  Tools │ Memory │ Tasks │ Sub-Agent │ Permission   │
├───────────────────────────────────────────────────┤
│            Infrastructure Layer                     │
│   Provider Adapter  │  MCP Client  │  SQLite       │
└───────────────────────────────────────────────────┘
```

### Design Principles

- **Single Responsibility**: Each module handles one clear functional domain
- **Dependency Inversion**: High-level modules don't depend on low-level modules; both depend on abstractions
- **Open/Closed Principle**: Open for extension, closed for modification
- **Async-First**: All IO operations are asynchronous

---

## Usage Modes

### 1. Interactive CLI

```bash
feinn -i
```

Supports multi-turn conversations, context persistence, and real-time tool execution. Ideal for complex tasks.

### 2. One-Shot Command

```bash
feinn "Analyze the code structure of the current directory"
```

Suitable for simple queries and scripting.

### 3. API Server

```bash
feinn --serve --host 0.0.0.0 --port 8000
```

Provides a RESTful API for integration with other applications:
- `POST /chat` - Send messages
- `GET /health` - Health check
- `GET /models` - List supported models

---

## Supported Models

### Cloud Providers

| Provider | Format | Example |
|----------|--------|---------|
| SiliconFlow | `siliconflow/{model}` | `siliconflow/Pro/zai-org/GLM-5.1` |
| OpenAI | `openai/{model}` | `openai/gpt-4o` |
| Anthropic | `anthropic/{model}` | `anthropic/claude-sonnet-4` |
| Azure OpenAI | `azure/{deployment}` | `azure/gpt-4` |
| Gemini | `gemini/{model}` | `gemini/gemini-2.5-pro` |
| DeepSeek | `deepseek/{model}` | `deepseek/deepseek-v3` |

### Local Deployment

| Method | Format | Configuration |
|--------|--------|---------------|
| vLLM | `vllm/{model}` | Set `VLLM_BASE_URL` |
| Ollama | `ollama/{model}` | Set `OLLAMA_BASE_URL` |
| LM Studio | `lmstudio/{model}` | Auto-detected |

---

## Built-in Tools

FeinnAgent includes 20+ built-in tools:

| Category | Tools | Description |
|----------|-------|-------------|
| File Operations | `Read`, `Write`, `Edit` | File reading, writing, and editing |
| Search | `Glob`, `Grep` | File search and content matching |
| Execution | `Bash` | Shell command execution |
| Memory | `MemorySave`, `MemorySearch`, `MemoryList` | Knowledge persistence |
| Task Management | `TaskCreate`, `TaskGet`, `TaskList` | DAG task orchestration |
| Sub-Agent | `Agent`, `CheckAgentResult` | Concurrent sub-agent collaboration |
| Skill | `Skill`, `SkillList` | Reusable prompt templates |

---

## Skill System

Skills are reusable prompt templates that encapsulate common workflows, invoked quickly via trigger words.

### Built-in Skills

| Skill | Trigger | Description |
|-------|---------|-------------|
| `commit` | `/commit` | Review staged changes and create standardized git commits |
| `review` | `/review` | Review code or PRs with structured feedback |
| `explain` | `/explain` | Explain code in detail |
| `test` | `/test` | Generate test cases for specified code |
| `doc` | `/doc` | Generate or update documentation for code |

### Custom Skills

Create `.md` files in `~/.feinn/skills/` or the project's `.feinn/skills/` directory to register custom Skills. Supports frontmatter configuration for triggers, tool permissions, and parameter templates.

---

## Getting Started

### Requirements

- Python 3.11+
- macOS / Linux / Windows

### Installation

```bash
git clone https://github.com/PeiziLiu/FeinnAgent.git
cd feinn-agent
python3.11 -m venv .venv
source .venv/bin/activate
python3.11 -m pip install -e .
cp .env.example .env
# Edit .env to configure your API keys
```

### Configuration

Edit the `.env` file to set your model provider API keys:

```bash
# SiliconFlow (recommended for China region)
SILICONFLOW_API_KEY=sk-your-key
DEFAULT_MODEL=siliconflow/Pro/zai-org/GLM-5.1

# Or OpenAI
OPENAI_API_KEY=sk-your-key
DEFAULT_MODEL=openai/gpt-4o

# Or Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
DEFAULT_MODEL=anthropic/claude-sonnet-4
```

### Running

```bash
# Interactive mode
feinn -i

# One-shot query
feinn "your question"

# API server
feinn --serve
```

---

## Interactive Commands

| Command | Description |
|---------|-------------|
| `/quit` | Exit the program |
| `/help` | Show help |
| `/clear` | Clear conversation history |
| `/model [model]` | View or switch model |
| `/save` | Save session to file |
| `/tasks` | Show task list |
| `/memory` | Show memory list |
| `/skills` | List available Skills |
| `/config` | Show current configuration |
| `/accept-all` | Switch to accept-all mode |
| `/auto` | Switch to smart judgment mode |
| `/manual` | Switch to manual confirmation mode |

---

## Configuration Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `DEFAULT_MODEL` | Default model | `siliconflow/Pro/zai-org/GLM-5.1` |
| `SILICONFLOW_API_KEY` | SiliconFlow API key | `sk-...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key | `...` |
| `VLLM_BASE_URL` | vLLM service URL | `http://localhost:8000/v1` |
| `LOG_LEVEL` | Log level | `INFO` / `DEBUG` |
| `PERMISSION_MODE` | Permission mode | `accept_all` / `auto` / `manual` |

---

## Roadmap

### v1.0.0 - Foundation (Current)

- Multi-model support
- Basic tool system (20+ built-in tools)
- Context management and compression
- Dual-scope memory system
- DAG task orchestration
- Concurrent sub-agent system
- Permission control
- MCP protocol support
- RESTful API and CLI

### v1.1.0 - Stability Enhancement

- Streaming response optimization (SSE / WebSocket)
- Performance optimization (connection pooling, caching strategies)
- Monitoring and observability (Prometheus / Grafana)

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Primary language |
| asyncio | Async concurrency |
| FastAPI | API server |
| Pydantic 2.0+ | Data validation |
| SQLite | Local storage |
| MCP | Tool protocol extension |

---

## License

Apache License 2.0

## Contact

- Email: hanfazy@126.com
- Issues: [GitHub Issues](https://github.com/PeiziLiu/FeinnAgent/issues)
