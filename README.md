# FeinnAgent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License: Apache 2.0">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-2.0+-e92063.svg" alt="Pydantic 2.0+">
</p>

<p align="center">
  <b>企业级多并发 AI Agent 框架</b><br>
  基于 Python 构建，支持多模型、多并发、上下文压缩、任务编排与子代理协作
</p>

---

## 特性

- **多模型支持**: 原生支持 OpenAI、Anthropic Claude，可扩展至任意 LLM 提供商
- **企业级并发**: 基于 asyncio 的高性能并发架构，支持多会话并行处理
- **智能上下文压缩**: 自动检测上下文窗口，智能压缩历史消息，确保长对话稳定性
- **任务编排系统**: 内置 DAG 任务管理，支持任务依赖、优先级和状态追踪
- **子代理协作**: 支持并发启动多个子代理，实现复杂任务的并行分解与执行
- **双作用域内存**: Workspace 级与 Agent 级内存隔离，灵活的知识管理
- **Skill 系统**: 可复用的提示模板，支持触发器、参数替换和工具限制
- **权限控制**: 细粒度的工具权限管理，支持自动审批、手动确认和只读模式
- **MCP 集成**: 原生支持 Model Context Protocol，可接入任意 MCP 服务
- **RESTful API**: 基于 FastAPI 的高性能 API 服务，支持 SSE 实时推送
- **CLI 工具**: 功能完善的命令行界面，支持交互式会话和批量任务

---

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/your-org/feinn-agent.git
cd feinn-agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -e ".[dev]"

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，添加你的 API 密钥
```

### 环境配置

编辑 `.env` 文件：

```env
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic (可选)
ANTHROPIC_API_KEY=sk-ant-...

# 其他配置
FEINN_LOG_LEVEL=INFO
FEINN_DEFAULT_PERMISSION=auto
```

### 命令行使用

```bash
# 启动交互式会话
feinn chat

# 执行单条命令
feinn run "分析当前目录的代码结构"

# 启动 API 服务
feinn serve --host 0.0.0.0 --port 8000
```

### API 使用

```python
import asyncio
from feinn_agent import Agent, AgentConfig

async def main():
    config = AgentConfig(
        model="openai/gpt-4o",
        permission_mode="auto"
    )

    agent = Agent(config)

    result = await agent.run("创建一个简单的 Python HTTP 服务器")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   REST API  │  │   SSE       │  │   WebSocket (未来)  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Agent Core                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Agent     │  │   Context   │  │   Compaction        │  │
│  │   Engine    │  │   Manager   │  │   Engine            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Subsystems                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │  Tools   │ │  Memory  │ │  Tasks   │ │  Subagents     │  │
│  │  System  │ │  System  │ │  System  │ │  System        │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Providers & MCP                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │  OpenAI  │ │Anthropic │ │  Other   │ │  MCP Servers   │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心模块

### 1. Agent 引擎

Agent 是核心执行单元，负责：
- 管理对话循环和工具调用
- 维护上下文状态
- 协调子系统工作
- 处理并发请求

```python
from feinn_agent import Agent, AgentConfig

config = AgentConfig(
    model="openai/gpt-4o",
    max_iterations=50,
    context_window=128000
)

agent = Agent(config)
```

### 2. 工具系统

内置 22 个工具，分为九类：

| 类别 | 工具 | 说明 |
|------|------|------|
| **文件操作** | Read, Write, Edit | 文件读写编辑 |
| **搜索** | Glob, Grep | 文件搜索与内容查找 |
| **执行** | Bash | 命令执行 |
| **Web** | WebFetch | 网络请求 |
| **交互** | AskUserQuestion | 用户确认 |
| **内存管理** | MemorySave, MemorySearch, MemoryList, MemoryDelete | 双作用域知识管理 |
| **任务管理** | TaskCreate, TaskGet, TaskList, TaskUpdate | DAG 任务编排 |
| **子代理** | Agent, CheckAgentResult, ListAgentTasks, ListAgentTypes | 并发子代理协作 |
| **Skill** | Skill, SkillList | 可复用提示模板 |

### 3. 上下文压缩

智能上下文管理系统：
- 自动检测上下文长度
- 分层压缩策略（摘要、截断、丢弃）
- 保留关键消息（系统提示、用户指令）
- 可配置的压缩阈值

### 4. 任务系统

基于 DAG 的任务编排：
- 任务依赖管理
- 优先级调度
- 状态追踪（pending/running/completed/failed）
- 并发执行控制

### 5. 子代理系统

支持并发子代理：
- 动态创建子代理
- 并行任务分解
- 结果聚合
- 资源隔离

### 6. Skill 系统

可复用的提示模板系统：
- 触发器机制（如 `/commit`）
- 参数替换（`$ARGUMENTS`, `$PR`）
- 工具限制（指定可用工具集）
- 上下文模式（inline/fork）

**使用内置 Skill**:
```python
# 使用 Skill 工具调用
await agent.run("使用 Skill 工具执行 commit")

# 或直接触发
await agent.run("/commit 修复登录bug")
```

**创建自定义 Skill**:
```markdown
---
name: deploy
description: Deploy the application
triggers: ["/deploy"]
tools: ["Bash", "Read"]
---

Deploy the app to production:
1. Run tests: `npm test`
2. Build: `npm run build`
3. Deploy: `npm run deploy`
```

---

## 企业级特性

### 高并发架构

```python
# 并发执行多个子代理
results = await asyncio.gather(
    agent.run_subagent("分析代码结构", agent_type="analyzer"),
    agent.run_subagent("检查依赖安全", agent_type="security"),
    agent.run_subagent("生成测试用例", agent_type="tester")
)
```

### 权限控制

三种权限模式：
- `accept_all`: 自动接受所有工具调用
- `auto`: 智能判断（破坏性操作需确认）
- `confirm_all`: 所有操作需人工确认

### 内存隔离

- **Workspace 内存**: 跨会话共享的项目知识
- **Agent 内存**: 会话级别的临时记忆

### MCP 集成

```python
# 配置 MCP 服务器
config.mcp_servers = {
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
    }
}
```

---

## 项目结构

```
feinn-agent/
├── src/feinn_agent/
│   ├── __init__.py
│   ├── agent.py              # 核心 Agent 实现
│   ├── types.py              # 类型定义
│   ├── config.py             # 配置管理
│   ├── providers.py          # LLM 提供商适配
│   ├── context.py            # 上下文管理
│   ├── compaction.py         # 上下文压缩
│   ├── permission.py         # 权限控制
│   ├── tools/                # 工具系统
│   │   ├── registry.py       # 工具注册中心
│   │   ├── builtins.py       # 内置工具
│   │   └── ...
│   ├── memory/               # 内存系统
│   ├── task/                 # 任务系统
│   ├── subagent/             # 子代理系统
│   ├── mcp/                  # MCP 集成
│   ├── server/               # API 服务
│   └── cli/                  # 命令行工具
├── tests/                    # 测试套件
├── docs/                     # 文档
├── pyproject.toml
└── README.md
```

---

## 开发指南

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_agent.py -v

# 带覆盖率报告
pytest tests/ --cov=feinn_agent --cov-report=html
```

### 代码检查

```bash
# 格式化
ruff format src/

# 检查
ruff check src/

# 类型检查
mypy src/feinn_agent/
```

### 添加新工具

```python
from feinn_agent.tools import register_tool

@register_tool(
    name="my_tool",
    description="工具描述",
    parameters={
        "type": "object",
        "properties": {
            "param": {"type": "string"}
        }
    }
)
async def my_tool(param: str, context: ToolContext) -> str:
    """工具实现"""
    return f"结果: {param}"
```

---

## 文档

- [需求设计文档](docs/requirements.md) - 功能需求与用例分析
- [架构设计文档](docs/architecture.md) - 系统架构与模块设计
- [技术设计文档](docs/technical.md) - 详细技术实现方案
- [开发路线图](docs/roadmap.md) - 版本规划与里程碑

---

## 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 许可证

本项目采用 Apache License 2.0 - 详见 [LICENSE](LICENSE) 文件

---

## 致谢

FeinnAgent 的设计参考了以下优秀项目：
- [CheetahClaws](https://github.com/fishdoll/cheetahclaws) - Python Agent 架构灵感
- [Claude Code](https://github.com/anthropics/claude-code) - 工具系统与交互设计
- [Hermes Agent](https://github.com/fishdoll/hermes-agent) - 企业级特性参考

---

<p align="center">
  Built with ❤️ by Feinn Team
</p>
