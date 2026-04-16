# FeinnAgent 开发迭代规范

基于 **Harness Engineering** 和 **hardness** 编程理念的开发流程，通过约束、工具、文档和反馈循环确保代码质量、需求完整性和版本控制规范性。

---

## 核心理念

### Harness Engineering

**Harness 是一组约束、工具、文档和反馈循环，让 Agent 保持高效和正轨。**

| 维度 | 描述 | 在 FeinnAgent 中的应用 |
|------|------|----------------------|
| **Guides (前置引导)** | 执行前主动约束行为空间 | 安全命令白名单、工具描述、超时建议、Plan 模式 |
| **Sensors (后置检测)** | 执行后自动检测输出质量 | 退出码语义、Diff 反馈、GetDiagnostics、输出截断 |
| **Guardrails (安全护栏)** | 全生命周期保持安全边界 | 进程树清理、危险命令检测、Tmux 隔离、权限模式 |

### Hardness Programming

**像硬件开发一样严谨对待软件开发**
- 明确的需求分析
- 严格的版本控制
- 完整的测试验证
- 可追溯的变更历史

---

## 核心理念

**Hardness Programming**: 像硬件开发一样严谨对待软件开发
- 明确的需求分析
- 严格的版本控制
- 完整的测试验证
- 可追溯的变更历史

---

## 开发前准备

### 1. 需求梳理

每次开发前必须明确回答：

```
□ 这是新增需求还是 roadmap 中的既有需求？
□ 需求的影响范围是什么？
□ 是否需要更新架构设计？
□ 测试策略是什么？
```

**如果是新增需求**：
1. 在 `docs/requirements.md` 中补充需求描述
2. 更新 `docs/roadmap.md` 中的优先级和排期
3. 创建需求追踪 Issue

**如果是 roadmap 需求**：
1. 在 roadmap 中标记为 "进行中"
2. 检查相关需求是否有变更
3. 确认依赖项是否已完成

### 2. 版本确认

```bash
# 1. 确保本地 dev 分支是最新的
git checkout dev
git pull origin dev

# 2. 基于最新版本创建 worktree
git worktree add ../feinn-agent-feature-xxx dev

# 3. 进入 worktree 目录
cd ../feinn-agent-feature-xxx
```

---

## Git Worktree 工作流

### 目录结构

```
~/work/
├── feinn-agent/              # 主仓库 (main/dev 分支)
├── feinn-agent-feature-xxx/  # 功能开发 worktree
├── feinn-agent-bugfix-yyy/   # Bug 修复 worktree
└── feinn-agent-hotfix-zzz/   # 热修复 worktree
```

### Worktree 管理命令

```bash
# 创建新的 worktree (基于 dev 分支)
git worktree add ../feinn-agent-feature-<name> dev

# 列出所有 worktree
git worktree list

# 清理已合并的 worktree
git worktree remove ../feinn-agent-feature-<name>

# 强制清理 (未提交更改会被删除)
git worktree remove -f ../feinn-agent-feature-<name>
```

---

## 开发流程

### Phase 1: 需求确认 (Must Have)

```markdown
## 需求检查清单

- [ ] 阅读相关需求文档 (docs/requirements.md)
- [ ] 确认需求类型 (新增 / roadmap / bugfix)
- [ ] 如果是新增需求，已更新 requirements.md 和 roadmap.md
- [ ] 理解需求的技术影响
- [ ] 预估开发工作量
- [ ] 确认测试策略
```

### Phase 2: 技术设计 (Should Have)

```markdown
## 设计检查清单

- [ ] 是否需要更新架构文档？
- [ ] 接口变更是否向后兼容？
- [ ] 数据库/schema 是否需要迁移？
- [ ] 性能影响评估
- [ ] 安全影响评估
```

### Phase 3: 编码实现

```bash
# 1. 创建功能分支
git checkout -b feature/xxx

# 2. 开发过程中保持提交规范
git commit -m "feat: 添加用户认证模块

- 实现 JWT token 生成和验证
- 添加登录/注册接口
- 集成权限检查中间件

Closes #123"
```

**提交规范** (Conventional Commits):
- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具相关

### Phase 4: 测试验证 (Must Have)

```bash
# 1. 本地测试
python3.11 -m pytest tests/ -v --tb=short

# 2. 代码质量检查
python3.11 -m ruff check src/
python3.11 -m ruff format src/ --check

# 3. 类型检查 (如有配置)
# python3.11 -m mypy src/feinn_agent/
```

**测试通过标准**:
- [ ] 核心测试用例 100% 通过
- [ ] 新增功能有对应的测试覆盖
- [ ] 代码覆盖率不降低
- [ ] 无 lint 错误

### Phase 5: 合并前检查

```markdown
## 合并检查清单

- [ ] 代码审查完成 (self-review 或 peer review)
- [ ] 所有测试通过
- [ ] 文档已更新 (README, API docs 等)
- [ ] CHANGELOG 已更新
- [ ] 无冲突可合并到 dev
```

```bash
# 1. 同步 dev 分支最新更改
git checkout dev
git pull origin dev
git checkout feature/xxx
git rebase dev

# 2. 解决冲突后强制推送
git push origin feature/xxx --force-with-lease

# 3. 创建 PR/MR 到 dev 分支
# 或使用命令行合并
git checkout dev
git merge --no-ff feature/xxx -m "Merge feature/xxx: 功能描述"
git push origin dev
```

---

## 分支策略

```
main (生产分支)
  ↑
dev (开发分支) ←── feature/xxx ── feature/yyy
  ↑
hotfix/zzz (紧急修复)
```

### 分支命名规范

- `feature/<描述>` - 新功能
- `bugfix/<描述>` - Bug 修复
- `hotfix/<描述>` - 紧急修复
- `docs/<描述>` - 文档更新
- `refactor/<描述>` - 重构

---

## 发布流程

### 版本号规范 (SemVer)

`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向下兼容的功能添加
- **PATCH**: 向下兼容的问题修复

### 发布检查清单

```markdown
- [ ] dev 分支稳定运行
- [ ] 所有测试通过
- [ ] 版本号已更新 (pyproject.toml)
- [ ] CHANGELOG 已更新
- [ ] 文档已更新
- [ ] 创建 Git tag
- [ ] 合并到 main 分支
```

```bash
# 1. 更新版本号
# 编辑 pyproject.toml

# 2. 创建发布分支
git checkout -b release/v0.2.0 dev

# 3. 版本修复 (如有必要)
# ...

# 4. 合并到 main
git checkout main
git merge --no-ff release/v0.2.0

# 5. 打标签
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin main --tags

# 6. 合并回 dev
git checkout dev
git merge main
```

---

## 快速参考

### 日常开发命令

```bash
# 开始新功能
git worktree add ../feinn-agent-feature-xxx dev
cd ../feinn-agent-feature-xxx
git checkout -b feature/xxx

# 开发中测试
python3.11 -m pytest tests/test_xxx.py -v

# 提交前检查
python3.11 -m pytest tests/ -v
python3.11 -m ruff check src/

# 合并到 dev
git checkout dev
git pull origin dev
git merge feature/xxx --no-ff
git push origin dev

# 清理 worktree
git worktree remove ../feinn-agent-feature-xxx
git branch -d feature/xxx
```

### 紧急修复流程

```bash
# 从 main 创建 hotfix
git worktree add ../feinn-agent-hotfix-xxx main
cd ../feinn-agent-hotfix-xxx
git checkout -b hotfix/xxx

# 修复 → 测试 → 提交

# 合并到 main 和 dev
git checkout main
git merge hotfix/xxx --no-ff
git tag -a v0.1.1 -m "Hotfix v0.1.1"

git checkout dev
git merge hotfix/xxx --no-ff
```

---

## 编码规范

### Harness Engineering 检查表

在编写代码时，始终考虑 Harness 的三个维度：

#### Guides（前置引导）检查
- [ ] 新工具的 description 是否清晰描述使用场景和限制？
- [ ] 是否包含超时建议和参数说明？
- [ ] 相关的安全命令是否添加到白名单？
- [ ] 工具是否有使用示例？

#### Sensors（后置检测）检查
- [ ] 文件变更是否返回 unified diff？
- [ ] 常见退出码是否有语义解释？
- [ ] 输出截断是否保留尾部信息（首 50% + 尾 25%）？
- [ ] ANSI 转义码是否在返回 LLM 前清理？

#### Guardrails（安全护栏）检查
- [ ] 进程/子进程是否在超时/异常时正确清理？
- [ ] 用户输入是否验证防止注入攻击？
- [ ] 危险命令是否有检测和拦截？
- [ ] 工具是否设置了正确的安全标志（read_only/destructive）？

### Python 版本与类型注解

- 最低 Python 版本: **3.11**
- 所有模块顶部加 `from __future__ import annotations`
- 所有公共函数和方法必须有完整类型注解
- 内部函数建议有类型注解，允许省略局部变量类型

```python
# Good
from __future__ import annotations

async def read_file(path: str, limit: int = 100) -> str:
    ...

# Bad — 缺少返回类型
async def read_file(path, limit=100):
    ...
```

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | snake_case | `context.py`, `tool_registry.py` |
| 类 | PascalCase | `FeinnAgent`, `ToolRegistry`, `ContextManager` |
| 函数/方法 | snake_case | `add_message()`, `get_token_count()` |
| 常量 | UPPER_SNAKE_CASE | `_MAX_RETRIES`, `DEFAULT_MODEL` |
| 私有成员 | 前缀 `_` | `_tools`, `_parse_chunk()` |
| 类型别名 | PascalCase | `AgentEvent`, `AgentStream` |
| dataclass 字段 | snake_case | `tool_call_id`, `input_tokens` |

### 异步编程规范

- **异步优先**: 所有 IO 操作（网络、文件、数据库）必须是 `async def`
- **禁止在异步函数中使用阻塞调用**: 如需调用同步阻塞函数，使用 `asyncio.to_thread()` 桥接
- **超时控制**: 所有外部调用必须有超时，使用 `asyncio.wait_for()`
- **并发控制**: 使用 `asyncio.Semaphore` 限制并发数，不要无限制并发

```python
# Good — 异步 IO + 超时
async def fetch_url(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            return await resp.text()

# Good — 同步阻塞通过 to_thread 桥接
async def run_tmux_command(cmd: str) -> str:
    return await asyncio.to_thread(subprocess.run, cmd, capture_output=True)

# Bad — 在异步函数中直接阻塞
async def bad_example():
    result = subprocess.run(cmd)  # 会阻塞整个事件循环!
```

### 数据模型规范

- **核心类型**: 使用 `dataclass`（参见 `types.py`），不使用 Pydantic
- **API 层**: FastAPI 的请求/响应模型可使用 Pydantic
- **不可变优先**: 核心数据结构尽量设计为不可变（`frozen=True`），需要可变状态时明确标注
- **StrEnum**: 枚举类型使用 `StrEnum` 而非 `str + Enum`

```python
# Good — 使用 dataclass
@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]

# Good — 使用 StrEnum
class PermissionMode(StrEnum):
    AUTO = "auto"
    ACCEPT_ALL = "accept-all"
```

### 模块组织

- 单个模块不超过 **500 行**（超过应拆分）
- 导入顺序: stdlib > third-party > local（ruff 的 `I` 规则自动排序）
- 循环导入通过 `TYPE_CHECKING` 保护或调整模块结构解决
- 公共 API 通过 `__init__.py` 的 `__all__` 明确导出

### 代码质量工具

```bash
# 代码检查（必须在提交前通过）
python3.11 -m ruff check src/

# 代码格式化
python3.11 -m ruff format src/

# ruff 配置位于 pyproject.toml:
# target-version = "py311"
# line-length = 120
# select = ["E", "F", "I", "N", "W", "UP"]
```

---

## 架构约束

### 分层依赖规则

```
表现层 (CLI / API Server)
     ↓ 只能调用
核心层 (Agent / Context / Compaction)
     ↓ 只能调用
子系统层 (Tools / Memory / Task / Subagent / Permission / Skill)
     ↓ 只能调用
基础设施层 (Providers / MCP / Storage)
```

- **禁止反向依赖**: 基础设施层不得 import 核心层或表现层
- **禁止跨层跳跃**: 表现层不得直接调用基础设施层（须经核心层中转）
- **子系统间低耦合**: 子系统间通过核心层协调，不直接相互调用

### Harness 架构映射

```
┌─────────────────────────────────────────────────────┐
│                   Harness Layer                      │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐│
│  │   Guides    │  │   Sensors    │  │  Guardrails ││
│  │  (前置引导)  │  │  (后置检测)  │  │  (安全护栏) ││
│  ├─────────────┤  ├──────────────┤  ├─────────────┤│
│  │ 安全白名单   │  │ 退出码解释   │  │ 进程树清理  ││
│  │ Plan 模式   │  │ Diff 反馈    │  │ 危险命令拦截││
│  │ 超时分级    │  │ GetDiagnostics│  │ Tmux 隔离  ││
│  │ 工具描述    │  │ ANSI 清理    │  │ 输出截断   ││
│  └─────────────┘  └──────────────┘  └─────────────┘│
└─────────────────────────────────────────────────────┘
```

### 工具系统约束 (Harness 集成)

- 所有工具必须通过 `registry.py` 注册，不允许硬编码调用
- 工具 handler 签名统一为 `async def handler(params: dict, config: dict) -> str`
- 工具的 `input_schema` 必须是有效的 JSON Schema
- **Guides**: 工具必须标注安全级别: `read_only`, `concurrent_safe`, 或 `destructive`
- **Sensors**: 工具输出通过 `max_result_chars` 限制最大返回长度
- **Guardrails**: 文件操作（Write/Edit）必须返回 unified diff 反馈

### 错误处理

- 工具执行错误应返回字符串（`"Error: ..."` 前缀），不抛异常到 Agent 循环
- Provider 层的网络错误使用重试机制（参见 `_MAX_RETRIES`）
- 仅对可重试错误自动重试: overloaded, rate_limit, timeout, context_length
- 不可恢复错误（如认证失败）直接报告给用户

### 新增依赖规则

- 核心功能**零新增 pip 依赖**（如 Tmux、诊断工具等使用系统级可选依赖）
- 必须添加的依赖需在 PR 中说明理由
- 开发依赖放在 `[project.optional-dependencies] dev` 中

---

## 测试规范

### Harness 回归测试

每个 PR 必须通过以下 Harness 维度的测试：

| 维度 | 测试场景 | 验证点 |
|------|----------|--------|
| **Guides** | `python --version` | 是否自动放行（无需确认）|
| **Guides** | `pip list` | 是否自动放行 |
| **Sensors** | `grep` 退出码 1 | 是否附加 "No matches found" 说明 |
| **Sensors** | Write 文件 | 是否返回 unified diff |
| **Guardrails** | `rm -rf /` | 是否被危险命令模式拦截 |
| **Guardrails** | `sleep 999` 超时 | 进程树是否完全清理 |

### 测试框架

- 框架: `pytest` + `pytest-asyncio`
- 异步模式: `asyncio_mode = "auto"` (在 pyproject.toml 中配置)
- 覆盖率: `pytest-cov`，目标 > 80%

### 测试文件命名

| 被测模块 | 测试文件 |
|----------|----------|
| `agent.py` | `tests/test_agent.py` |
| `tools/builtins.py` | `tests/test_tools.py` |
| `compaction.py` | `tests/test_compaction.py` |
| `memory/store.py` | `tests/test_memory.py` |
| `skill/` | `tests/test_skill.py` |

### 测试编写规范

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_agent_handles_tool_call():
    """测试 Agent 正确处理工具调用"""
    # Arrange - 准备测试数据和 mock
    mock_provider = AsyncMock()
    ...

    # Act - 执行被测操作
    result = await agent.run("test input")

    # Assert - 验证结果
    assert result is not None
```

- 测试函数命名: `test_<被测功能>_<场景>` (例: `test_bash_timeout_kills_process`)
- 每个测试只验证一个行为
- 使用 `AsyncMock` mock 异步依赖
- 不依赖外部 API（LLM 调用必须 mock）
- 集成测试用 `@pytest.mark.integration` 标记，不在 CI 默认运行

### 运行测试

```bash
# 运行所有测试
python3.11 -m pytest tests/ -v --tb=short

# 运行特定模块测试
python3.11 -m pytest tests/test_tools.py -v

# 带覆盖率报告
python3.11 -m pytest tests/ --cov=src/feinn_agent --cov-report=term-missing

# 只运行快速单元测试（排除集成测试）
python3.11 -m pytest tests/ -v -m "not integration"
```

---

## 相关文档

- [README](README.md) - 项目概述和快速开始
- [贡献指南](CONTRIBUTING.md) - 贡献流程、代码规范和 PR 指南
- [需求文档](docs/requirements.md) - 功能需求和非功能需求
- [架构设计](docs/architecture.md) - 系统架构、分层设计和数据流
- [技术设计](docs/technical.md) - 模块实现和 API 设计
- [开发路线图](docs/roadmap.md) - 版本规划和里程碑

---

## 工具推荐

- **Git**: worktree, rebase, cherry-pick
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Linting**: ruff, mypy
- **CI/CD**: GitHub Actions / GitLab CI
