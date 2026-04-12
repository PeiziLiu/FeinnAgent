# FeinnAgent Wiki

<p align="center">
  <a href="wiki.md">English</a> | <strong>中文</strong>
</p>

## 项目简介

FeinnAgent 是一个**企业级多并发 AI Agent 框架**，基于 Python 构建，专为复杂的 AI 代理任务设计。它支持多模型接入、多并发执行、智能上下文压缩、DAG 任务编排与子代理协作，适用于个人开发者和企业级应用场景。

---

## 核心特性

| 特性 | 说明 |
|------|------|
| 多模型支持 | 原生支持 10+ 家 LLM 提供商（OpenAI、Anthropic、SiliconFlow、Azure、Gemini、DeepSeek 等） |
| 企业级并发 | 基于 asyncio 的高性能异步并发架构 |
| 智能上下文压缩 | 自动检测上下文窗口，智能压缩历史消息，避免 token 超限 |
| DAG 任务编排 | 内置有向无环图任务管理，支持任务依赖和状态追踪 |
| 子代理协作 | 支持并发启动多个子代理，实现复杂任务并行分解 |
| 双作用域内存 | Workspace 级与 Agent 级内存隔离，知识持久化 |
| Skill 系统 | 可复用的提示模板，支持触发器和参数替换 |
| 权限控制 | 细粒度的工具权限管理（自动/手动/全部接受） |
| MCP 集成 | 原生支持 Model Context Protocol，扩展工具生态 |

---

## 系统架构

FeinnAgent 采用**分层架构**与**模块化设计**：

```
┌───────────────────────────────────────────────────┐
│              表现层 (Presentation)                  │
│    CLI 交互  │  RESTful API  │  WebSocket（未来）  │
├───────────────────────────────────────────────────┤
│              核心层 (Core)                          │
│  Agent 引擎  │  上下文管理  │  压缩引擎            │
├───────────────────────────────────────────────────┤
│              子系统层 (Subsystem)                   │
│  工具系统 │ 内存系统 │ 任务系统 │ 子代理 │ 权限    │
├───────────────────────────────────────────────────┤
│              基础设施层 (Infrastructure)            │
│  Provider 适配器  │  MCP 客户端  │  SQLite         │
└───────────────────────────────────────────────────┘
```

### 设计原则

- **单一职责**: 每个模块负责一个清晰的功能域
- **依赖反转**: 高层模块不依赖低层模块，都依赖于抽象
- **开闭原则**: 对扩展开放，对修改封闭
- **异步优先**: 所有 IO 操作均为异步

---

## 使用模式

### 1. 交互式 CLI

```bash
feinn -i
```

支持多轮对话、上下文保持、工具实时执行，适合复杂任务。

### 2. 一次性命令

```bash
feinn "分析当前目录的代码结构"
```

适合简单查询和脚本调用。

### 3. API 服务

```bash
feinn --serve --host 0.0.0.0 --port 8000
```

提供 RESTful API，适合集成到其他应用：
- `POST /chat` - 发送消息
- `GET /health` - 健康检查
- `GET /models` - 列出支持的模型

---

## 支持的模型

### 云服务商

| 提供商 | 格式 | 示例 |
|--------|------|------|
| SiliconFlow | `siliconflow/{model}` | `siliconflow/Pro/zai-org/GLM-5.1` |
| OpenAI | `openai/{model}` | `openai/gpt-4o` |
| Anthropic | `anthropic/{model}` | `anthropic/claude-sonnet-4` |
| Azure OpenAI | `azure/{deployment}` | `azure/gpt-4` |
| Gemini | `gemini/{model}` | `gemini/gemini-2.5-pro` |
| DeepSeek | `deepseek/{model}` | `deepseek/deepseek-v3` |

### 本地部署

| 方式 | 格式 | 配置 |
|------|------|------|
| vLLM | `vllm/{model}` | 设置 `VLLM_BASE_URL` |
| Ollama | `ollama/{model}` | 设置 `OLLAMA_BASE_URL` |
| LM Studio | `lmstudio/{model}` | 自动检测 |

---

## 内置工具

FeinnAgent 内置 20+ 工具：

| 类别 | 工具 | 说明 |
|------|------|------|
| 文件操作 | `Read`, `Write`, `Edit` | 文件读写编辑 |
| 搜索 | `Glob`, `Grep` | 文件搜索与内容查找 |
| 执行 | `Bash` | Shell 命令执行 |
| 内存管理 | `MemorySave`, `MemorySearch`, `MemoryList` | 知识持久化管理 |
| 任务管理 | `TaskCreate`, `TaskGet`, `TaskList` | DAG 任务编排 |
| 子代理 | `Agent`, `CheckAgentResult` | 并发子代理协作 |
| Skill | `Skill`, `SkillList` | 可复用提示模板 |

---

## Skill 系统

Skill 是封装常见工作流程的可复用提示模板，通过触发词快速调用。

### 内置 Skill

| Skill | 触发词 | 说明 |
|-------|--------|------|
| `commit` | `/commit` | 审查暂存更改并创建规范的 git 提交 |
| `review` | `/review` | 审查代码或 PR 并提供结构化反馈 |
| `explain` | `/explain` | 详细解释代码 |
| `test` | `/test` | 为指定代码生成测试用例 |
| `doc` | `/doc` | 为代码生成或更新文档 |

### 自定义 Skill

在 `~/.feinn/skills/` 或项目 `.feinn/skills/` 目录下创建 `.md` 文件即可注册自定义 Skill，支持 frontmatter 配置触发词、工具权限、参数模板等。

---

## 快速开始

### 环境要求

- Python 3.11+
- macOS / Linux / Windows

### 安装

```bash
git clone https://github.com/PeiziLiu/FeinnAgent.git
cd feinn-agent
python3.11 -m venv .venv
source .venv/bin/activate
python3.11 -m pip install -e .
cp .env.example .env
# 编辑 .env 配置 API 密钥
```

### 配置

编辑 `.env` 文件，设置模型提供商的 API 密钥：

```bash
# SiliconFlow（推荐，国内可用）
SILICONFLOW_API_KEY=sk-your-key
DEFAULT_MODEL=siliconflow/Pro/zai-org/GLM-5.1

# 或 OpenAI
OPENAI_API_KEY=sk-your-key
DEFAULT_MODEL=openai/gpt-4o

# 或 Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
DEFAULT_MODEL=anthropic/claude-sonnet-4
```

### 运行

```bash
# 交互模式
feinn -i

# 一次性提问
feinn "你的问题"

# API 服务
feinn --serve
```

---

## 交互模式命令

| 命令 | 说明 |
|------|------|
| `/quit` | 退出程序 |
| `/help` | 显示帮助 |
| `/clear` | 清空对话历史 |
| `/model [model]` | 查看或切换模型 |
| `/save` | 保存会话到文件 |
| `/tasks` | 显示任务列表 |
| `/memory` | 显示记忆列表 |
| `/skills` | 列出可用的 Skill |
| `/config` | 显示当前配置 |
| `/accept-all` | 切换到自动接受模式 |
| `/auto` | 切换到智能判断模式 |
| `/manual` | 切换到手动确认模式 |

---

## 配置参考

| 变量 | 说明 | 示例 |
|------|------|------|
| `DEFAULT_MODEL` | 默认模型 | `siliconflow/Pro/zai-org/GLM-5.1` |
| `SILICONFLOW_API_KEY` | SiliconFlow 密钥 | `sk-...` |
| `OPENAI_API_KEY` | OpenAI 密钥 | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic 密钥 | `sk-ant-...` |
| `AZURE_OPENAI_API_KEY` | Azure 密钥 | `...` |
| `VLLM_BASE_URL` | vLLM 服务地址 | `http://localhost:8000/v1` |
| `LOG_LEVEL` | 日志级别 | `INFO` / `DEBUG` |
| `PERMISSION_MODE` | 权限模式 | `accept_all` / `auto` / `manual` |

---

## 开发路线

### v1.0.0 - 基础版本（当前）

- 多模型支持
- 基本工具系统（20+ 内置工具）
- 上下文管理与压缩
- 双作用域内存系统
- DAG 任务编排
- 并发子代理系统
- 权限控制
- MCP 协议支持
- RESTful API 与 CLI

### v1.1.0 - 稳定性增强

- 流式响应优化（SSE / WebSocket）
- 性能优化（连接池、缓存策略）
- 监控与可观测性（Prometheus / Grafana）

---

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.11+ | 主语言 |
| asyncio | 异步并发 |
| FastAPI | API 服务 |
| Pydantic 2.0+ | 数据验证 |
| SQLite | 本地存储 |
| MCP | 工具协议扩展 |

---

## 许可证

Apache License 2.0

## 联系方式

- 邮箱: hanfazy@126.com
- 问题反馈: [GitHub Issues](https://github.com/PeiziLiu/FeinnAgent/issues)
