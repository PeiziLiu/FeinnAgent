# FeinnAgent 代码执行引擎升级 — 开发需求文档

> 参考实现: CheetahClaws  
> 工程方法论: Harness Engineering  
> 版本: v1.1.0  
> 状态: 草案

---

## 1. 背景与动机

### 1.1 现状分析

FeinnAgent 当前的代码执行引擎（`tools/builtins.py` 中 `_bash` 函数）仅 ~40 行，提供基础的 asyncio subprocess 执行能力。在与同类框架的对比中，存在以下短板:

| 能力 | FeinnAgent 现状 | CheetahClaws 参考 | 差距 |
|------|----------------|-------------------|------|
| 进程树管理 | 无（仅 `proc.kill()`） | `_kill_proc_tree` 跨平台进程组清理 | 僵尸进程风险 |
| 后台/长进程 | 不支持 | Tmux 11 个工具 + 子代理后台线程 | 无法运行服务器/watch 类任务 |
| 安全命令白名单 | 正则匹配 | 前缀白名单（更多类别，含 python/node/pip/npm） | 覆盖范围不足 |
| 代码诊断 | 无 | GetDiagnostics（pyright/mypy/eslint/shellcheck） | 缺失 |
| Plan 模式 | 仅权限层支持 | 完整 Plan 模式工作流 | 未集成到执行层 |
| 输出截断策略 | 首尾各 50% | 首 50% + 尾 25%（更合理的分布） | 尾部信息不足 |
| Diff 反馈 | 无 | Write/Edit 返回 unified diff | 用户无法直观看到变更 |
| 跨平台进程管理 | 仅 Unix | Unix（killpg）+ Windows（taskkill） | Windows 支持不完整 |

### 1.2 目标

参考 CheetahClaws 的实现，在保持 FeinnAgent 轻量级架构优势的前提下，系统性升级代码执行引擎，应用 Harness Engineering 方法论，构建对 AI Agent 行为的**约束、引导、反馈**闭环。

---

## 2. Harness Engineering 应用框架

Harness Engineering 的核心思想: **harness 是一组约束、工具、文档和反馈循环，让 agent 保持高效和正轨。**

在本次升级中，将 Harness Engineering 映射为三个维度:

### 2.1 Guides（前置引导）

> 在 agent 执行前主动约束行为空间，提高首次正确率。

| 引导机制 | 对应功能 |
|----------|----------|
| 安全命令白名单增强 | 扩展 `_SAFE_PREFIXES` 覆盖 python/node/pip/npm 等开发工具 |
| Plan 模式集成 | 执行层原生支持 Plan 模式，强制先规划再执行 |
| 进程超时分级 | 不同命令类别使用不同默认超时（读操作 30s / 构建 300s） |
| 工具描述增强 | Bash 工具的 schema description 包含超时建议 |

### 2.2 Sensors（后置检测）

> 在 agent 执行后自动检测输出质量，发现问题。

| 检测机制 | 对应功能 |
|----------|----------|
| 退出码语义解释 | 对 grep/diff/git 等工具的非零退出码附加说明 |
| GetDiagnostics 工具 | 内置代码诊断（pyright/eslint/shellcheck） |
| Diff 反馈 | Write/Edit 操作返回 unified diff，让 agent 确认变更 |
| 输出截断优化 | 采用首 50% + 尾 25% 策略，保留更多尾部错误信息 |

### 2.3 Guardrails（安全护栏）

> 在执行全生命周期保持安全边界。

| 护栏机制 | 对应功能 |
|----------|----------|
| 进程树清理 | 跨平台进程组管理，避免僵尸进程 |
| 危险命令增强 | 扩展 `_UNSAFE_PATTERNS` 覆盖更多危险场景 |
| Tmux 持久会话 | 长进程通过 Tmux 隔离，避免阻塞主循环 |
| 输出安全 | ANSI 转义码清理 + 参数注入防护 |

---

## 3. 功能需求

### FR-1: 进程树管理

**优先级**: P0（必须）

**描述**: 实现跨平台的进程树清理能力，确保超时或异常退出时子进程不会泄漏。

**参考**: CheetahClaws `_kill_proc_tree()` (tools.py:453-468)

**验收标准**:
- Unix 上使用 `start_new_session=True` + `os.killpg()` 清理进程组
- Windows 上使用 `taskkill /F /T /PID` 清理进程树
- 超时时先 SIGTERM，3 秒后 SIGKILL
- 异常退出时自动清理所有子进程

### FR-2: 安全命令白名单增强

**优先级**: P0（必须）

**描述**: 扩展安全命令白名单，覆盖常用开发工具链。

**参考**: CheetahClaws `_SAFE_PREFIXES` (tools.py:329-338)

**新增白名单**:
```
python, python3, node, ruby, perl          # 脚本解释器（直接执行）
pip show, pip list, npm list, cargo metadata  # 包管理器查询
df, du, free, top -bn, ps                    # 系统信息
curl -I, curl --head                         # HTTP 头请求
printf, date, uname, id, printenv            # 系统工具
ag, fd                                       # 搜索工具
git remote, git stash list, git tag          # 额外 git 只读命令
```

### FR-3: 退出码语义解释

**优先级**: P1（重要）

**描述**: 对常见命令的非零退出码附加语义说明，避免 agent 误判为错误并浪费 token 排查。

**参考**: Hermes `exit_code_meaning` 机制

**覆盖命令**:
| 命令 | 退出码 | 含义 |
|------|--------|------|
| grep | 1 | 无匹配（非错误） |
| diff | 1 | 文件存在差异（非错误） |
| git diff | 1 | 存在差异（非错误） |
| test/[ | 1 | 条件为假（非错误） |

### FR-4: Write/Edit 操作返回 Diff

**优先级**: P1（重要）

**描述**: 文件写入和编辑操作返回 unified diff 格式的变更摘要，让 agent 和用户直观确认修改内容。

**参考**: CheetahClaws `generate_unified_diff()` + `maybe_truncate_diff()` (tools.py:348-361)

**验收标准**:
- Write: 新建文件返回行数统计，更新文件返回 unified diff
- Edit: 返回替换处的 unified diff
- Diff 超过 80 行时截断并提示剩余行数
- 保持异步执行，不引入阻塞操作

### FR-5: Tmux 持久会话集成

**优先级**: P1（重要）

**描述**: 集成 Tmux 工具，支持长进程管理、服务器启动、watch 类任务等场景。

**参考**: CheetahClaws `tmux_tools.py` (完整 322 行实现)

**工具清单**:
| 工具 | 类型 | 说明 |
|------|------|------|
| TmuxListSessions | 只读 | 列出所有活跃会话 |
| TmuxNewSession | 写入 | 创建新会话 |
| TmuxSendKeys | 写入 | 向 pane 发送命令/按键 |
| TmuxCapture | 只读 | 捕获 pane 输出 |
| TmuxListPanes | 只读 | 列出窗格信息 |
| TmuxKillPane | 写入 | 关闭窗格 |
| TmuxNewWindow | 写入 | 创建新窗口 |
| TmuxListWindows | 只读 | 列出窗口信息 |
| TmuxSplitWindow | 写入 | 分割窗格 |
| TmuxSelectPane | 写入 | 切换焦点窗格 |
| TmuxResizePane | 写入 | 调整窗格大小 |

**验收标准**:
- 自动检测 tmux 可用性，不可用时不注册工具
- 会话/窗格名称输入做正则校验，防止注入
- 所有命令参数使用 `shlex.quote()` 转义
- Tmux 命令超时 10 秒
- 兼容 asyncio 事件循环（通过 `asyncio.to_thread` 桥接）

### FR-6: GetDiagnostics 工具

**优先级**: P2（一般）

**描述**: 内置代码诊断工具，自动检测已安装的 linter/checker 并运行。

**参考**: CheetahClaws GetDiagnostics 实现

**支持的诊断器**:
| 语言 | 诊断器 | 检测方式 |
|------|--------|----------|
| Python | pyright, mypy, py_compile | `which` 检测 |
| JavaScript/TypeScript | tsc, eslint | `which` 检测 |
| Shell | shellcheck, `bash -n` | `which` 检测 |
| Go | `go vet` | `which` 检测 |
| Rust | `cargo check` | `which` 检测 |

**验收标准**:
- 自动检测可用的诊断器，优先使用更精确的工具
- 仅返回错误和警告，过滤掉提示信息
- 输出格式统一为 `file:line:col: level: message`
- 超时 60 秒

### FR-7: 输出截断策略优化

**优先级**: P2（一般）

**描述**: 调整输出截断策略，保留更多尾部信息（错误信息通常在末尾）。

**当前策略**: 首尾各 50%  
**目标策略**: 首 50% + 尾 25%（与 CheetahClaws 一致）

### FR-8: ANSI 转义码清理

**优先级**: P2（一般）

**描述**: 清理命令输出中的 ANSI 转义序列，避免干扰 LLM 理解。

**验收标准**:
- 使用正则剥离所有 ANSI 转义序列
- 在输出返回给 LLM 前自动处理
- 不影响用户终端的彩色显示

---

## 4. 非功能需求

### NFR-1: 轻量性保持

新增代码总量控制在 **800 行以内**（不含测试），保持 FeinnAgent 轻量优势。

**预估**:
| 模块 | 预估行数 |
|------|----------|
| 进程树管理 + Bash 增强 | ~80 行 |
| 安全命令/退出码 | ~60 行 |
| Diff 反馈 | ~50 行 |
| Tmux 工具 | ~350 行 |
| GetDiagnostics | ~150 行 |
| ANSI 清理 + 截断优化 | ~30 行 |
| **总计** | **~720 行** |

### NFR-2: 异步一致性

所有新增工具必须保持 `async def` 接口，与现有 asyncio 架构一致。同步操作（如 Tmux subprocess）通过 `asyncio.to_thread()` 桥接。

### NFR-3: 零新增核心依赖

不引入新的 pip 依赖。Tmux 和诊断工具均为系统级可选依赖，自动检测可用性。

### NFR-4: 向后兼容

现有工具的 API schema 和行为不发生破坏性变更。新功能以增量方式添加。

### NFR-5: Harness 可组合性

所有新增的 Guides/Sensors/Guardrails 机制应可独立启用/禁用，支持渐进式采纳。

---

## 5. 实施优先级

| 阶段 | 功能 | 优先级 |
|------|------|--------|
| Phase 1 | FR-1 进程树管理 + FR-2 安全白名单 + FR-7 截断优化 + FR-8 ANSI 清理 | P0 |
| Phase 2 | FR-3 退出码解释 + FR-4 Diff 反馈 | P1 |
| Phase 3 | FR-5 Tmux 集成 | P1 |
| Phase 4 | FR-6 GetDiagnostics | P2 |

---

## 6. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Tmux 不可用 | 后台进程功能缺失 | 自动检测，不可用时优雅降级 |
| 进程组清理失败 | 僵尸进程 | 多层 fallback（killpg → kill → 忽略） |
| 诊断器输出格式不统一 | 解析失败 | 正则容错 + 原始输出 fallback |
| 安全白名单误判 | 安全风险或过度限制 | 白名单可通过配置扩展 |
