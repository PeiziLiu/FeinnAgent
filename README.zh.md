# FeinnAgent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License: Apache 2.0">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-2.0+-e92063.svg" alt="Pydantic 2.0+">
</p>

<p align="center">
  <b>企业级多并发 AI Agent 框架</b><br>
  基于 Python 构建，支持多模型、多并发、上下文压缩、任务编排与子代理协作
</p>

<p align="center">
  <strong>中文</strong> | <a href="README.md">English</a>
</p>

---

FeinnAgent 是一个基于 Python 的企业级多并发 AI Agent 框架，同时面向本地开发与服务端部署场景。它提供开箱即用的多模型接入（支持 OpenAI、Anthropic、SiliconFlow、Azure、Gemini、DeepSeek 等 10+ 家 LLM 提供商）、智能上下文压缩、DAG 任务编排、子代理并发协作以及双作用域内存系统。通过内置的 20+ 工具、Skill 可复用模板和 MCP 协议扩展，FeinnAgent 能够高效处理从简单问答到复杂多步骤任务的各种场景。框架提供交互式 CLI、一次性命令和生产就绪的 RESTful API 服务三种使用方式，既适合开发者本地快速验证，也支持在企业基础设施中进行规模化部署。

## 目录

- [安装](#安装)
- [快速开始](#快速开始)
- [配置](#配置)
- [使用模式](#使用模式)
- [命令参考](#命令参考)
- [支持模型](#支持模型)
- [架构特性](#架构特性)
- [项目结构](#项目结构)
- [Skill 系统](#skill-系统)
- [开发指南](#开发指南)
- [文档](#文档)

---

## 安装

### 环境要求

- Python 3.11+
- macOS / Linux / Windows

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/PeiziLiu/FeinnAgent.git
cd feinn-agent

# 2. 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
python3.11 -m pip install -e .

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置你的 API 密钥
```

---

## 快速开始

### 1. 配置 API 密钥

编辑 `.env` 文件，选择你要使用的模型提供商：

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

# 或 Azure OpenAI
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_URL=https://your-resource.openai.azure.com/...
DEFAULT_MODEL=azure/gpt-4

# 或 vLLM 自托管
VLLM_BASE_URL=http://localhost:8000/v1
DEFAULT_MODEL=vllm/Qwen2.5-72B-Instruct
```

### 2. 启动交互模式

```bash
# 启动交互式会话（推荐）
feinn -i

# 或一次性提问
feinn "分析当前目录的代码结构"

# 启动 API 服务
feinn --serve
```

### 3. 交互模式使用

启动 `feinn -i` 后，你会看到：

```
  FeinnAgent v0.1.0
  Model: siliconflow/Pro/zai-org/GLM-5.1
  Type '/quit' to exit, '/help' for commands

feinn> 你好
```

直接输入你的问题，Agent 会保持对话上下文。

---

## 配置

### 环境变量 (.env)

| 变量 | 说明 | 示例 |
|------|------|------|
| `DEFAULT_MODEL` | 默认使用的模型 | `siliconflow/Pro/zai-org/GLM-5.1` |
| `SILICONFLOW_API_KEY` | SiliconFlow API 密钥 | `sk-...` |
| `OPENAI_API_KEY` | OpenAI API 密钥 | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | `sk-ant-...` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI 密钥 | `...` |
| `AZURE_OPENAI_URL` | Azure OpenAI 端点 | `https://...` |
| `VLLM_BASE_URL` | vLLM 服务地址 | `http://localhost:8000/v1` |
| `VLLM_API_KEY` | vLLM API 密钥（可选） | `sk-...` |
| `LOG_LEVEL` | 日志级别 | `INFO` / `DEBUG` |
| `LOG_FILE` | 日志文件路径 | `~/.feinn/feinn.log` |
| `PERMISSION_MODE` | 权限模式 | `accept-all` / `auto` / `manual` / `plan` |

### 权限模式

| 模式 | 说明 |
|------|------|
| `accept-all` | 自动接受所有工具调用（默认） |
| `auto` | 智能判断，破坏性操作需确认 |
| `manual` | 所有工具调用需人工确认 |
| `plan` | 只读模式，仅允许计划文件写入 |

---

## 使用模式

### 模式一：交互式 CLI（推荐）

适合多轮对话、复杂任务：

```bash
feinn -i
```

**特点**：
- 保持对话上下文
- 支持多轮追问
- 实时显示工具执行
- 内置命令快捷操作

**示例会话**：
```
feinn> 读取 README.md 文件
[Tool: Read] 读取中...
文件内容：...

feinn> 总结一下这个项目是做什么的
基于刚才的内容，这是一个...

feinn> 帮我创建一个简单的示例
[Tool: Write] 写入文件 example.py...
已创建示例文件。
```

### 模式二：一次性命令

适合简单查询、脚本调用：

```bash
feinn "你的问题或指令"
```

**示例**：
```bash
feinn "解释 Python 的 asyncio 原理"
feinn "检查当前目录的代码风格问题"
feinn "生成一个 Flask 项目的 Dockerfile"
```

### 模式三：API 服务

适合集成到其他应用：

```bash
# 启动服务
feinn --serve --host 0.0.0.0 --port 8000

# 或使用环境变量
SERVER_HOST=0.0.0.0 SERVER_PORT=8000 feinn --serve
```

**API 端点**：
- `POST /chat` - 发送消息
- `GET /health` - 健康检查
- `GET /models` - 列出支持的模型

---

## 命令参考

### 全局选项

```bash
feinn [OPTIONS] [PROMPT]

Options:
  -i, --interactive    启动交互式 REPL 模式
  --serve              启动 API 服务
  --model TEXT         指定模型
  --accept-all         自动接受所有工具调用
  --thinking           启用扩展思考模式
  --host TEXT          服务主机地址
  --port INTEGER       服务端口
  --help               显示帮助信息
```

### 交互模式命令

在 `feinn -i` 交互模式下，可以使用以下命令：

| 命令 | 说明 |
|------|------|
| `/quit` 或 `/q` | 退出程序 |
| `/help` 或 `/h` | 显示帮助 |
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

### 使用示例

```bash
# 交互模式
feinn -i

# 一次性提问
feinn "如何优化这段代码？"

# 指定模型
feinn --model openai/gpt-4o "解释量子计算"

# 自动接受所有操作
feinn -i --accept-all

# 启动 API 服务
feinn --serve --port 8080

# 使用 vLLM 本地模型
feinn --model vllm/Qwen2.5-72B-Instruct -i
```

---

## 支持模型

### 云服务商

| 提供商 | 模型格式 | 示例 |
|--------|----------|------|
| SiliconFlow | `siliconflow/{model}` | `siliconflow/Pro/zai-org/GLM-5.1` |
| OpenAI | `openai/{model}` | `openai/gpt-4o` |
| Anthropic | `anthropic/{model}` | `anthropic/claude-sonnet-4` |
| Azure OpenAI | `azure/{deployment}` | `azure/gpt-4` |
| Gemini | `gemini/{model}` | `gemini/gemini-2.5-pro` |
| DeepSeek | `deepseek/{model}` | `deepseek/deepseek-v3` |

### 本地部署

| 方式 | 模型格式 | 配置 |
|------|----------|------|
| vLLM | `vllm/{model}` | `VLLM_BASE_URL` |
| Ollama | `ollama/{model}` | `OLLAMA_BASE_URL` |
| LM Studio | `lmstudio/{model}` | 自动检测 |

---

## 架构特性

### 核心特性

- **多模型支持**: 原生支持 10+ 家 LLM 提供商
- **企业级并发**: 基于 asyncio 的高性能并发架构
- **智能上下文压缩**: 自动检测上下文窗口，智能压缩历史消息
- **任务编排系统**: 内置 DAG 任务管理，支持任务依赖和状态追踪
- **子代理协作**: 支持并发启动多个子代理，实现复杂任务并行分解
- **双作用域内存**: Workspace 级与 Agent 级内存隔离
- **Skill 系统**: 可复用的提示模板，支持触发器和参数替换
- **权限控制**: 细粒度的工具权限管理
- **MCP 集成**: 原生支持 Model Context Protocol

### 内置工具（20+）

| 类别 | 工具 | 说明 |
|------|------|------|
| 文件操作 | `Read`, `Write`, `Edit` | 文件读写编辑 |
| 搜索 | `Glob`, `Grep` | 文件搜索与内容查找 |
| 执行 | `Bash` | 命令执行 |
| Tmux | `TmuxNewSession`, `TmuxSendKeys`, `TmuxCapture` | 持久会话管理 |
| 诊断 | `GetDiagnostics` | 代码检查与类型检查 |
| 内存管理 | `MemorySave`, `MemorySearch`, `MemoryList` | 知识管理 |
| 任务管理 | `TaskCreate`, `TaskGet`, `TaskList` | DAG 任务编排 |
| 子代理 | `Agent`, `CheckAgentResult` | 并发子代理协作 |
| Skill | `Skill`, `SkillList` | 可复用提示模板 |

---

## 项目结构

```
feinn-agent/
├── src/feinn_agent/          # 主包
│   ├── __init__.py           # 公共 API 导出
│   ├── agent.py              # 核心 Agent 循环（异步生成器）
│   ├── cli.py                # CLI 入口（基于 Click）
│   ├── config.py             # 配置加载（.env + YAML）
│   ├── types.py              # 核心类型定义（dataclasses）
│   ├── providers.py          # LLM Provider 适配器（OpenAI、Anthropic 等）
│   ├── context.py            # 上下文窗口管理
│   ├── compaction.py         # 上下文压缩引擎
│   ├── server.py             # FastAPI REST API 服务
│   ├── tools/                # 工具系统
│   │   ├── registry.py       # 工具注册与调度
│   │   ├── builtins.py       # 内置工具（Read/Write/Edit/Bash/Glob/Grep）
│   │   ├── process.py        # 进程树管理
│   │   ├── tmux.py           # Tmux 持久会话工具
│   │   ├── diagnostics.py    # 代码诊断（pyright/eslint/shellcheck）
│   │   ├── output.py         # 输出处理（截断/ANSI 清理）
│   │   └── skills.py         # Skill 工具封装
│   ├── memory/               # 双作用域内存系统
│   │   └── store.py          # 内存存储与检索
│   ├── task/                 # DAG 任务编排
│   │   └── store.py          # 任务状态机与依赖管理
│   ├── skill/                # Skill 模板系统
│   │   ├── loader.py         # Skill 文件发现与解析
│   │   ├── executor.py       # Skill 执行引擎
│   │   └── builtin.py        # 内置 Skill 定义
│   ├── subagent/             # 并发子代理系统
│   │   └── manager.py        # 子代理生命周期管理
│   ├── permission/           # 权限控制
│   │   └── __init__.py       # 权限检查（4 种模式）
│   ├── mcp/                  # MCP 协议集成
│   │   └── client.py         # MCP 客户端（stdio/sse 传输）
│   └── plugin/               # 插件系统
│       └── __init__.py       # 插件加载接口
├── tests/                    # 测试套件
│   ├── test_agent.py         # Agent 循环测试
│   ├── test_compaction.py    # 上下文压缩测试
│   ├── test_config.py        # 配置测试
│   ├── test_core.py          # 核心集成测试
│   ├── test_execution_engine.py  # 执行引擎测试
│   ├── test_memory.py        # 内存系统测试
│   ├── test_providers.py     # Provider 适配器测试
│   ├── test_skill.py         # Skill 系统测试
│   └── test_tools.py         # 工具系统测试
├── docs/                     # 文档
│   ├── requirements.md       # 需求设计文档
│   ├── architecture.md       # 架构设计文档
│   ├── technical.md          # 技术设计文档
│   ├── roadmap.md            # 开发路线图
│   └── execution-engine-*.md # 执行引擎升级文档
├── .feinn/skills/            # 项目级自定义 Skill
├── pyproject.toml            # 项目元数据与依赖
├── DEVELOPMENT_WORKFLOW.md   # 开发流程与规范
├── wiki.md / wiki.zh.md      # Wiki 文档（英文/中文）
└── README.md / README.zh.md  # README（英文/中文）
```

---

## Skill 系统

Skill 是 FeinnAgent 的可复用提示模板系统，用于封装常见的工作流程。通过触发词（activator）快速调用预定义的提示模板。

### 内置 Skill

| Skill | 触发词 | 说明 |
|-------|--------|------|
| `commit` | `/commit` | 审查暂存更改并创建规范的 git 提交 |
| `review` | `/review`, `/review-pr` | 审查代码或 PR 并提供结构化反馈 |
| `explain` | `/explain` | 详细解释代码，适合学习理解 |
| `test` | `/test` | 为指定代码生成全面的测试用例 |
| `doc` | `/doc` | 为代码生成或更新文档 |

### 使用 Skill

在交互模式下，直接输入触发词：

```
feinn> /commit
[Agent 会审查 git 状态并创建提交]

feinn> /explain src/feinn_agent/agent.py
[Agent 会详细解释该文件的代码]

feinn> /test src/feinn_agent/tools.py
[Agent 会为该模块生成测试]

feinn> /review
[Agent 会审查当前分支的更改]
```

### 自定义 Skill

在 `~/.feinn/skills/` 或项目 `.feinn/skills/` 目录下创建 `.md` 文件：

```markdown
---
id: my-skill
summary: 我的自定义 Skill
activators: ["/my", "do my thing"]
tools: ["Read", "Write"]
param-guide: "[文件名]"
param-names: ["filename"]
---

请处理文件: $FILENAME

上下文: $PARAMS
```

**Frontmatter 字段说明：**

| 字段 | 说明 | 必需 |
|------|------|------|
| `id` | Skill 唯一标识 | 是 |
| `summary` | 简短描述 | 是 |
| `activators` | 触发词列表 | 否（默认使用 `/id`） |
| `tools` | 允许使用的工具 | 否 |
| `param-guide` | 参数提示 | 否 |
| `param-names` | 参数名列表（用于 `$NAME` 替换） | 否 |
| `exec-mode` | 执行模式：`direct` 或 `isolated` | 否 |
| `visible` | 是否在列表中显示 | 否 |

**模板占位符：**

- `$PARAMS` 或 `$ARGUMENTS` - 用户输入的完整参数字符串
- `$NAME` - 对应 `param-names` 中的命名参数（大写）

---

## 开发指南

### 运行测试

```bash
# 运行所有测试
python3.11 -m pytest tests/ -v

# 运行特定测试
python3.11 -m pytest tests/test_core.py -v
```

### 代码检查

```bash
# 格式化代码
python3.11 -m ruff format src/

# 检查代码
python3.11 -m ruff check src/
```

### 添加新工具

```python
from feinn_agent.tools.registry import register

@register(
    name="my_tool",
    description="工具描述",
    input_schema={
        "type": "object",
        "properties": {
            "param": {"type": "string"}
        }
    }
)
async def my_tool(param: str) -> str:
    """工具实现"""
    return f"结果: {param}"
```

---

## 文档

### 设计文档

- [需求设计](docs/requirements.md) - 功能与非功能需求
- [架构设计](docs/architecture.md) - 系统架构、分层设计、数据流
- [技术设计](docs/technical.md) - 模块实现细节与 API 设计
- [开发路线图](docs/roadmap.md) - 版本规划与里程碑

### 执行引擎升级

- [执行引擎需求](docs/execution-engine-requirements.md) - 基于 Harness Engineering 的升级需求
- [执行引擎技术设计](docs/execution-engine-technical.md) - 详细实现设计

### 部署指南

- [vLLM 部署指南](docs/vllm-deployment.md) - 自托管模型部署
- [vLLM + Qwen3.5 示例](docs/vllm-qwen35-demo.md) - Qwen3.5 部署示例
- [SiliconFlow 配置](docs/siliconflow-setup.md) - 国内 API 平台使用
- [Azure OpenAI 配置](docs/azure-openai-setup.md) - 企业 Azure 部署

### 开发

- [开发流程与规范](DEVELOPMENT_WORKFLOW.md) - Git 工作流、编码规范、发布流程
- [Wiki](wiki.md) / [Wiki（中文）](wiki.zh.md) - 通用参考文档

---

## 许可证

Apache License 2.0 - 详见 [LICENSE](LICENSE) 文件

---

## 联系方式与支持

- **邮箱**: hanfazy@126.com
- **问题反馈**: [GitHub Issues](https://github.com/PeiziLiu/FeinnAgent/issues)

### 捐赠支持

如果这个项目对您有帮助，欢迎支持开发：

<p align="center">
  <img src="docs/images/wechat-donate.png" width="200" alt="微信捐赠">
  <br>
  <sub>微信扫码捐赠</sub>
</p>

---

<p align="center">
  Built with ❤️ by Feinn Team
</p>
