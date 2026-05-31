---
name: feinn_agent_tech_stack
description: Complete dependency and tooling configuration for feinn-agent
type: project
confidence: 1.0
source: user
last_used_at: 2026-06-01
conflict_group: feinn_agent_tech_stack
---
Technology stack and dependencies:
- Python 3.11+ (target-version for ruff)
- Build: hatchling
- Core async: asyncio, httpx>=0.27.0
- Web framework: FastAPI>=0.115.0, uvicorn>=0.30.0
- Data validation: pydantic>=2.9.0
- CLI/TUI: click>=8.1.0, rich>=13.9.0, prompt-toolkit>=3.0.0
- LLM APIs: anthropic>=0.42.0, openai>=1.50.0
- Config: pyyaml>=6.0.0, python-dotenv>=1.0.0, aiofiles>=24.1.0
- File watching: watchdog>=5.0.0
- Testing: pytest>=8.3.0, pytest-asyncio>=0.24.0, pytest-cov>=5.0.0
- Linting: ruff>=0.6.0 (line-length 120, rules: E,F,I,N,W,UP)
- Entry point: feinn = feinn_agent.cli:main
- Project layout: src/ layout with hatch build