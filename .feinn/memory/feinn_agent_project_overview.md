---
name: feinn_agent_project_overview
description: FeinnAgent 项目概览与架构
type: project
confidence: 0.95
source: user
last_used_at: 2026-06-05
conflict_group: feinn_agent_project_overview
---
FeinnAgent 是一个企业级 Python AI Agent 框架，位于 /Users/fisherhe/work/feinn-agent。

**技术栈**: Python 3.11+, asyncio, Pydantic 2, FastAPI, Rich, prompt-toolkit, click, SQLite
**构建工具**: hatchling, uv, ruff, pytest
**入口**: `feinn = feinn_agent.cli:main`

**核心模块** (src/feinn_agent/):
- agent.py - Agent 引擎主循环
- cli.py / cli_tui.py - CLI 与 TUI 界面
- display/ - 显示系统（kawaii 风格进度条、diff 显示）
- config.py / context.py / providers.py - 配置、上下文、模型适配
- checkpoint/ - Git 快照与回滚
- compaction.py - 上下文压缩
- memory/ / task/ / plan/ - 记忆、任务、计划系统
- skill/ - 可复用 Skill 模板（加载器、执行器、策展）
- subagent/ - 并发子 Agent 管理
- tools/ - 20+ 内置工具（含 browser 多提供商支持）
- mcp/ - Model Context Protocol 客户端
- interrupt/ / permission/ / trajectory/ - 中断、权限、轨迹
- learning/ - 闭环学习（review, nudge, session_store）

**架构**: 分层设计（Presentation -> Core -> Subsystem -> Infrastructure）
**测试**: tests/ 目录，pytest + pytest-asyncio + pytest-cov