---
name: feinn_agent_overview
description: FeinnAgent project overview and current state
type: project
confidence: 1.0
source: user
last_used_at: 2026-06-05
conflict_group: feinn_agent_overview
---
FeinnAgent is an enterprise-grade async AI agent framework (Python 3.11+, Apache 2.0).

**Tech Stack**: asyncio, Pydantic 2, FastAPI, Rich, prompt-toolkit, click, SQLite, uv.

**Key Modules**:
- Agent Engine (core conversation loop)
- Context Manager + Compaction Engine
- Tool System (20+ built-in tools, browser automation, MCP)
- Memory System (dual-scope: user/project)
- Task System (DAG orchestration)
- Subagent System (concurrent collaboration)
- Skill System (reusable templates)
- CLI / TUI / API Server (3 usage modes)

**Current Branch**: cli_optimize
**Recent Work**: CLI/TUI/Display enhancements. Files modified: cli.py, cli_tui.py, display/__init__.py, tests.
**Key Config**: pyproject.toml (hatchling build, ruff lint, pytest-asyncio). Entry point: `feinn = feinn_agent.cli:main`.

**Directory Layout**:
- src/feinn_agent/ — core source
- tests/ — pytest suite (25+ test files)
- docs/ — extensive requirements + technical docs