---
name: feinn_agent_project_overview
description: Complete project overview of feinn-agent codebase
type: project
confidence: 1.0
source: user
last_used_at: 2026-06-01
conflict_group: feinn_agent_project_overview
---
FeinnAgent is an enterprise-grade async AI agent framework built with Python 3.11+. Key stats:
- ~12,700 lines of Python code across src/feinn_agent/
- Core modules: agent.py (341 lines), cli.py (814), cli_tui.py (907), display/__init__.py (784), providers.py (567), plan/__init__.py (471), checkpoint/__init__.py (518)
- Architecture: async generator agent loop with concurrent tool execution, dual-scope memory (user/project), skill template system, DAG task orchestration, sub-agent collaboration
- 10+ LLM providers supported (OpenAI, Anthropic, Gemini, DeepSeek, SiliconFlow, Azure, vLLM, Ollama, LM Studio)
- Three usage modes: interactive CLI (click+prompt-toolkit), one-shot commands, FastAPI REST server
- 20+ built-in tools including browser automation (multi-provider: local/Firecrawl/Browserbase/Browseruse), file ops, bash, diagnostics, tmux, memory, tasks
- MCP (Model Context Protocol) integration with stdio/sse/http transport
- Git-based checkpoint/rollback system
- Closed-loop learning system with nudge counters and background review