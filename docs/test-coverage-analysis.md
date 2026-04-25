# 测试用例完整性分析报告

> 分析日期：2026-04-25

## 一、总体概况

| 指标 | 值 |
|------|-----|
| 源文件（非 `__init__`） | 28 个 |
| 测试文件 | 20 个 |
| 测试用例总数 | 389 个 |
| 通过 | 364 |
| 失败 | 11 |
| 跳过 | 1 |

## 二、模块级覆盖对照表

| 源文件 | 测试文件 | 状态 |
|--------|---------|------|
| `agent.py` | `test_agent.py` | ⚠️ 部分覆盖，**1个测试失败** |
| `cli.py` | **❌ 无测试** | 完全未覆盖 |
| `compaction.py` | `test_compaction.py` | ⚠️ 部分覆盖，**3个测试失败** |
| `config.py` | `test_config.py` | ⚠️ 部分覆盖，**2个测试失败** |
| `context.py` | `test_context.py` | ✅ 基本覆盖 |
| `types.py` | `test_core.py` | ✅ 覆盖尚可 |
| `providers.py` | `test_providers.py` | ⚠️ 部分覆盖 |
| `server.py` | `test_server.py` | ⚠️ 部分覆盖 |
| `memory/store.py` | `test_memory.py` | ⚠️ **2个测试失败** |
| `mcp/client.py` | `test_mcp.py` | ⚠️ 覆盖很浅 |
| `skill/builtin.py` | `test_skills.py` | ⚠️ 覆盖很浅 |
| `skill/executor.py` | `test_skill.py` | ⚠️ 部分覆盖 |
| `skill/loader.py` | `test_skill.py` | ✅ 覆盖尚可 |
| `subagent/manager.py` | `test_subagent.py` | ⚠️ 覆盖很浅 |
| `task/store.py` | `test_task.py` | ✅ 覆盖尚可 |
| `checkpoint/__init__.py` | `test_checkpoint.py` | ✅ 覆盖较好 |
| `plan/__init__.py` | `test_plan_system.py` | ⚠️ 部分覆盖 |
| `trajectory/__init__.py` | `test_trajectory.py` | ✅ 覆盖较好 |
| `tools/browser.py` | `test_browser.py` | ✅ 覆盖较好 |
| `tools/browser_providers/` | `test_browser_providers.py` | ⚠️ 覆盖很浅（仅实例化测试） |
| `tools/builtins.py` | `test_execution_engine.py` | ⚠️ 间接测试，无直接handler测试 |
| `tools/diagnostics.py` | `test_execution_engine.py` | ✅ 覆盖较好 |
| `tools/output.py` | `test_execution_engine.py` | ✅ 覆盖较好 |
| `tools/process.py` | `test_execution_engine.py` | ✅ 覆盖较好 |
| `tools/registry.py` | `test_tools.py` | ⚠️ 部分覆盖，**1个测试失败** |
| `tools/skills.py` | **❌ 无直接测试** | 仅通过skill集成间接覆盖 |
| `tools/tmux.py` | `test_execution_engine.py` | ⚠️ 仅安全/可用性测试 |
| `display/__init__.py` | `test_plan_system.py` | ⚠️ 基础覆盖（KawaiiDisplay、DiffDisplay、ToolPreview） |
| `interrupt/__init__.py` | `test_plan_system.py` | ✅ 在plan测试中间接覆盖 |
| `permission/__init__.py` | `test_core.py` + `test_execution_engine.py` | ⚠️ 部分覆盖，**1个测试失败** |

## 三、关键问题

### 🔴 破碎的测试（11个失败）

1. **`test_agent.py::test_tool_call_handling`** — mock路径错误，`feinn_agent.agent` 不存在 `dispatch` 属性（应该是 `dispatch_batch`）
2. **`test_compaction.py` 3个** — `maybe_compact` / `AgentState` 接口可能已变更
3. **`test_config.py` 2个** — `test_config_file_override` / `test_invalid_config_file` 断言不匹配
4. **`test_core.py::test_accept_all_mode`** — `asyncio.get_event_loop()` 在 Python 3.11+ 已废弃
5. **`test_memory.py` 2个** — `MemoryEntry.to_markdown/from_markdown` 行为变更
6. **`test_tools.py` 2个** — `register_duplicate_raises` / `dispatch_unknown_tool` 断言与实现不匹配

### 🔴 完全没有测试文件的模块

1. **`cli.py`** — 6个函数/方法，零测试。CLI 是用户体验的核心入口，包含交互循环、命令处理、skill触发等逻辑，完全缺乏测试是非常严重的遗漏。

### 🟡 覆盖非常浅的模块

1. **`tools/browser_providers/`** — 测试仅创建了5个provider实例并验证基本属性，没有测试 `create_session` / `execute_command` / `close_session` / `emergency_cleanup` 等核心方法的实际行为。

2. **`mcp/client.py`** — 测试仅覆盖配置加载和添加服务器，没有测试 `connect` / `list_tools` / `call_tool` / `stop_all` 的实际行为。

3. **`subagent/manager.py`** — 有17个公开函数/类，但只测试了 `spawn`、`check_result`、`list_tasks`、`list_agent_types`，缺少 `_restore_tools`、`_agent_spawn`、`_check_agent_result` 等核心handler的测试。

4. **`skill/builtin.py`** — `register_builtin_skills()` 仅有1个简单验证测试，未验证5个内置skill模板的具体内容是否正确。

5. **`tools/skills.py`** — `_skill_tool` 和 `_skill_list_tool` 完全没有直接测试。

### 🟡 关键逻辑路径缺失

1. **`agent.py`** — `_stream_with_retry` 的 context_length 重试路径未测试；`_execute_tools` 权限被拒绝的路径未测试；`_permission_callback` 交互流程未测试。

2. **`providers.py`** — `stream()` 函数（LLM调用的核心）完全没有测试；`_to_anthropic_messages` / `_to_openai_messages` 消息转换没有测试；`estimate_cost` 没有测试。

3. **`permission/__init__.py`** — `check_permission` 的 `PLAN` 模式和 `AUTO` 模式下的各种分支（read_only检查、destructive检查、callback调用）覆盖不完整。

4. **`tools/builtins.py`** — 所有8个handler（`_read_file`, `_write_file`, `_edit_file`, `_bash`, `_glob`, `_grep`, `_web_fetch`, `_ask_user`）没有独立的单元测试，只通过 `run_command` 等间接覆盖了部分行为。

5. **`context.py`** — `_get_git_info()` 和 `_load_project_context()` 没有测试。

6. **`display/__init__.py`** — `KawaiiDisplay` 有300+行代码（包括各种渲染方法），测试仅覆盖了构造函数。

## 四、测试质量问题

1. **`test_agent.py` 底部定义了一个 `AssistantTurn` 辅助类**（第302行），与 `feinn_agent.types.AssistantTurn` 冲突，造成潜在混淆。
2. **异步测试使用已废弃的 `asyncio.get_event_loop().run_until_complete()`**（test_core.py），应改用 `pytest-asyncio`。
3. **`test_plan_system.py` 是"上帝测试文件"** — 不只测plan，还测了interrupt、display，职责混乱。
4. **`test_execution_engine.py` 也是"上帝测试文件"** — 跨越output、process、tmux、diagnostics、builtins、permission 多个模块。
5. **测试文件与源文件的映射关系不一致** — `test_skills.py` vs `test_skill.py` 对应不同模块，容易混淆。

## 五、优先建议

| 优先级 | 行动 | 影响 |
|--------|------|------|
| P0 | 修复11个失败的测试 | 恢复CI可靠性 |
| P0 | 为 `cli.py` 添加测试 | 核心入口零覆盖 |
| P1 | 为 `providers.py` 的 `stream()` / 消息转换函数添加测试 | LLM交互核心无测试 |
| P1 | 为 `tools/builtins.py` 的8个handler添加独立单元测试 | 核心工具无直接测试 |
| P1 | 为 `permission.check_permission` 补全各模式分支测试 | 安全关键逻辑缺测试 |
| P2 | 为 `browser_providers` 的核心方法添加mock测试 | Provider接口验证不足 |
| P2 | 为 `subagent/manager.py` handler函数添加测试 | Agent协调逻辑缺测试 |
| P2 | 为 `tools/skills.py` 添加测试 | skill工具零测试 |
| P3 | 重构测试文件映射关系，消除"上帝测试文件" | 维护性改进 |

## 六、总结

项目的测试覆盖面中等偏上（389个测试），但存在11个失败测试、1个完全无覆盖的核心模块（`cli.py`），以及多个关键逻辑路径（LLM调用、消息转换、权限分支、工具handler）缺乏测试的问题。当务之急是修复失败测试和补全 `cli.py` 的覆盖。
