---
name: feinn-agent-cli-architecture
description: Architecture overview of feinn-agent CLI mode
type: project
confidence: 1.0
source: user
last_used_at: 2026-05-31
conflict_group: feinn-agent-cli-architecture
---
Project: feinn-agent (enterprise async AI agent framework)
CLI Entry: src/feinn_agent/cli.py using Click framework
Entry point: feinn = "feinn_agent.cli:main" in pyproject.toml

Key CLI Features:
- Interactive REPL mode (default) with prompt_toolkit for multibyte char handling
- One-shot mode: feinn "prompt"
- API server mode: feinn --serve
- 15+ slash commands: /quit, /help, /model, /clear, /save, /tasks, /memory, /skills, /config, /accept-all, /auto, /manual, /plan, /checkpoint, /interrupt, /resume, /trajectory
- Skill activator system (e.g., /commit, /review, /explain, /test, /doc)
- Permission callbacks with y/n/A options
- MCP initialization/shutdown lifecycle
- KawaiiDisplay for tool execution visualization
- Cost estimation on AgentDone events
- Session saving to ~/.feinn/sessions/

Config System (config.py):
- Layered: defaults → ~/.feinn/config.json → env vars (via _ENV_MAP)
- Supports FEINN_HOME env var
- 20+ API providers mapped
- Daily rotating logs via TimedRotatingFileHandler

Notable Gaps:
- No dedicated CLI tests in tests/ directory
- /resume command is stub ("requires session state preservation")
- Error handling is basic try/except around agent.run()