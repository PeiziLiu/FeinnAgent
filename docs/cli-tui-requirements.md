# CLI TUI Enhancement — Requirements Document

## 1. 背景与动机

当前 FeinnAgent CLI 使用 PromptSession（非 full-screen）进行交互，agent 在 asyncio 主循环中运行，输出直接写 stdout。存在的问题：

- **无动画 spinner**：LLM 思考 / 工具执行期间没有等待动画和耗时显示
- **缺少 kawaii face 轮转**：预期展示 (｡◕‿◕｡) / (◕‿◕✿) 等表情
- **无状态栏**：底部不显示模型名、token 用量、会话时长
- **输出竞争**：`print()` 与 `print_formatted_text()` 混合使用导致终端显示异常

Hermes Agent 的 Python CLI 使用 prompt_toolkit `Application`（full_screen=False）+ 后台线程模型，提供了稳定的动画 spinner、status bar、approval panel。FeinnAgent 应参考该架构进行重构。

## 2. 功能需求

### FR-1: 动画 Spinner
- LLM 思考阶段显示旋转动画 + kawaii face + 已耗时
- 工具执行阶段显示工具名 + elapsed time
- Spinner 必须在后台线程持续更新（约 10fps）
- 必须与输出打印不冲突

### FR-2: 状态栏 (Status Bar)
- 底部固定显示：模型名 / 会话时长 / token 用量
- Agent 运行时持续刷新
- 空闲时保持显示，供用户参考

### FR-3: 线程安全输出
- Agent 在后台线程运行期间，所有输出通过 `run_in_terminal()` 安全打印
- 输出内容和 TUI chrome（spinner、status bar、input）不互相覆盖
- 同 Hermes 的 `cprint()` 实现

### FR-4: 输入
- 使用 prompt_toolkit `TextArea` 替代 `PromptSession`
- 支持 multi-line（Alt+Enter 换行，Enter 提交）
- Tab 补全（commands, skills, @refs, file paths）
- Ctrl+C 清除 / 退出

### FR-5: 权限面板 (Approval Panel)
- 工具执行需要批准时，TUI 顶部弹出面板（Hermes 风格 ConditionalContainer）
- 选项：y / n / A (always) / s (session) / d (deny)
- 带有边框、标题、args 摘要

### FR-6: 错误恢复
- 终端 resize 后 TUI chrome 自动适应
- Ctrl+C 中断 agent 执行后返回输入提示，不崩溃

## 3. 非功能需求

- NFR-1: 兼容 prompt_toolkit >= 3.0
- NFR-2: 最低 Python 3.11
- NFR-3: macOS / Linux 终端兼容
- NFR-4: 保持与当前 `FeinnCompleter`、`SpinnerEngine`、`render_tool_card` 等组件的兼容性
- NFR-5: 代码模块化，核心 TUI 逻辑在 `cli_tui.py` 中，不膨胀 `cli.py`

## 4. 架构约束

1. 必须使用 `Application(full_screen=False)`（Hermes 模式），而非 full-screen 模式
2. Agent 必须在后台线程中运行，主线程运行 prompt_toolkit event loop
3. Spinner 通过 `app.invalidate()` 触发 TUI 重绘，而非 raw `\r` 输出
4. Approval 面板通过 `ConditionalContainer` + `queue.Queue` 实现（同 Hermes `callbacks.py`）
