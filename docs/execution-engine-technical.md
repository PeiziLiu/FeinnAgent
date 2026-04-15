# FeinnAgent 代码执行引擎升级 — 技术开发文档

> 参考实现: CheetahClaws  
> 工程方法论: Harness Engineering  
> 版本: v1.1.0  
> 状态: 草案

---

## 1. 架构概览

### 1.1 当前架构

```
tools/builtins.py::_bash()
    └── asyncio.create_subprocess_shell()
        ├── asyncio.wait_for(timeout)
        ├── stdout/stderr 捕获
        └── proc.kill()（超时时）

tools/registry.py::dispatch()
    ├── handler 调用
    └── 输出截断（首尾各 50%）

permission/__init__.py::check_permission()
    ├── 安全命令正则匹配
    ├── 危险命令正则匹配
    └── 4 种权限模式
```

### 1.2 目标架构

```
tools/
├── builtins.py         # 现有工具（Read/Write/Edit/Bash/Glob/Grep/WebFetch）
├── registry.py         # 工具注册与调度
├── skills.py           # Skill 系统
├── process.py          # [新增] 进程管理模块
├── tmux.py             # [新增] Tmux 持久会话工具
├── diagnostics.py      # [新增] 代码诊断工具
└── output.py           # [新增] 输出处理（截断/ANSI清理/Diff）

permission/
└── __init__.py         # 权限系统（增强安全白名单）
```

### 1.3 Harness Engineering 架构映射

```
┌─────────────────────────────────────────────────────┐
│                  Harness Layer                        │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │   Guides    │  │   Sensors    │  │  Guardrails  │ │
│  │  (前置引导)  │  │  (后置检测)   │  │  (安全护栏)  │ │
│  ├─────────────┤  ├──────────────┤  ├─────────────┤ │
│  │ 安全白名单   │  │ 退出码解释    │  │ 进程树清理   │ │
│  │ Plan模式     │  │ GetDiagnostics│  │ 危险命令拦截 │ │
│  │ 超时分级     │  │ Diff反馈      │  │ Tmux隔离     │ │
│  │ 工具描述     │  │ ANSI清理      │  │ 输出截断     │ │
│  └─────────────┘  └──────────────┘  └─────────────┘ │
│                         │                             │
│  ┌──────────────────────┴──────────────────────────┐ │
│  │              Execution Engine                     │ │
│  │  Bash工具 │ Tmux工具 │ Diagnostics │ File工具    │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 2. 模块设计

### 2.1 process.py — 进程管理模块

**职责**: 封装跨平台的进程创建、超时控制和进程树清理逻辑。

**参考**: CheetahClaws `_kill_proc_tree()` (tools.py:453-468) 和 `_bash()` (tools.py:471-495)

```python
# src/feinn_agent/tools/process.py

"""进程管理 — 跨平台进程树清理与增强执行。"""

import asyncio
import os
import sys
import signal
import re
from typing import Optional

# ── 退出码语义 ──────────────────────────────────────────────

_EXIT_CODE_MEANINGS: dict[str, dict[int, str]] = {
    "grep":  {1: "No matches found (not an error)"},
    "rg":    {1: "No matches found (not an error)"},
    "diff":  {1: "Files differ (not an error)"},
    "git":   {1: "Non-zero exit (often normal for diff/grep)"},
    "test":  {1: "Condition is false (not an error)"},
    "[":     {1: "Condition is false (not an error)"},
}

# ── ANSI 转义码清理 ─────────────────────────────────────────

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07")


def strip_ansi(text: str) -> str:
    """移除 ANSI 转义序列。"""
    return _ANSI_ESCAPE.sub("", text)


# ── 进程树清理 ──────────────────────────────────────────────

def kill_process_tree(pid: int) -> None:
    """跨平台终止进程及其所有子进程。
    
    Unix: 使用 os.killpg() 清理进程组
    Windows: 使用 taskkill /F /T 清理进程树
    多层 fallback 确保不会泄漏僵尸进程。
    """
    if sys.platform == "win32":
        import subprocess
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
        )
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


# ── 增强 Bash 执行 ──────────────────────────────────────────

async def run_command(
    command: str,
    timeout: int = 120,
    cwd: Optional[str] = None,
) -> tuple[str, int]:
    """执行 shell 命令，返回 (output, exit_code)。
    
    增强点（vs 当前实现）:
    1. 进程组隔离（Unix start_new_session）
    2. 进程树清理（超时/异常时）
    3. ANSI 转义码清理
    4. 退出码语义解释
    """
    working_dir = cwd or os.getcwd()
    
    kwargs: dict = {}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True  # 创建新进程组

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=working_dir,
        **kwargs,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except TimeoutError:
        kill_process_tree(proc.pid)
        try:
            await asyncio.wait_for(proc.wait(), timeout=3)
        except TimeoutError:
            proc.kill()
        return f"Error: command timed out after {timeout}s (process killed)", -1

    # 组装输出
    output_parts: list[str] = []
    if stdout:
        output_parts.append(stdout.decode("utf-8", errors="replace"))
    if stderr:
        output_parts.append(f"[stderr]\n{stderr.decode('utf-8', errors='replace')}")

    result = "\n".join(output_parts) or f"[exit code: {proc.returncode}]"
    result = strip_ansi(result)

    exit_code = proc.returncode or 0

    # 退出码语义解释
    if exit_code != 0:
        result += f"\n[exit code: {exit_code}]"
        cmd_name = command.strip().split()[0] if command.strip() else ""
        meaning = _EXIT_CODE_MEANINGS.get(cmd_name, {}).get(exit_code)
        if meaning:
            result += f"\n[note: {meaning}]"

    return result, exit_code
```

**设计说明**:
- `kill_process_tree()`: 直接参考 CheetahClaws 的 `_kill_proc_tree()`，采用相同的 Unix/Windows 双路径策略
- `run_command()`: 增强版异步命令执行，整合进程组隔离 + ANSI 清理 + 退出码语义
- `strip_ansi()`: 正则清理 ANSI 转义，防止干扰 LLM 上下文

### 2.2 output.py — 输出处理模块

**职责**: 统一管理输出截断、Diff 生成等输出后处理逻辑。

**参考**: CheetahClaws `generate_unified_diff()` (tools.py:348-353) 和 `maybe_truncate_diff()` (tools.py:355-361)

```python
# src/feinn_agent/tools/output.py

"""输出处理 — 截断策略、Diff 生成。"""

import difflib


def truncate_output(text: str, max_chars: int = 32_000) -> str:
    """截断过长输出，保留首 50% + 尾 25%。
    
    相比旧策略（首尾各 50%），新策略保留更多尾部信息，
    因为错误信息通常出现在输出末尾。
    """
    if len(text) <= max_chars:
        return text

    first_half = max_chars // 2
    last_quarter = max_chars // 4
    truncated = len(text) - first_half - last_quarter

    return (
        text[:first_half]
        + f"\n[... {truncated} chars truncated ...]\n"
        + text[-last_quarter:]
    )


def generate_unified_diff(
    old: str, new: str, filename: str, context_lines: int = 3
) -> str:
    """生成 unified diff 格式的变更摘要。"""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=context_lines,
    )
    return "".join(diff)


def truncate_diff(diff_text: str, max_lines: int = 80) -> str:
    """截断过长的 diff 输出。"""
    lines = diff_text.splitlines()
    if len(lines) <= max_lines:
        return diff_text
    shown = lines[:max_lines]
    remaining = len(lines) - max_lines
    return "\n".join(shown) + f"\n\n[... {remaining} more lines ...]"
```

**设计说明**:
- `truncate_output()`: 采用 CheetahClaws 的首 50% + 尾 25% 策略，相比现有实现更合理
- `generate_unified_diff()` / `truncate_diff()`: 直接参考 CheetahClaws 实现，用于 Write/Edit 工具的变更反馈

### 2.3 tmux.py — Tmux 持久会话工具

**职责**: 提供 Tmux 会话管理能力，支持长进程和后台服务。

**参考**: CheetahClaws `tmux_tools.py` (完整 322 行)

```python
# src/feinn_agent/tools/tmux.py

"""Tmux 持久会话工具 — 自动检测，按需注册。

参考 CheetahClaws tmux_tools.py 实现。
关键差异: 使用 asyncio.to_thread() 桥接同步 subprocess 调用。
"""

import asyncio
import os
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any

from ..types import ToolDef
from .registry import register

# ── 检测 ────────────────────────────────────────────────────

_TMUX_BIN: str | None = None
_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.:-]+$")
_READ_ONLY_TOOLS = frozenset((
    "TmuxListSessions", "TmuxCapture",
    "TmuxListPanes", "TmuxListWindows",
))


def _find_tmux() -> str | None:
    """检测 tmux 二进制文件。"""
    found = shutil.which("tmux")
    if found:
        return found
    if sys.platform == "win32":
        # Windows: 检测 psmux 替代品
        for name in ("psmux", "tmux.exe"):
            path = shutil.which(name)
            if path:
                return path
    return None


def _safe(value: str) -> str:
    """校验 tmux 标识符，防止注入。"""
    if not value or not _SAFE_NAME.match(value):
        raise ValueError(f"Invalid tmux identifier: {value!r}")
    return value


def _run_sync(cmd: str, timeout: int = 10) -> str:
    """同步执行 tmux 命令（将在 to_thread 中调用）。"""
    global _TMUX_BIN
    try:
        if cmd.startswith("tmux "):
            cmd = f'"{_TMUX_BIN}" {cmd[5:]}'
        env = dict(os.environ)
        env.pop("TMUX", None)
        r = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout, env=env,
        )
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()
        if r.returncode != 0 and stderr:
            return f"FAILED (exit {r.returncode}): {stderr}"
        out = (stdout + ("\n" + stderr if stderr else "")).strip()
        return out if out else "(ok)"
    except subprocess.TimeoutExpired:
        return "Error: tmux command timed out"
    except Exception as e:
        return f"Error: {e}"


async def _run(cmd: str, timeout: int = 10) -> str:
    """异步桥接: 在线程池中运行同步 tmux 命令。"""
    return await asyncio.to_thread(_run_sync, cmd, timeout)


def _t(params: dict, key: str = "target") -> str:
    """构建 -t 参数。"""
    val = params.get(key, "")
    return f" -t {_safe(val)}" if val else ""


# ── 工具实现 ────────────────────────────────────────────────
# 每个工具的 handler 签名: async (params, config) -> str

async def _list_sessions(p: dict, c: dict) -> str:
    return await _run("tmux list-sessions")

async def _new_session(p: dict, c: dict) -> str:
    name = _safe(p.get("session_name", "feinn"))
    detach = "-d" if p.get("detached", True) else ""
    cmd = p.get("command", "")
    shell_part = f" {shlex.quote(cmd)}" if cmd else ""
    return await _run(f"tmux new-session {detach} -s {name}{shell_part}")

async def _send_keys(p: dict, c: dict) -> str:
    keys = p["keys"]
    enter = " Enter" if p.get("press_enter", True) else ""
    safe_keys = keys.replace("'", "'\\''")
    return await _run(f"tmux send-keys{_t(p)} '{safe_keys}'{enter}")

async def _capture_pane(p: dict, c: dict) -> str:
    lines = p.get("lines", 50)
    return await _run(f"tmux capture-pane{_t(p)} -p -S -{int(lines)}")

async def _list_panes(p: dict, c: dict) -> str:
    fmt = "'#{{pane_index}}: #{{pane_current_command}} [#{{pane_width}}x#{{pane_height}}] #{{?pane_active,(active),}}'"
    return await _run(f"tmux list-panes{_t(p)} -F {fmt}")

async def _kill_pane(p: dict, c: dict) -> str:
    return await _run(f"tmux kill-pane{_t(p)}")

async def _new_window(p: dict, c: dict) -> str:
    t_flag = _t(p, "target_session")
    name = p.get("window_name", "")
    n_flag = f" -n {_safe(name)}" if name else ""
    cmd = p.get("command", "")
    shell_part = f" {shlex.quote(cmd)}" if cmd else ""
    return await _run(f"tmux new-window{t_flag}{n_flag}{shell_part}")

async def _list_windows(p: dict, c: dict) -> str:
    fmt = "'#{{window_index}}: #{{window_name}} [#{{window_width}}x#{{window_height}}] #{{?window_active,(active),}}'"
    return await _run(f"tmux list-windows{_t(p, 'target_session')} -F {fmt}")

async def _split_window(p: dict, c: dict) -> str:
    direction = "-v" if p.get("direction", "vertical") == "vertical" else "-h"
    cmd = p.get("command", "")
    shell_part = f" {shlex.quote(cmd)}" if cmd else ""
    return await _run(f"tmux split-window {direction}{_t(p)}{shell_part}")

async def _select_pane(p: dict, c: dict) -> str:
    return await _run(f"tmux select-pane -t {_safe(p['target'])}")

async def _resize_pane(p: dict, c: dict) -> str:
    _RESIZE_FLAGS = {"up": "-U", "down": "-D", "left": "-L", "right": "-R"}
    direction = p.get("direction", "down")
    amount = int(p.get("amount", 10))
    d_flag = _RESIZE_FLAGS.get(direction, "-D")
    return await _run(f"tmux resize-pane{_t(p)} {d_flag} {amount}")


# ── Schema 定义与注册 ───────────────────────────────────────
# （省略完整 schema，结构与 CheetahClaws TMUX_TOOL_SCHEMAS 一致）

# 工具名 → (handler, read_only, schema)
_TOOLS: dict[str, tuple] = {
    "TmuxListSessions": (_list_sessions, True, {...}),
    "TmuxNewSession":   (_new_session, False, {...}),
    "TmuxSendKeys":     (_send_keys, False, {...}),
    "TmuxCapture":      (_capture_pane, True, {...}),
    "TmuxListPanes":    (_list_panes, True, {...}),
    "TmuxKillPane":     (_kill_pane, False, {...}),
    "TmuxNewWindow":    (_new_window, False, {...}),
    "TmuxListWindows":  (_list_windows, True, {...}),
    "TmuxSplitWindow":  (_split_window, False, {...}),
    "TmuxSelectPane":   (_select_pane, False, {...}),
    "TmuxResizePane":   (_resize_pane, False, {...}),
}


def register_tmux_tools() -> int:
    """注册所有 Tmux 工具。返回注册数量。
    
    如果 tmux 不可用，返回 0 且不注册任何工具。
    """
    global _TMUX_BIN
    _TMUX_BIN = _find_tmux()
    if not _TMUX_BIN:
        return 0
    
    count = 0
    for name, (handler, read_only, schema) in _TOOLS.items():
        register(ToolDef(
            name=name,
            description=schema.get("description", ""),
            input_schema=schema.get("input_schema", {}),
            handler=handler,
            read_only=read_only,
            concurrent_safe=True,
        ))
        count += 1
    return count
```

**关键设计决策**:

| 决策 | CheetahClaws 方式 | FeinnAgent 方式 | 原因 |
|------|-------------------|-----------------|------|
| 同步/异步 | `subprocess.run`（同步） | `asyncio.to_thread` 桥接 | 保持异步一致性，不阻塞事件循环 |
| 默认会话名 | `cheetah` | `feinn` | 品牌一致 |
| 注入防护 | `_SAFE_NAME` 正则 | 同样的正则校验 | 直接复用成熟方案 |
| 环境变量 | 移除 `$TMUX` + `$PSMUX_SESSION` | 移除 `$TMUX` | 简化（不支持 psmux 嵌套） |

### 2.4 diagnostics.py — 代码诊断工具

**职责**: 自动检测可用的 linter/checker，运行诊断并返回统一格式的结果。

```python
# src/feinn_agent/tools/diagnostics.py

"""代码诊断工具 — 自动检测并运行代码检查器。"""

import asyncio
import shutil
from pathlib import Path
from typing import Any

from ..types import ToolDef
from .registry import register
from .process import run_command

# ── 诊断器配置 ──────────────────────────────────────────────

_DIAGNOSTICS: dict[str, list[dict]] = {
    ".py": [
        {"name": "pyright",    "cmd": "pyright {file}", "binary": "pyright"},
        {"name": "mypy",       "cmd": "mypy {file}",    "binary": "mypy"},
        {"name": "py_compile", "cmd": "python -m py_compile {file}", "binary": "python"},
    ],
    ".js": [
        {"name": "eslint", "cmd": "eslint {file}", "binary": "eslint"},
    ],
    ".ts": [
        {"name": "tsc", "cmd": "tsc --noEmit {file}", "binary": "tsc"},
        {"name": "eslint", "cmd": "eslint {file}", "binary": "eslint"},
    ],
    ".sh": [
        {"name": "shellcheck", "cmd": "shellcheck {file}", "binary": "shellcheck"},
        {"name": "bash_syntax", "cmd": "bash -n {file}", "binary": "bash"},
    ],
    ".go": [
        {"name": "go_vet", "cmd": "go vet {file}", "binary": "go"},
    ],
    ".rs": [
        {"name": "cargo_check", "cmd": "cargo check", "binary": "cargo"},
    ],
}


async def _get_diagnostics(params: dict[str, Any], config: dict[str, Any]) -> str:
    """对指定文件运行代码诊断。
    
    自动检测文件类型，选择可用的诊断器运行。
    """
    file_path = params.get("file_path", "")
    if not file_path:
        return "Error: file_path is required"

    path = Path(file_path)
    if not path.exists():
        return f"Error: file not found: {file_path}"

    suffix = path.suffix.lower()
    checkers = _DIAGNOSTICS.get(suffix)
    if not checkers:
        return f"No diagnostics available for {suffix} files"

    # 找到第一个可用的诊断器
    for checker in checkers:
        if shutil.which(checker["binary"]):
            cmd = checker["cmd"].format(file=file_path)
            output, exit_code = await run_command(cmd, timeout=60)
            return f"[{checker['name']}] {output}"

    return f"No diagnostic tools found for {suffix} files. Checked: {', '.join(c['name'] for c in checkers)}"


register(ToolDef(
    name="GetDiagnostics",
    description="Run code diagnostics (linting, type checking) on a file. Auto-detects available checkers.",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Absolute path to the file to diagnose"},
        },
        "required": ["file_path"],
    },
    handler=_get_diagnostics,
    read_only=True,
    concurrent_safe=True,
))
```

### 2.5 builtins.py 改造 — Bash/Write/Edit 增强

#### 2.5.1 Bash 工具改造

**变更点**: 使用 `process.run_command()` 替换当前的内联 subprocess 逻辑。

```python
# 改造前（当前实现）
async def _bash(params, config):
    command = params.get("command", "")
    timeout = params.get("timeout", 120)
    cwd = params.get("cwd", os.getcwd())
    proc = await asyncio.create_subprocess_shell(...)
    # ... 无进程组管理、无 ANSI 清理、无退出码解释

# 改造后
async def _bash(params, config):
    command = params.get("command", "")
    timeout = params.get("timeout", 120)
    cwd = params.get("cwd", os.getcwd())
    if not command:
        return "Error: command is required"
    output, _ = await run_command(command, timeout=timeout, cwd=cwd)
    return output
```

#### 2.5.2 Write 工具增强

**变更点**: 返回 unified diff 而非简单的字符数统计。

```python
# 改造后
async def _write_file(params, config):
    file_path = params.get("file_path", "")
    content = params.get("content", "")
    # ...
    path = Path(file_path).expanduser().resolve()
    is_new = not path.exists()
    old_content = "" if is_new else path.read_text(encoding="utf-8", errors="replace")
    
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    if is_new:
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return f"Created {file_path} ({line_count} lines)"
    
    diff = generate_unified_diff(old_content, content, path.name)
    if not diff:
        return f"No changes in {file_path}"
    return f"File updated — {file_path}:\n\n{truncate_diff(diff)}"
```

#### 2.5.3 Edit 工具增强

**变更点**: 返回替换处的 diff。

```python
# 改造后（关键变更部分）
    # ... 替换逻辑不变 ...
    path.write_text(new_content, encoding="utf-8")
    
    diff = generate_unified_diff(content, new_content, path.name)
    return f"Changes applied to {path.name}:\n\n{truncate_diff(diff)}"
```

### 2.6 permission/__init__.py 增强 — 安全白名单扩展

**变更点**: 扩展 `_SAFE_READ_COMMANDS` 列表。

```python
# 新增安全命令模式
_SAFE_READ_COMMANDS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        # ── 现有 ──
        r"^ls\b", r"^cat\b", r"^head\b", r"^tail\b",
        r"^find\b", r"^grep\b", r"^rg\b", r"^wc\b", r"^file\b",
        r"^git status\b", r"^git log\b", r"^git diff\b",
        r"^git branch\b", r"^git show\b",
        r"^pwd$", r"^whoami$", r"^echo\b", r"^which\b", r"^env\b",
        r"^python --version", r"^node --version",
        r"^npm list\b", r"^pip list\b",
        
        # ── 新增: 搜索工具 ──
        r"^ag\b",           # silver searcher
        r"^fd\b",           # fd-find
        
        # ── 新增: 脚本执行（读操作场景）──
        r"^python\s",       # python 脚本
        r"^python3\s",
        r"^node\s",         # node 脚本
        r"^ruby\s",
        r"^perl\s",
        
        # ── 新增: 包管理器查询 ──
        r"^pip show\b",
        r"^cargo metadata\b",
        
        # ── 新增: 系统信息 ──
        r"^df\b", r"^du\b", r"^free\b",
        r"^top\s+-bn", r"^ps\b",
        r"^printf\b", r"^date\b", r"^uname\b",
        r"^id$", r"^printenv\b",
        
        # ── 新增: HTTP 头请求 ──
        r"^curl\s+-I\b", r"^curl\s+--head\b",
        
        # ── 新增: Git 只读命令 ──
        r"^git remote\b", r"^git stash list\b", r"^git tag\b",
    ]
]
```

### 2.7 registry.py 改造 — 截断策略

**变更点**: 使用 `output.truncate_output()` 替换内联截断逻辑。

```python
# 改造前
if len(result) > limit:
    half = limit // 2
    result = result[:half] + f"\n... [...] ...\n" + result[-half:]

# 改造后
from .output import truncate_output
result = truncate_output(result, max_chars=limit)
```

---

## 3. 文件变更清单

| 文件 | 操作 | 变更说明 |
|------|------|----------|
| `src/feinn_agent/tools/process.py` | **新增** | 进程管理: kill_process_tree + run_command + strip_ansi + 退出码语义 |
| `src/feinn_agent/tools/output.py` | **新增** | 输出处理: truncate_output + generate_unified_diff + truncate_diff |
| `src/feinn_agent/tools/tmux.py` | **新增** | Tmux 持久会话: 11 个工具 + 自动检测 + 异步桥接 |
| `src/feinn_agent/tools/diagnostics.py` | **新增** | 代码诊断: GetDiagnostics 多语言自动检测 |
| `src/feinn_agent/tools/builtins.py` | **修改** | Bash 使用 run_command; Write/Edit 返回 diff |
| `src/feinn_agent/tools/registry.py` | **修改** | 使用 output.truncate_output 替换内联截断 |
| `src/feinn_agent/permission/__init__.py` | **修改** | 扩展安全命令白名单 |
| `src/feinn_agent/tools/__init__.py` | **修改** | 导入 tmux 和 diagnostics 模块触发注册 |

---

## 4. Harness Engineering 检查清单

每个新增/修改的模块都需要通过以下 Harness 维度验证:

### 4.1 Guides（前置引导）验证

- [ ] Bash 工具 schema description 是否包含超时建议
- [ ] 安全白名单是否覆盖常用开发工具
- [ ] 新工具的 description 是否清晰描述使用场景和限制

### 4.2 Sensors（后置检测）验证

- [ ] 退出码语义是否覆盖 grep/diff/git/test
- [ ] Write/Edit 是否返回 diff 格式的变更摘要
- [ ] GetDiagnostics 输出是否包含 file:line 定位信息
- [ ] ANSI 清理是否在返回 LLM 前完成

### 4.3 Guardrails（安全护栏）验证

- [ ] 进程树清理是否覆盖超时和异常两种场景
- [ ] Tmux 标识符是否做正则校验
- [ ] Tmux 命令参数是否使用 shlex.quote 转义
- [ ] 危险命令模式是否覆盖新增场景

### 4.4 持续改进循环

每次 agent 执行失败时，检查是否需要:
1. 在安全白名单中添加新的安全命令
2. 在退出码语义表中添加新的解释
3. 在危险命令模式中添加新的拦截规则
4. 在工具 description 中补充引导信息

---

## 5. 测试策略

### 5.1 单元测试

| 模块 | 测试重点 |
|------|----------|
| `process.py` | kill_process_tree 多平台 mock; strip_ansi 转义清理; 退出码语义映射 |
| `output.py` | truncate_output 边界条件; diff 生成正确性; diff 截断 |
| `tmux.py` | _safe 输入校验; _find_tmux 检测逻辑; register_tmux_tools 条件注册 |
| `diagnostics.py` | 文件类型映射; 诊断器 fallback 链; 不可用时的优雅降级 |
| `builtins.py` | Bash 超时清理; Write diff 输出; Edit diff 输出 |
| `permission` | 新增白名单命令是否正确匹配 |

### 5.2 集成测试

| 场景 | 验证点 |
|------|--------|
| Bash 超时 | `sleep 999` 在超时后是否完全清理 |
| Tmux 不可用 | 无 tmux 环境下是否优雅降级（0 个工具注册） |
| Tmux 注入 | 恶意会话名是否被正则拦截 |
| Write + Diff | 修改文件是否返回正确的 unified diff |
| GetDiagnostics | 对含错误的 Python 文件是否返回诊断结果 |

### 5.3 Harness 回归测试

| 维度 | 测试 |
|------|------|
| Guides | 安全命令 `python --version`、`pip list` 是否自动放行 |
| Sensors | `grep` 退出码 1 是否附加 "No matches found" 说明 |
| Guardrails | `rm -rf /` 是否被危险命令模式拦截 |

---

## 6. 实施步骤

### Phase 1: 基础强化（process.py + output.py + 权限增强）

1. 创建 `tools/process.py`，实现 `kill_process_tree` + `run_command` + `strip_ansi` + 退出码语义
2. 创建 `tools/output.py`，实现 `truncate_output` + `generate_unified_diff` + `truncate_diff`
3. 改造 `builtins.py::_bash` 使用 `run_command`
4. 改造 `builtins.py::_write_file` 和 `_edit_file` 返回 diff
5. 改造 `registry.py::dispatch` 使用 `truncate_output`
6. 扩展 `permission/__init__.py` 安全白名单
7. 编写单元测试

### Phase 2: Tmux 集成

1. 创建 `tools/tmux.py`，实现 11 个 Tmux 工具
2. 在 `tools/__init__.py` 中条件导入和注册
3. 编写单元测试和集成测试

### Phase 3: 代码诊断

1. 创建 `tools/diagnostics.py`，实现 GetDiagnostics
2. 编写单元测试
3. 在不同语言文件上验证

---

## 7. 参考文件索引

| 参考源 | 文件路径 | 关键行 |
|--------|----------|--------|
| CheetahClaws 进程管理 | `/Users/fisherhe/work/cheetahclaws/tools.py` | 453-495 |
| CheetahClaws 安全白名单 | `/Users/fisherhe/work/cheetahclaws/tools.py` | 329-343 |
| CheetahClaws Diff 工具 | `/Users/fisherhe/work/cheetahclaws/tools.py` | 348-361, 385-450 |
| CheetahClaws Tmux | `/Users/fisherhe/work/cheetahclaws/tmux_tools.py` | 1-322 |
| CheetahClaws 工具注册 | `/Users/fisherhe/work/cheetahclaws/tool_registry.py` | 1-98 |
| CheetahClaws 子代理 | `/Users/fisherhe/work/cheetahclaws/multi_agent/subagent.py` | 219-253 |
| FeinnAgent 当前 Bash | `/Users/fisherhe/work/feinn-agent/src/feinn_agent/tools/builtins.py` | 189-248 |
| FeinnAgent 当前注册 | `/Users/fisherhe/work/feinn-agent/src/feinn_agent/tools/registry.py` | 66-96 |
| FeinnAgent 当前权限 | `/Users/fisherhe/work/feinn-agent/src/feinn_agent/permission/__init__.py` | 15-76 |
| Harness Engineering | Martin Fowler: martinfowler.com/articles/harness-engineering.html | — |
