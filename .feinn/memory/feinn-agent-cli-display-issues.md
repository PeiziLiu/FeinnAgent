---
name: feinn-agent-cli-display-issues
description: feinn-agent CLI/TUI 显示层 7 类关键问题代码审查结果
type: reference
confidence: 0.95
source: user
last_used_at: 2026-06-04
conflict_group: feinn-agent-cli-display-issues
---
对 feinn-agent 项目 CLI/TUI 显示层进行系统性代码审查后发现的 7 类关键问题：

1. **TUI 输出缓冲延迟** (`cli_tui.py`): TextChunk 流式内容被累积在 `_output_accumulator` 中，直到 `TurnDone`/`AgentDone` 才通过 `run_in_terminal` 批量刷新，用户会在整个 turn 期间看不到任何输出，产生“假死”感。

2. **Spinner 与输出竞争** (`cli_tui.py`): 背景线程的 `_spinner_loop` 每 100ms 调用 `_invalidate()`，而 `_safe_output` 也触发 `run_in_terminal`。两者都操作 prompt_toolkit 的 screen state，在快速事件流中可能导致 spinner 残影或光标位置错乱。

3. **固定宽度布局脆弱性** (`display/__init__.py`): `show_welcome()` 使用 `" " * (38 - len(model))` 做 ASCII 框线对齐。若 model 名含 ANSI 转义序列或宽字符（CJK），长度计算错误会导致框线错位甚至 `ValueError`（负数乘法）。多处硬编码 `"─" * 40` 同样存在此风险。

4. **终端宽度适配缺失**: `render_tool_card`、diff preview、permission callback 中的长文本均未查询 `os.get_terminal_size()` 做截断或换行，超出终端宽度后破坏视觉布局。

5. **ANSI 与 PTStyle 混用** (`cli_tui.py`): `_safe_output` 传入的字符串含裸 ANSI 代码（如 `Colors.GREEN`），通过 `ANSI()` 交由 prompt_toolkit 解析；而 TUI layout（spinner、status bar、approval panel）使用 `PTStyle` 的 class 机制。两套颜色体系并存，在某些终端（如 Windows CMD、部分 Web Terminal）下表现不一致。

6. **Legacy spinner 清除不完整** (`cli.py`): `_CLEAR_LINE = "\r" + " " * 100 + "\r"` 只覆盖 100 列，超宽终端会留下尾部残字。且 legacy 路径直接使用 `print()` 而非 `_cprint()`，与 prompt_toolkit 的 alt screen 可能冲突。

7. **权限面板高度固定** (`cli_tui.py`): `approval_panel` 高度 hard-code 为 6，若工具参数多或 diff preview 行数多，内容会被截断无滚动条。

相关文件：
- `src/feinn_agent/cli.py` — 主入口、legacy fallback、one-shot 模式
- `src/feinn_agent/cli_tui.py` — prompt_toolkit Application、多线程 agent/spinner
- `src/feinn_agent/display/__init__.py` — Colors、KawaiiDisplay、SpinnerEngine、render_tool_card