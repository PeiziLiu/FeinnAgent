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
</p>

<p align="center">
  <a href="README.zh.md">中文</a> | <strong>English</strong>
</p>

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Modes](#usage-modes)
- [Command Reference](#command-reference)
- [Supported Models](#supported-models)
- [Architecture Features](#architecture-features)
- [Development Guide](#development-guide)

---

## Installation

### Requirements

- Python 3.11+
- macOS / Linux / Windows

### Installation Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-org/feinn-agent.git
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
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key | `...` |
| `AZURE_OPENAI_URL` | Azure OpenAI endpoint | `https://...` |
| `VLLM_BASE_URL` | vLLM service URL | `http://localhost:8000/v1` |
| `VLLM_API_KEY` | vLLM API key (optional) | `sk-...` |
| `LOG_LEVEL` | Log level | `INFO` / `DEBUG` |
| `LOG_FILE` | Log file path | `~/.feinn/feinn.log` |
| `PERMISSION_MODE` | Permission mode | `accept_all` / `auto` / `manual` |

### Permission Modes

| Mode | Description |
|------|-------------|
| `accept_all` | Auto-accept all tool calls (default) |
| `auto` | Smart judgment, destructive operations require confirmation |
| `manual` | All tool calls require manual confirmation |

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

| Category | Tools | Description |
|----------|-------|-------------|
| File Operations | `Read`, `Write`, `Edit` | File read/write/edit |
| Search | `Glob`, `Grep` | File search and content lookup |
| Execution | `Bash` | Command execution |
| Memory | `MemorySave`, `MemorySearch`, `MemoryList` | Knowledge management |
| Task Management | `TaskCreate`, `TaskGet`, `TaskList` | DAG task orchestration |
| Sub-Agent | `Agent`, `CheckAgentResult` | Concurrent sub-agent collaboration |
| Skill | `Skill`, `SkillList` | Reusable prompt templates |

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
```

### Code Formatting

```bash
# Format code
python3.11 -m ruff format src/

# Check code
python3.11 -m ruff check src/
```

### Adding New Tools

```python
from feinn_agent.tools.registry import register

@register(
    name="my_tool",
    description="Tool description",
    input_schema={
        "type": "object",
        "properties": {
            "param": {"type": "string"}
        }
    }
)
async def my_tool(param: str) -> str:
    """Tool implementation"""
    return f"Result: {param}"
```

---

## Documentation

- [vLLM Deployment Guide](docs/vllm-deployment.md) - Self-hosted model deployment
- [SiliconFlow Setup](docs/siliconflow-setup.md) - China API platform usage
- [Azure OpenAI Setup](docs/azure-openai-setup.md) - Enterprise Azure deployment

---

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details

---

## Contact & Support

- **Email**: hanfazy@126.com
- **Issues**: [GitHub Issues](https://github.com/your-org/feinn-agent/issues)

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
