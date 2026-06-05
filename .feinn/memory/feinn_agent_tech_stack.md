---
name: feinn_agent_tech_stack
description: FeinnAgent 技术栈与工具链配置
type: project
confidence: 0.95
source: user
last_used_at: 2026-06-05
conflict_group: feinn_agent_tech_stack
---
FeinnAgent 技术栈详情：
- Python >=3.11，hatchling 构建
- 核心依赖: anthropic>=0.42, openai>=1.50, httpx>=0.27, fastapi>=0.115, uvicorn>=0.30, pydantic>=2.9, rich>=13.9, prompt-toolkit>=3.0, click>=8.1, pyyaml>=6.0, watchdog>=5.0, aiofiles>=24.1, python-dotenv>=1.0
- 开发依赖: pytest>=8.3, pytest-asyncio>=0.24, pytest-cov>=5.0, ruff>=0.6
- Ruff 配置: target-version py311, line-length 120, lint select E/F/I/N/W/UP
- pytest 配置: asyncio_mode=auto, testpaths=["tests"]
- 项目入口脚本: `feinn` 映射到 `feinn_agent.cli:main`