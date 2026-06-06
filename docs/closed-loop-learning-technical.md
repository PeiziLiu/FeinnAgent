# FeinnAgent 闭环学习系统 — 技术设计文档

> 版本: v1.0.0  
> 状态: **已实现** (src/feinn_agent/learning/)

---

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AGENT LOOP (agent.py)                            │
│                                                                         │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────┐  │
│  │ User Msg  │──▶│ LLM Call     │──▶│ Tool Dispatch│──▶│ Response   │  │
│  └──────────┘   └──────────────┘   └──────────────┘   └────────────┘  │
│       │                                                                │
│       │  ┌─────────────────────────────────────────────────────────┐   │
│       │  │  Trajectory Recorder (auto-record every turn)           │   │
│       │  └─────────────────────────────────────────────────────────┘   │
│       │  ┌─────────────────────────────────────────────────────────┐   │
│       │  │  Nudge Evaluation (per turn)                            │   │
│       │  │  _turns_since_memory += 1                               │   │
│       │  │  _iters_since_skill += tool_iterations                  │   │
│       │  └─────────────────────────────────────────────────────────┘   │
│       ▼                                                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  BACKGROUND REVIEW (threading.Thread, daemon)                   │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │  Forked ReviewAgent                                       │   │   │
│  │  │  ├─ Inherits: provider, model, api_key, base_url          │   │   │
│  │  │  ├─ Tool whitelist: MemorySave, SkillManage, SkillList    │   │   │
│  │  │  ├─ Review prompt: _MEMORY / _SKILL / _COMBINED           │   │   │
│  │  │  └─ Result: skill_manage(create/patch) + memory(add)      │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  SESSION STORE (per-turn)                                       │   │
│  │  SQLite + FTS5 → cross-session recall via SessionSearch tool    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| **learning/nudge.py** | `src/feinn_agent/learning/nudge.py` | Nudge 计数器管理、触发判断 |
| **learning/review.py** | `src/feinn_agent/learning/review.py` | Background review agent fork、prompt 模板、结果处理 |
| **learning/session_store.py** | `src/feinn_agent/learning/session_store.py` | SQLite session 存储、FTS5 索引 |
| **learning/session_search.py** | `src/feinn_agent/learning/session_search.py` | 跨会话检索工具（DISCOVER/SCROLL/BROWSE）|
| **skill/auto_create.py** | `src/feinn_agent/skill/auto_create.py` | Skill 自动创建、patch、安全扫描 |
| **skill/usage.py** | `src/feinn_agent/skill/usage.py` | Skill 使用 telemetry（.usage.json）|
| **skill/curator.py** | `src/feinn_agent/skill/curator.py` | Skill 生命周期管理、归档 |

### 1.3 数据流

```
User Input → Agent Loop → Tool Execution → Response
                              │
                              ▼
                    ┌─────────────────────┐
                    │ Turn / Iter Count    │
                    └──────┬──────────────┘
                           │ nudge threshold met?
                           ├── No → continue
                           │
                           ▼ Yes
                    ┌─────────────────────┐
                    │ Spawn Background    │
                    │ Review Thread       │
                    └──────┬──────────────┘
                           │
                           ▼
                    ┌─────────────────────┐
                    │ Fork ReviewAgent:   │
                    │ 1. Snapshot messages │
                    │ 2. Review prompt     │
                    │ 3. Run & collect     │
                    └──────┬──────────────┘
                           │
                           ▼
                    ┌─────────────────────┐
                    │ Persist Results:     │
                    │ · MemorySave()       │
                    │ · skill_manage()     │
                    │ · Display summary    │
                    └─────────────────────┘
```

---

## 2. 模块详细设计

### 2.1 Nudge 系统 (learning/nudge.py)

```python
"""
Nudge system for triggering background review.

Two independent counters:
1. Memory Nudge: counts user turns, triggers memory review
2. Skill Nudge: counts tool iterations, triggers skill review
"""

from dataclasses import dataclass, field


@dataclass
class NudgeConfig:
    """Nudge system configuration."""
    memory_nudge_interval: int = 10
    skill_nudge_interval: int = 10
    enabled: bool = True


class NudgeCounter:
    """
    Tracks nudge state for a conversation session.

    On session resume, counters are reconstructed:
        counter = prior_count % interval
    to avoid immediate trigger on resume.
    """

    def __init__(self, config: NudgeConfig | None = None):
        self.config = config or NudgeConfig()
        self._turns_since_memory: int = 0
        self._iters_since_skill: int = 0

    @property
    def should_review_memory(self) -> bool:
        if not self.config.enabled:
            return False
        if self.config.memory_nudge_interval <= 0:
            return False
        return self._turns_since_memory >= self.config.memory_nudge_interval

    @property
    def should_review_skill(self) -> bool:
        if not self.config.enabled:
            return False
        if self.config.skill_nudge_interval <= 0:
            return False
        return self._iters_since_skill >= self.config.skill_nudge_interval

    def record_turn(self):
        """Increment after each user turn."""
        self._turns_since_memory += 1

    def record_tool_iterations(self, count: int):
        """Increment after each set of tool calls."""
        self._iters_since_skill += count

    def reset_memory_nudge(self):
        self._turns_since_memory = 0

    def reset_skill_nudge(self):
        self._iters_since_skill = 0

    def reset_all(self):
        self._turns_since_memory = 0
        self._iters_since_skill = 0

    def hydrate_from_history(self, prior_turns: int, prior_tool_iters: int):
        """
        Reconstruct counters from prior session history.
        Prevents immediate nudge on session resume.
        """
        if self.config.memory_nudge_interval > 0:
            self._turns_since_memory = prior_turns % self.config.memory_nudge_interval
        if self.config.skill_nudge_interval > 0:
            self._iters_since_skill = prior_tool_iters % self.config.skill_nudge_interval

    def suppress_skill_nudge(self):
        """
        Called when agent uses skill_manage() — agent is already
        actively managing skills, so skip the nudge this cycle.
        """
        self._iters_since_skill = 0
```

### 2.2 Background Review (learning/review.py)

```python
"""
Background review system.

After every turn (when nudge fires), spawns a daemon thread that forks
a lightweight ReviewAgent to evaluate the conversation and persist
learnings as memory entries or skill updates.
"""

from dataclasses import dataclass
from typing import Callable


# ── Review Prompts ──────────────────────────────────────────────────────

_MEMORY_REVIEW_PROMPT = """
You are reviewing a conversation to persist important information about the user.
Focus on:

1. **User Identity**: name, role, preferences, work style
2. **User Preferences**: tool choices, coding style, communication preferences
3. **Important Facts**: project context, architecture decisions, constraints
4. **User Corrections**: "stop doing X", "I prefer Y"

Use `memory(action="add")` to save each insight.
Use `memory(action="update")` to update existing entries.
Be selective — only save what would be useful in future sessions.
"""

_SKILL_REVIEW_PROMPT = """
You are reviewing a conversation to create or update reusable skills (templates).
Focus on:

1. **Reproducible Workflows**: multi-step processes the user performed
2. **Problem-Solving Patterns**: debugging techniques, architecture decisions
3. **User Corrections**: "don't do it that way, do it this way"
4. **Non-trivial Techniques**: anything worth remembering for next time

Priority (highest to lowest):
1. Update a skill that was loaded this session
2. Update an existing skill from the library
3. Create a new skill

Use `skill_manage(action="create")` or `skill_manage(action="patch")`.

DO NOT capture:
- Environment-dependent transient errors
- One-off narratives or single-use operations
- Negative claims about tools (unless they reveal a preference)
"""

_COMBINED_REVIEW_PROMPT = _MEMORY_REVIEW_PROMPT + _SKILL_REVIEW_PROMPT


@dataclass
class ReviewResult:
    """Summary of background review actions."""
    actions: list[str]  # Human-readable summaries
    error: str | None = None


class BackgroundReviewer:
    """
    Orchestrates background review in a daemon thread.

    Usage:
        reviewer = BackgroundReviewer(agent, nudge_counter)
        if nudge_counter.should_review_memory or nudge_counter.should_review_skill:
            reviewer.spawn(messages_snapshot)
    """

    def __init__(self, agent, config: dict):
        self._agent = agent
        self._review_timeout = config.get("review_timeout", 30.0)

    def spawn(self, messages_snapshot: list, review_memory: bool, review_skill: bool):
        """
        Start background review in a daemon thread.
        This method returns immediately — the review runs asynchronously.
        """
        ...
```

**Review Agent Fork 流程：**
1. 从父 Agent 提取 runtime 信息（provider, model, api_key, base_url）
2. 创建 ReviewAgent 实例：
   - 继承父 Agent 的 provider 配置（利用 prompt caching）
   - `skip_memory=True`（防止写入外部 memory provider）
   - 绑定父 Agent 的 `_memory_store`
   - 工具白名单：仅允许 `MemorySave`、`SkillManage`、`SkillList`
3. 根据触发类型选择 review prompt
4. 在 `threading.Thread(daemon=True)` 中运行 review
5. 收集结果，显示摘要给用户

### 2.3 会话存储 (learning/session_store.py)

```python
"""
SQLite-backed session storage with FTS5 full-text search.

Schema:
    sessions(id TEXT PK, created_at TEXT, updated_at TEXT,
             parent_session_id TEXT REFERENCES sessions(id),
             title TEXT, model TEXT, token_count INT)

    messages(id INT PK AUTOINCREMENT, session_id TEXT REFERENCES sessions(id),
             role TEXT, content TEXT, tool_calls TEXT,
             tokens INT, model TEXT, created_at TEXT)

    messages_fts (VIRTUAL TABLE using FTS5(content))
"""

from dataclasses import dataclass


@dataclass
class SessionRecord:
    id: str
    created_at: str
    updated_at: str
    parent_session_id: str | None = None
    title: str | None = None
    model: str | None = None
    token_count: int = 0


@dataclass
class MessageRecord:
    id: int
    session_id: str
    role: str  # user / assistant / tool
    content: str
    tool_calls: str | None = None  # JSON
    tokens: int = 0
    model: str | None = None
    created_at: str


class SessionStore:
    """
    Thread-safe session storage with FTS5 search.

    Key operations:
    - create_session(): New session with optional parent link
    - append_message(): Record a message
    - end_session(): Finalize a session
    - search(): FTS5 DISCOVER mode
    - get_session_messages(): ±window around a message (SCROLL mode)
    - list_sessions(): BROWSE mode
    """

    def __init__(self, db_path: str = "~/.feinn/sessions.db"):
        self._db_path = db_path
        ...

    def _init_db(self):
        """Initialize SQLite with WAL mode and FTS5."""
        ...

    def create_session(self, parent_id: str | None = None) -> SessionRecord:
        ...

    def append_message(self, session_id: str, role: str, content: str,
                       tool_calls: list | None = None,
                       tokens: int = 0, model: str | None = None) -> MessageRecord:
        ...

    def end_session(self, session_id: str, title: str | None = None):
        ...

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """
        FTS5 DISCOVER mode.
        Returns: [{session_id, snippet, bookend_start, messages, bookend_end}]
        """
        ...

    def scroll(self, session_id: str, around_message_id: int,
               window: int = 5) -> list[MessageRecord]:
        """:SCROLL mode — get ±window around a message."""
        ...

    def browse(self, limit: int = 20) -> list[SessionRecord]:
        """BROWSE mode — list recent sessions."""
        ...
```

### 2.4 跨会话检索工具 (learning/session_search.py)

三种调用方式，零 LLM 开销：

| Shape | 参数 | 行为 |
|-------|------|------|
| DISCOVER | `query: str` | FTS5 全文搜索，返回匹配片段 + 上下文消息 |
| SCROLL | `session_id + around_message_id` | 围绕锚点消息的 ±N 窗口 |
| BROWSE | 无参数 | 列出最近会话 |

```
Tool Schema:
  name: "session_search"
  input_schema:
    type: object
    properties:
      query: { type: string, description: "Search query (DISCOVER mode)" }
      session_id: { type: string, description: "Session ID (SCROLL mode)" }
      around_message_id: { type: integer, description: "Anchor message (SCROLL)" }
      mode: { type: string, enum: ["discover", "scroll", "browse"] }
```

### 2.5 Skill 自动创建 (skill/auto_create.py)

```python
"""
Auto-creation and self-improvement of skills.

Review agent calls these functions through the SkillManage tool:
"""

from pathlib import Path
from dataclasses import dataclass


SKILL_FRONTMATTER_TEMPLATE = """\
---
id: {skill_id}
summary: {summary}
activators: [{activators}]
tools: [{tools}]
param-guide: [{param_guide}]
param-names: [{param_names}]
exec-mode: direct
visible: true
---

{template_body}
"""


def create_skill(skill_id: str, summary: str, template_body: str,
                 activators: list[str] | None = None,
                 tools: list[str] | None = None,
                 skill_dir: str | None = None) -> Path:
    """
    Create a new skill file at ~/.feinn/skills/<skill_id>/SKILL.md.

    Flow:
    1. Validate skill_id (no path traversal)
    2. Create skill directory
    3. Security scan template_body
    4. Atomic write: tempfile + os.replace
    5. Init usage telemetry
    """
    ...


def patch_skill(skill_id: str, template_body: str | None = None,
                summary: str | None = None,
                add_tools: list[str] | None = None) -> bool:
    """
    Patch an existing skill. Performs security scan on new content.
    """
    ...


def _security_scan(template_body: str) -> bool:
    """
    Scan skill content for dangerous patterns:
    - rm -rf /
    - curl | bash patterns
    - obfuscated commands
    Returns False if blocked.
    """
    ...
```

### 2.6 Skill Usage Telemetry (skill/usage.py)

```python
"""
Skill usage tracking. Persisted as .usage.json next to skills directory.

{
  "skills": {
    "commit": {
      "use_count": 42,
      "view_count": 15,
      "patch_count": 3,
      "created_at": "2026-01-15T10:30:00",
      "last_used_at": "2026-05-30T14:22:00",
      "state": "active"  // active | stale | archived | pinned
    }
  }
}
"""

from dataclasses import dataclass
from enum import Enum


class SkillState(str, Enum):
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"
    PINNED = "pinned"


@dataclass
class SkillUsage:
    skill_id: str
    use_count: int = 0
    view_count: int = 0
    patch_count: int = 0
    created_at: str = ""
    last_used_at: str = ""
    state: SkillState = SkillState.ACTIVE


def record_use(skill_id: str):
    """Increment use_count and update last_used_at."""

def record_view(skill_id: str):
    """Increment view_count."""

def record_patch(skill_id: str):
    """Increment patch_count."""

def get_usage(skill_id: str) -> SkillUsage | None:
    """Get usage stats for a skill."""

def list_stale_skills(days: int = 30) -> list[SkillUsage]:
    """List skills not used in N days."""
```

### 2.7 Skill Curator (skill/curator.py)

```python
"""
Skill lifecycle management.

States: active → stale (unused for N days) → archived (moved to .archive/)
Rules:
- Bundled skills are never curated
- Hub-installed skills are never curated
- PINNED skills are content-updatable but never deleted
"""

def run_curation(dry_run: bool = False) -> list[str]:
    """
    Scan skills directory and archive stale skills.
    Returns list of actions taken.
    """

def archive_skill(skill_id: str) -> bool:
    """Move skill to .archive/ subdirectory."""

def restore_skill(skill_id: str) -> bool:
    """Restore from .archive/ back to active."""

def pin_skill(skill_id: str) -> bool:
    """Mark skill as pinned (exempt from curation)."""
```

---

## 3. Agent Loop 集成

### 3.1 agent.py 修改点

```python
# In FeinnAgent.__init__():
self._nudge_counter = NudgeCounter(config.nudge_config)
self._background_reviewer = BackgroundReviewer(self, config)
self._trajectory_recorder = TrajectoryRecorder()
self._session_store = SessionStore()

# In FeinnAgent.run(), after tool execution:
async def run(self, message: str):
    # ... existing code ...

    # 1. Record trajectory
    self._trajectory_recorder.record_turn(turn_record)

    # 2. Record session
    self._session_store.append_message(
        session_id=self.state.session_id,
        role="user" if i == 0 else "assistant",
        content=message if i == 0 else response,
        tool_calls=tool_calls,
        tokens=turn_tokens,
    )

    # 3. Nudge check (after each user turn, after tool execution)
    self._nudge_counter.record_turn()
    self._nudge_counter.record_tool_iterations(tool_count)

    if self._nudge_counter.should_review_memory or self._nudge_counter.should_review_skill:
        self._background_reviewer.spawn(
            messages_snapshot=list(self.state.messages),
            review_memory=self._nudge_counter.should_review_memory,
            review_skill=self._nudge_counter.should_review_skill,
        )
        self._nudge_counter.reset_all()

    # 4. Suppress skill nudge when skill_manage is used
    if any(tc.name == "SkillManage" for tc in tool_calls):
        self._nudge_counter.suppress_skill_nudge()
```

### 3.2 Context Compression 集成

```python
# In compaction.py or context.py:
async def maybe_compact(self):
    # ... existing compression logic ...

    # Before compression, trigger memory extraction
    if self._session_store:
        self._session_store.end_session(self.state.session_id)
        new_session = self._session_store.create_session(
            parent_id=self.state.session_id
        )
        self.state.session_id = new_session.id
```

---

## 4. 工具注册

### 4.1 新增工具

| 工具名 | 只读 | 描述 |
|--------|------|------|
| `SkillManage` | No | 创建/更新/删除 Skill（已存在，扩展功能） |
| `SessionSearch` | Yes | 跨会话检索（DISCOVER/SCROLL/BROWSE） |

### 4.2 SkillManage 扩展

现有 `SkillManage` 工具增加 `action` 参数值：

| Action | 功能 |
|--------|------|
| `create` | 创建新 Skill（已有） |
| `patch` | 更新现有 Skill（已有） |
| `delete` | 删除 Skill |

---

## 5. 配置项

```yaml
# config.yaml additions
learning:
  enabled: true
  review_timeout: 30  # seconds
  nudge:
    memory_interval: 10   # user turns
    skill_interval: 10    # tool iterations
  
skill:
  curation:
    enabled: true
    stale_days: 30
    run_interval_hours: 24

session_store:
  db_path: "~/.feinn/sessions.db"
  enabled: true
```

---

## 6. 测试策略

### 6.1 单元测试

| 测试 | 文件 | 内容 |
|------|------|------|
| Nudge 计数 | `tests/test_learning.py` | 计数器递增、重置、hydrate、边界条件 |
| Session Store | `tests/test_learning.py` | CRUD、FTS5 搜索、session 链 |
| Skill 自动创建 | `tests/test_skill.py` | 文件写入、安全扫描阻断、原子写入 |
| Skill Telemetry | `tests/test_skill.py` | 计数递增、JSON 持久化 |
| Curator | `tests/test_skill.py` | 归档、恢复、stale 检测 |

### 6.2 集成测试

| 测试 | 内容 |
|------|------|
| Background Review | mock agent loop，触发 review，验证 memory/skill 写入 |
| Review Agent Fork | 验证 tool whitelist 生效 |
| Session Search 工具 | 在 SQLite 中插入数据，验证 DISCOVER/SCROLL/BROWSE |

### 6.3 测试配置

```python
# pytest markers
integration: marks tests requiring SQLite or filesystem
```

---

## 7. 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| CREATE | `src/feinn_agent/learning/__init__.py` | 新模块 |
| CREATE | `src/feinn_agent/learning/nudge.py` | Nudge 系统 |
| CREATE | `src/feinn_agent/learning/review.py` | Background review |
| CREATE | `src/feinn_agent/learning/session_store.py` | SQLite session 存储 |
| CREATE | `src/feinn_agent/learning/session_search.py` | Session search 工具 |
| CREATE | `src/feinn_agent/skill/auto_create.py` | Skill 自动创建/patch |
| CREATE | `src/feinn_agent/skill/usage.py` | Skill telemetry |
| CREATE | `src/feinn_agent/skill/curator.py` | Skill 生命周期管理 |
| MODIFY | `src/feinn_agent/agent.py` | 集成 nudge/review/trajectory/session |
| MODIFY | `src/feinn_agent/context.py` | 集成压缩前记忆提取 |
| MODIFY | `src/feinn_agent/types.py` | 添加 NudgeConfig 等类型 |
| MODIFY | `src/feinn_agent/tools/registry.py` | 注册 SessionSearch |
| CREATE | `tests/test_learning.py` | 学习系统测试 |
| MODIFY | `tests/test_skill.py` | 扩展 Skill 测试 |
