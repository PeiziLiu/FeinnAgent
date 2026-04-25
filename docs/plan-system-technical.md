# FeinnAgent 执行计划系统技术设计文档

## 1. 架构设计

### 1.1 整体架构

执行计划系统采用模块化设计，与FeinnAgent现有架构无缝集成：

```
┌─────────────────────────────────────────────────────────────────┐
│                         FeinnAgent CLI                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ /plan 命令   │  │ /checkpoint  │  │ /interrupt 命令      │ │
│  │              │  │ 命令         │  │                      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Plan System Modules                           │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ plan/          │  │ checkpoint/    │  │ trajectory/    │   │
│  │   - manager.py │  │   - manager.py │  │   - recorder.py│   │
│  │   - parser.py  │  │   - git_repo.py│  │   - analyzer.py│   │
│  │   - executor.py │  │   - restorer.py│  │   - formatter.py   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ interrupt/     │  │ display/       │  │ cli/           │   │
│  │   - signal.py  │  │   - diff.py    │  │   - commands.py│   │
│  │   - handler.py │  │   - preview.py │  │   - ui.py     │   │
│  └────────────────┘  │   - kawaii.py  │  └────────────────┘   │
│                       └────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FeinnAgent Core                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ agent.py     │  │ types.py     │  │ tools/registry.py    │ │
│  │ (扩展支持)    │  │ (新增事件类型) │  │ (集成plan工具)       │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 目录结构

```
src/feinn_agent/
├── plan/                          # 执行计划模块
│   ├── __init__.py
│   ├── manager.py                 # 计划管理器
│   ├── parser.py                  # 计划解析器
│   ├── executor.py                # 计划执行器
│   └── templates.py              # 计划模板
├── checkpoint/                    # Checkpoint模块
│   ├── __init__.py
│   ├── manager.py                 # Checkpoint管理器
│   ├── git_repo.py                # Git仓库操作
│   └── restorer.py                # 状态恢复器
├── trajectory/                    # Trajectory模块
│   ├── __init__.py
│   ├── recorder.py                # 轨迹记录器
│   ├── analyzer.py                # 轨迹分析器
│   ├── formatter.py               # 格式化导出
│   └── compressor.py              # 轨迹压缩
├── interrupt/                     # 中断模块
│   ├── __init__.py
│   ├── signal.py                  # 中断信号
│   └── handler.py                 # 中断处理器
├── display/                       # 显示模块
│   ├── __init__.py
│   ├── diff.py                    # Diff展示
│   ├── preview.py                  # 工具预览
│   ├── kawaii.py                  # Kawaii界面
│   └── colors.py                  # 颜色定义
├── cli/                           # CLI命令
│   ├── __init__.py
│   ├── plan_commands.py           # /plan命令
│   ├── checkpoint_commands.py      # /checkpoint命令
│   ├── interrupt_commands.py      # /interrupt命令
│   └── ui.py                      # CLI UI组件
└── types/                         # 类型定义（扩展）
    └── plan_types.py              # 计划相关类型
```

## 2. 核心模块设计

### 2.1 Plan模块

#### 2.1.1 PlanManager

```python
class PlanManager:
    """执行计划管理器"""
    
    def __init__(self, plans_dir: Path):
        self.plans_dir = plans_dir
    
    async def create_plan(self, task: str, context: dict) -> Plan:
        """根据任务创建执行计划"""
        
    async def get_plan(self, plan_id: str) -> Plan | None:
        """获取指定计划"""
        
    async def list_plans(self) -> list[Plan]:
        """列出所有计划"""
        
    async def update_plan(self, plan: Plan) -> Plan:
        """更新计划"""
        
    async def delete_plan(self, plan_id: str) -> bool:
        """删除计划"""
        
    async def execute_plan(self, plan: Plan, agent: FeinnAgent) -> PlanResult:
        """执行计划"""
```

#### 2.1.2 Plan结构

```python
@dataclass
class Plan:
    """执行计划"""
    id: str
    title: str
    task: str
    goal: str
    steps: list[PlanStep]
    status: PlanStatus
    created_at: datetime
    updated_at: datetime
    metadata: dict

@dataclass
class PlanStep:
    """计划步骤"""
    id: str
    order: int
    description: str
    expected_result: str
    dependencies: list[str]
    status: StepStatus
    actual_result: str | None = None
    notes: str | None = None

class PlanStatus(Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"

class StepStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
```

### 2.2 Checkpoint模块

#### 2.2.1 CheckpointManager

```python
class CheckpointManager:
    """Checkpoint管理器 - 使用Git shadow repo实现"""
    
    def __init__(self, checkpoints_dir: Path):
        self.checkpoints_dir = checkpoints_dir
        self.shadow_repos: dict[str, Path] = {}
    
    def create_checkpoint(
        self,
        working_dir: str | Path,
        message: str = ""
    ) -> Checkpoint:
        """创建Checkpoint快照"""
        
    def list_checkpoints(
        self,
        working_dir: str | Path
    ) -> list[Checkpoint]:
        """列出所有Checkpoint"""
        
    def get_checkpoint(
        self,
        checkpoint_id: str
    ) -> Checkpoint | None:
        """获取指定Checkpoint"""
        
    def restore_checkpoint(
        self,
        checkpoint_id: str,
        working_dir: str | Path
    ) -> RestoreResult:
        """恢复到指定Checkpoint"""
        
    def delete_checkpoint(
        self,
        checkpoint_id: str
    ) -> bool:
        """删除Checkpoint"""
        
    def cleanup_expired(self, retention_days: int = 30) -> int:
        """清理过期的Checkpoint"""
```

#### 2.2.2 GitRepoHelper

```python
class GitRepoHelper:
    """Git仓库操作辅助类"""
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
        self.shadow_repo: Path | None = None
    
    def _get_shadow_repo_path(self) -> Path:
        """获取shadow repo路径"""
        
    def _run_git(self, args: list[str]) -> tuple[int, str, str]:
        """执行git命令"""
        
    def commit(self, message: str) -> str:
        """创建提交"""
        
    def get_history(self, max_count: int = 100) -> list[GitCommit]:
        """获取提交历史"""
        
    def diff(self, commit_id: str) -> str:
        """获取指定提交的diff"""
        
    def restore(self, commit_id: str) -> bool:
        """恢复到指定提交"""
```

### 2.3 Trajectory模块

#### 2.3.1 TrajectoryRecorder

```python
class TrajectoryRecorder:
    """轨迹记录器"""
    
    def __init__(
        self,
        trajectories_dir: Path,
        session_id: str
    ):
        self.trajectories_dir = trajectories_dir
        self.session_id = session_id
        self.turns: list[TurnRecord] = []
        self.checkpoints: list[CheckpointRecord] = []
        self.interrupts: list[InterruptRecord] = []
    
    def record_turn(
        self,
        turn: TurnRecord
    ) -> None:
        """记录一个turn"""
        
    def record_checkpoint(
        self,
        checkpoint: CheckpointRecord
    ) -> None:
        """记录checkpoint创建"""
        
    def record_interrupt(
        self,
        interrupt: InterruptRecord
    ) -> None:
        """记录中断"""
        
    async def save(self) -> Path:
        """保存轨迹到文件"""
        
    def get_stats(self) -> TrajectoryStats:
        """获取统计信息"""
```

#### 2.3.2 TrajectoryAnalyzer

```python
class TrajectoryAnalyzer:
    """轨迹分析器"""
    
    def analyze_efficiency(
        self,
        trajectory: Trajectory
    ) -> EfficiencyAnalysis:
        """分析执行效率"""
        
    def compare_trajectories(
        self,
        trajectory1: Trajectory,
        trajectory2: Trajectory
    ) -> ComparisonResult:
        """对比两条轨迹"""
        
    def identify_bottlenecks(
        self,
        trajectory: Trajectory
    ) -> list[Bottleneck]:
        """识别瓶颈"""
```

### 2.4 Interrupt模块

#### 2.4.1 InterruptSignal

```python
class InterruptSignal:
    """中断信号管理器"""
    
    _event: threading.Event = threading.Event()
    _interrupt_reason: str | None = None
    
    @classmethod
    def set_interrupt(cls, reason: str = "") -> None:
        """设置中断信号"""
        
    @classmethod
    def clear_interrupt(cls) -> None:
        """清除中断信号"""
        
    @classmethod
    def is_interrupted(cls) -> bool:
        """检查是否被中断"""
        
    @classmethod
    def get_reason(cls) -> str | None:
        """获取中断原因"""
```

#### 2.4.2 InterruptHandler

```python
class InterruptHandler:
    """中断处理器"""
    
    def __init__(
        self,
        agent: FeinnAgent,
        trajectory_recorder: TrajectoryRecorder
    ):
        self.agent = agent
        self.recorder = trajectory_recorder
        self._interrupted_turn: int | None = None
    
    async def handle_interrupt(self) -> InterruptResult:
        """处理中断"""
        
    async def resume(self) -> ResumeResult:
        """恢复执行"""
        
    def get_interrupted_state(self) -> InterruptedState:
        """获取中断时的状态"""
```

## 3. 显示模块设计

### 3.1 Diff展示

```python
class DiffDisplay:
    """Diff展示器"""
    
    def __init__(self, use_color: bool = True):
        self.use_color = use_color
    
    def show_file_diff(
        self,
        before: str,
        after: str,
        filename: str
    ) -> str:
        """生成文件diff"""
        
    def show_changes_summary(
        self,
        changes: list[FileChange]
    ) -> str:
        """生成变更摘要"""
    
    def format_unified_diff(
        self,
        old_lines: list[str],
        new_lines: list[str],
        context: int = 3
    ) -> str:
        """格式化为unified diff"""
```

### 3.2 工具预览

```python
class ToolPreview:
    """工具预览"""
    
    def preview_tool_call(
        self,
        tool_name: str,
        arguments: dict
    ) -> str:
        """生成工具调用预览"""
        
    def format_arguments(
        self,
        arguments: dict
    ) -> str:
        """格式化参数显示"""
```

### 3.3 Kawaii界面

```python
class KawaiiDisplay:
    """Kawaii风格界面"""
    
    # 状态表情
    STATUS_EMOJI = {
        "thinking": "🤔",
        "executing": "⚡",
        "success": "✨",
        "error": "😢",
        "warning": "🤨",
        "waiting": "⏳",
        "completed": "🎉",
        "interrupted": "🛑",
    }
    
    def show_progress(
        self,
        current: int,
        total: int,
        message: str = ""
    ) -> str:
        """显示进度"""
        
    def show_tool_start(
        self,
        tool_name: str,
        args: dict
    ) -> str:
        """显示工具开始"""
        
    def show_tool_end(
        self,
        tool_name: str,
        result: str
    ) -> str:
        """显示工具结束"""
        
    def show_plan_step(
        self,
        step: PlanStep,
        index: int
    ) -> str:
        """显示计划步骤"""
```

## 4. CLI命令设计

### 4.1 Plan命令

```python
# /plan - 显示当前计划
async def cmd_plan(args: list[str], cli: FeinnCLI) -> bool:
    """显示或编辑执行计划"""
    if not args:
        return await show_current_plan(cli)
    elif args[0] == "edit":
        return await edit_plan(cli)
    elif args[0] == "approve":
        return await approve_plan(cli)
    elif args[0] == "abort":
        return await abort_plan(cli)
```

### 4.2 Checkpoint命令

```python
# /checkpoint list - 列出所有Checkpoint
async def cmd_checkpoint_list(args: list[str], cli: FeinnCLI) -> bool:
    """列出Checkpoint"""

# /checkpoint save - 保存Checkpoint
async def cmd_checkpoint_save(args: list[str], cli: FeinnCLI) -> bool:
    """保存Checkpoint"""

# /checkpoint restore <id> - 恢复Checkpoint
async def cmd_checkpoint_restore(args: list[str], cli: FeinnCLI) -> bool:
    """恢复Checkpoint"""
```

### 4.3 Interrupt命令

```python
# /interrupt - 中断执行
async def cmd_interrupt(args: list[str], cli: FeinnCLI) -> bool:
    """中断当前执行"""

# /resume - 恢复执行
async def cmd_resume(args: list[str], cli: FeinnCLI) -> bool:
    """恢复执行"""
```

## 5. Agent集成

### 5.1 事件类型扩展

```python
# types.py 新增事件类型

@dataclass
class PlanCreated:
    """计划已创建"""
    plan: Plan

@dataclass
class PlanStepCompleted:
    """计划步骤完成"""
    plan_id: str
    step: PlanStep

@dataclass
class CheckpointCreated:
    """Checkpoint已创建"""
    checkpoint: Checkpoint

@dataclass
class CheckpointRestored:
    """Checkpoint已恢复"""
    checkpoint_id: str

@dataclass
class Interrupted:
    """执行被中断"""
    reason: str
    turn: int

@dataclass
class Resumed:
    """执行已恢复"""
    from_turn: int
```

### 5.2 Agent扩展

```python
class FeinnAgent:
    # 新增属性
    plan_manager: PlanManager | None = None
    checkpoint_manager: CheckpointManager | None = None
    trajectory_recorder: TrajectoryRecorder | None = None
    interrupt_handler: InterruptHandler | None = None
    
    # 新增配置
    def __init__(
        self,
        config: dict[str, Any],
        enable_plan_system: bool = True,
        enable_checkpoint: bool = True,
        enable_trajectory: bool = True,
    ):
        # 初始化各管理器
```

## 6. 数据存储

### 6.1 目录结构

```
~/.feinn/
├── .env                     # 环境配置
├── plans/                   # 执行计划
│   ├── 20260418-120000-task1.md
│   └── 20260418-130000-task2.md
├── checkpoints/             # Checkpoint存储 (Git shadow repos)
│   └── {sha256(working_dir)}/
│       ├── HEAD
│       ├── refs/
│       ├── objects/
│       └── HERMES_WORKDIR
├── trajectories/            # 轨迹记录
│   ├── session-xxx.json
│   └── session-yyy.json.gz
└── logs/                   # 日志
    └── feinn.log
```

### 6.2 Plan文件格式

```markdown
---
id: plan-20260418-120000
title: 实现用户登录功能
status: in_progress
created_at: 2026-04-18T12:00:00
updated_at: 2026-04-18T12:30:00
---

# 执行计划：实现用户登录功能

## 任务目标
实现用户的登录和登出功能，包括表单验证、会话管理和安全保护。

## 执行步骤

### 步骤 1: 创建登录表单
- [x] 完成
- 预期结果：包含用户名、密码输入框和登录按钮
- 实际结果：✅ 创建了 login.html

### 步骤 2: 实现后端验证API
- [x] 完成
- 预期结果：返回JWT token
- 实际结果：✅ POST /api/auth/login 返回token

### 步骤 3: 添加会话管理
- [ ] 待执行
- 预期结果：用户状态持久化
- 依赖：步骤2完成

## 元数据
- 创建者: FeinnAgent
- 版本: 1.0
```

### 6.3 Trajectory JSON格式

```json
{
  "version": "1.0",
  "session_id": "sess-abc123",
  "agent_id": "feinn-001",
  "created_at": "2026-04-18T12:00:00Z",
  "completed_at": "2026-04-18T12:45:00Z",
  "status": "completed",
  "config": {
    "model": "siliconflow/Pro/zai-org/GLM-5.1",
    "max_iterations": 50
  },
  "turns": [
    {
      "turn": 1,
      "user_message": {
        "content": "实现用户登录功能",
        "images": []
      },
      "assistant": {
        "text": "我将为您实现用户登录功能...",
        "reasoning": "需要先了解现有代码结构...",
        "tool_calls": [
          {
            "id": "call_001",
            "name": "read_file",
            "arguments": {"path": "src/app.py"}
          }
        ]
      },
      "tool_results": [
        {
          "tool_call_id": "call_001",
          "tool_name": "read_file",
          "result": "def app()...",
          "duration_ms": 150
        }
      ],
      "tokens": {
        "input": 1200,
        "output": 3400
      },
      "duration_ms": 5200
    }
  ],
  "checkpoints": [
    {
      "id": "ckpt-001",
      "created_at": "2026-04-18T12:05:00Z",
      "commit_id": "abc123",
      "message": "Before implementing auth"
    }
  ],
  "interrupts": [],
  "stats": {
    "total_turns": 12,
    "total_tokens": 45600,
    "total_duration_ms": 180000,
    "tool_calls": {
      "read_file": 25,
      "write_file": 8,
      "execute_command": 3
    }
  }
}
```

## 7. 实现顺序

### Phase 1: 基础架构
1. 创建模块目录结构
2. 实现基础数据类型
3. 实现Interrupt信号机制
4. 实现Checkpoint管理器

### Phase 2: 核心功能
5. 实现Plan管理器
6. 实现Trajectory记录器
7. 实现Agent集成

### Phase 3: CLI命令
8. 实现Plan命令
9. 实现Checkpoint命令
10. 实现Interrupt命令
11. 实现Resume命令

### Phase 4: 可视化
12. 实现Diff展示
13. 实现工具预览
14. 实现Kawaii界面
15. 实现Trajectory分析

### Phase 5: 测试和优化
16. 单元测试
17. 集成测试
18. 性能优化
19. 文档完善

## 8. 测试策略

### 8.1 单元测试
- 每个模块独立测试
- Mock外部依赖
- 覆盖率目标 >= 80%

### 8.2 集成测试
- Agent完整执行流程
- Checkpoint创建和恢复
- 中断和恢复流程

### 8.3 回归测试
- 确保现有功能不受影响
- 自动化测试套件

## 9. 配置项

```yaml
# config.yaml
plan:
  enabled: true
  auto_create: true
  save_directory: "~/.feinn/plans"

checkpoint:
  enabled: true
  save_directory: "~/.feinn/checkpoints"
  max_files: 50000
  retention_days: 30
  exclude_patterns:
    - "*.pyc"
    - "__pycache__/"
    - ".git/"
    - "node_modules/"
    - "*.log"

trajectory:
  enabled: true
  save_directory: "~/.feinn/trajectories"
  compression: true
  max_size_mb: 100

interrupt:
  enabled: true
  response_timeout_ms: 100

display:
  use_color: true
  show_diff: true
  kawaii_style: true
```

## 10. 错误处理

### 10.1 错误类型

```python
class PlanError(Exception):
    """计划相关错误"""
    
class CheckpointError(Exception):
    """Checkpoint相关错误"""
    
class TrajectoryError(Exception):
    """轨迹相关错误"""
    
class InterruptError(Exception):
    """中断相关错误"""
```

### 10.2 恢复策略

- Checkpoint创建失败：回退到原状态，提示用户
- Checkpoint恢复失败：保留原状态，提供手动恢复指引
- 轨迹保存失败：重试3次，记录到日志
- 中断响应超时：强制停止执行
