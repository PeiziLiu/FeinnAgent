# FeinnAgent 闭环学习系统 — 开发需求文档

> 参考实现: Hermes Agent  
> 工程方法论: Harness Engineering  
> 版本: v1.0.0  
> 状态: **已实现** (src/feinn_agent/learning/)

---

## 1. 背景与动机

### 1.1 现状分析

FeinnAgent 当前具备 Skill 模板系统、双作用域内存系统和轨迹记录基础设施，但**缺乏从交互经验中持续学习的能力**。在与 Hermes Agent 的对比中，存在以下差距：

| 能力 | FeinnAgent 现状 | Hermes Agent 参考 | 差距 |
|------|----------------|-------------------|------|
| Skill 自动创建 | 无（仅手动编写 .md） | 后台 review 线程自动从交互中创建 Skill | Agent 无法自主积累经验 |
| Skill 自我改进 | 无（创建后不更新） | 使用中发现过时时自动 `skill_manage(patch)` | Skill 无法进化 |
| 知识自动持久化 | 无（仅手动 MemorySave） | 每 N 轮触发 memory nudge，自动提取用户画像/偏好 | 知识会丢失 |
| 跨会话检索 | 无 SQLite FTS | FTS5 全文搜索 + DISCOVER/SCROLL/BROWSE 三种检索模式 | 代理无法回忆先前会话 |
| 背景 review 机制 | 无 | daemon 线程 fork 子 Agent 审查每轮对话 | 无触发式学习 |
| 使用 Telemetry | 无 | 追踪 use_count/patch_count/last_used_at | 无法判断 Skill 生命周期 |
| Skill 生命期管理 | 无 | Curator 自动归档 stale skill | Skill 会堆积 |

### 1.2 目标

参考 Hermes Agent 的实现，在保持 FeinnAgent 现有架构的前提下，系统性引入**闭环学习能力**，应用 Harness Engineering 方法论，构建对 AI Agent 行为的**引导、检测、反馈**学习闭环。

---

## 2. Harness Engineering 应用框架

### 2.1 Guides（前置引导）

| 引导机制 | 对应功能 |
|----------|----------|
| System Prompt 学习引导 | 在 system prompt 中加入 Skill 使用/创建/改进指导 |
| Nudge 间隔配置 | 可配置的 memory nudge / skill nudge 间隔 |
| Skill 使用指南 | Agent 被告知何时创建/更新 Skill |

### 2.2 Sensors（后置检测）

| 检测机制 | 对应功能 |
|----------|----------|
| Turn Counter | 追踪 user 消息轮次和 tool 调用次数 |
| Skill 使用追踪 | 记录每次 Skill 的 use/view/patch 操作 |
| Memory 提取检测 | 在 context 压缩前触发的记忆提取钩子 |

### 2.3 Feedback Loops（反馈循环）

| 反馈回路 | 对应功能 |
|----------|----------|
| Background Review | daemon 线程 fork 子 Agent，审查对话并持久化知识 |
| Context Compression Hook | 压缩前触发 memory provider 提取 |
| Session Continuation | 压缩后创建父子 session 链 |

---

## 3. 功能需求

### 3.1 Nudge 系统

| ID | 需求 | 描述 | 验收标准 | 实现 |
|----|------|------|----------|------|
| CL-001 | Memory Nudge | 每 N 轮用户消息后触发记忆审查 | 可配置间隔（默认 10），触发生成 USER.md/MEMORY.md | `learning/nudge.py` |
| CL-002 | Skill Nudge | 每 N 次工具调用后触发 Skill 审查 | 可配置间隔（默认 10），tool iteration 计数 | `learning/nudge.py` |
| CL-003 | Nudge 合并 | memory 和 skill nudge 同时触发时合并为一次 review | 单次 review 处理两种需求 | `learning/review.py` |
| CL-004 | Nudge 恢复 | 恢复会话时重建计数器 | 计数器 = 已有轮次 % 间隔，避免立即触发 | `learning/nudge.py` |
| CL-005 | Suppression | Agent 主动使用 `skill_manage` 时重置 skill nudge 计数器 | 防止不必要的重复审查 | `learning/nudge.py` |

### 3.2 Background Review 系统

| ID | 需求 | 描述 | 验收标准 | 实现 |
|----|------|------|----------|------|
| CL-011 | Review Agent | fork 子 Agent 进行背景审查 | 继承父 Agent 的 runtime（provider、model）、tool whitelist | `learning/review.py` |
| CL-012 | Tool Whitelist | review agent 仅允许 memory 和 skill_manage 工具 | 不允许执行任意工具 | `learning/review.py` |
| CL-013 | Memory Review Prompt | 提取用户画像、偏好、需求 | 保存到 USER.md/MEMORY.md | `learning/review.py` |
| CL-014 | Skill Review Prompt | 自动创建/更新 Skill | 优先级：(1) 更新已加载 Skill (2) 更新现有 (3) 创建新 Skill | `learning/review.py` |
| CL-015 | Non-blocking 执行 | review 在 daemon 线程中运行 | 不阻塞主对话流程，失败也不影响主流程 | `learning/review.py` |
| CL-016 | 结果通知 | review 结果展示给用户 | 显示 "Self-improvement: saved memory · created skill X" 摘要 | `learning/review.py` |

### 3.3 Skill 自动创建与自我改进

| ID | 需求 | 描述 | 验收标准 | 实现 |
|----|------|------|----------|------|
| CL-021 | 自动创建 Skill | 从交互中提取通用工作流创建 Skill | YAML frontmatter + 模板内容，写入 `~/.feinn/skills/<id>/SKILL.md` | `skill/auto_create.py` |
| CL-022 | 自动更新 Skill | 使用中发现过时/错误时 patch | 原子写入 + security scan | `skill/auto_create.py` |
| CL-023 | Support Files | Skill 支持文件（references/ templates/ scripts/） | 在 Skill 目录下创建子目录 | `skill/auto_create.py` |
| CL-024 | 安全扫描 | 新创建/更新的 Skill 做安全审查 | 阻塞模式写入回滚 | `skill/auto_create.py` |
| CL-025 | Usage Telemetry | 追踪 use/view/patch 次数和最后使用时间 | 侧边 `.usage.json` 文件 | `skill/usage.py` |
| CL-026 | Skill Curator | 自动归档长期未使用的 Skill | `active` → `stale` → `archived` | `skill/curator.py` |

### 3.4 记忆自动持久化

| ID | 需求 | 描述 | 验收标准 | 实现 |
|----|------|------|----------|------|
| CL-031 | 自动 Memory 写入 | review agent 自动调用 `memory(action="add")` | 写入 USER.md/MEMORY.md | `learning/review.py` |
| CL-032 | 压缩前提取 | context 压缩前触发记忆提取 | `on_pre_compress` 钩子 | `memory/store.py` |
| CL-033 | 会话边界提取 | session 结束时提取知识 | `on_session_end` 钩子 | `memory/store.py` |

### 3.5 跨会话检索

| ID | 需求 | 描述 | 验收标准 | 实现 |
|----|------|------|----------|------|
| CL-041 | SQLite Session 存储 | 每轮对话存入 SQLite | role, content, tool_calls, tokens, model 信息 | `learning/session_store.py` |
| CL-042 | FTS5 全文搜索 | 对历史会话做全文检索 | 支持 DISCOVER / SCROLL / BROWSE 三种模式 | `learning/session_search.py` |
| CL-043 | Session 链 | context 压缩后创建父子 session | `parent_session_id` 链支持溯源 | `learning/session_store.py` |
| CL-044 | Session Search 工具 | 注册为 LLM 可调用工具 | 零 LLM 开销的检索工具 | `learning/session_search.py` |

### 3.6 轨迹集成

| ID | 需求 | 描述 | 验收标准 | 实现 |
|----|------|------|----------|------|
| CL-051 | 轨迹自动记录 | agent loop 自动记录每轮轨迹 | 集成 TrajectoryRecorder 到 agent.py | `agent.py` |
| CL-052 | 轨迹查询 | 查看历史轨迹 | 按时间/会话查询 | `trajectory/__init__.py` |

---

## 4. 非功能需求

| ID | 需求 | 描述 | 目标 |
|----|------|------|------|
| CL-NF01 | Review 延迟 | Background review 不增加主对话延迟 | < 100ms 开销（fork + prompt 构建） |
| CL-NF02 | 失败隔离 | Review 失败不影响主流程 | 异常捕获 + 日志记录 |
| CL-NF03 | 存储容量 | 长期运行不导致磁盘膨胀 | SQLite WAL 模式，Skill 自动归档 |
| CL-NF04 | 可配置性 | 所有 nudge 间隔和 feature toggle 可配置 | config.yaml 暴露所有参数 |

---

## 5. 用户场景

### 5.1 场景 1：自动学习工作流

```
1. 用户在项目中执行复杂的 Git 操作（分支管理、rebase、cherry-pick）
2. FeinnAgent 执行完成后触发 skill nudge
3. Background review agent fork 审查对话
4. 发现这是一个可复现的工作流模式
5. 自动创建 `git-workflow` Skill
6. 下次用户输入 `/git-workflow` 时直接执行
7. 用户修正后，Agent 自动 patch Skill
```

### 5.2 场景 2：跨会话知识累积

```
1. Session A 中用户告知"我偏好使用 poetry 管理依赖"
2. Memory nudge 触发，保存到 USER.md
3. Session B 中用户要求"初始化项目"
4. Agent 从 memory 检索到用户偏好
5. 自动使用 poetry 而不是 pip
```

### 5.3 场景 3：Skill 自我改进

```
1. Agent 创建了 `docker-deploy` Skill
2. 多次使用后，发现某步骤已过时（Docker Compose v3 → v4）
3. Agent 主动调用 skill_manage(patch) 更新模板
4. Usage telemetry 记录更新
```

---

## 6. 约束

### 6.1 技术约束

- **语言**: Python 3.11+
- **异步**: 主流程使用 asyncio；review 线程使用 threading（非阻塞）
- **存储**: SQLite（session 存储）+ 文件系统（Skill 和 Memory）
- **类型**: 完整类型注解
- **集成**: 不得破坏现有 Skill、Memory、Tool 系统的兼容性

### 6.2 架构约束

- **Review Agent**: fork 时不复制父 Agent 的 conversation history（仅传递 conversation snapshot）
- **Tool 隔离**: Review Agent 仅有 memory 和 skill_manage 工具权限
- **Nudge 非精确**: nudge 是尽力而为机制，不保证精确触发

---

## 7. 词汇表

| 术语 | 定义 |
|------|------|
| Nudge | 定时触发机制，在特定间隔后启动背景审查 |
| Background Review | 在后台线程中 fork 子 Agent 审查对话并持久化知识 |
| FTS5 | SQLite 全文搜索扩展 |
| Telemetry | Skill 使用统计追踪 |
| Curator | Skill 生命周期管理模块 |
| Session Chain | 通过 parent_session_id 链接的会话序列 |

---

## 8. 附录

### 8.1 相关文档

- [闭环学习技术设计](closed-loop-learning-technical.md)
- [需求设计文档](requirements.md)
- [架构设计](architecture.md)

### 8.2 参考实现

- [Hermes Agent - nousresearch/hermes-agent](https://github.com/NousResearch/hermes-agent)

### 8.3 修订历史

| 版本 | 日期 | 作者 | 变更 |
|------|------|------|------|
| 0.1.0 | 2026-05-31 | Feinn Team | 初始版本 |
