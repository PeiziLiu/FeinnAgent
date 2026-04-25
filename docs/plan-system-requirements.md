# FeinnAgent 执行计划系统需求文档

## 1. 概述

### 1.1 项目背景

FeinnAgent是一个企业级异步AI Agent框架，目前具备基础的Agent循环和工具调用能力。但在任务执行可视化、计划管理和执行控制方面相比Hermes-agent还有差距。本文档旨在定义执行计划系统的完整需求，为后续开发提供指导。

### 1.2 目标与范围

**目标**：为FeinnAgent构建一套完整的执行计划系统，支持任务计划的展示、编辑和执行，提供Checkpoint机制、执行轨迹记录和中断恢复能力。

**范围**：
- 执行计划管理（/plan命令）
- Checkpoint机制（文件系统快照和回滚）
- Trajectory轨迹记录
- 中断和恢复机制
- 丰富的可视化界面

### 1.3 术语定义

| 术语 | 定义 |
|------|------|
| Plan | 执行计划，包含任务分解和执行步骤 |
| Checkpoint | 文件系统快照，用于回滚 |
| Trajectory | 执行轨迹，记录完整的对话和工具调用历史 |
| Interrupt | 中断信号，用于停止正在执行的Agent |
| Rollback | 回滚操作，恢复到某个Checkpoint状态 |

## 2. 功能需求

### 2.1 执行计划系统

#### 2.1.1 计划创建

- **FR-001**: Agent能够根据用户输入自动生成执行计划
- **FR-002**: 计划以Markdown格式存储在`.feinn/plans/`目录下
- **FR-003**: 计划文件名格式：`{timestamp}-{task_summary}.md`
- **FR-004**: 计划包含：任务目标、步骤分解、依赖关系、预期结果

#### 2.1.2 计划展示

- **FR-005**: 支持`/plan`命令查看当前执行计划
- **FR-006**: 计划展示包含：编号列表、步骤状态（待执行/执行中/已完成）、预估时间
- **FR-007**: 支持在CLI中实时显示计划执行进度
- **FR-008**: 计划变更历史可追溯

#### 2.1.3 计划编辑

- **FR-009**: 支持在执行前编辑计划（增删改步骤）
- **FR-010**: 支持调整步骤执行顺序
- **FR-011**: 支持添加步骤说明和备注
- **FR-012**: 编辑后的计划需要用户确认才能执行

#### 2.1.4 计划执行

- **FR-013**: 支持按计划步骤顺序执行
- **FR-014**: 支持跳过特定步骤
- **FR-015**: 支持在任意步骤暂停/继续
- **FR-016**: 执行结果与计划预期对比展示

### 2.2 Checkpoint机制

#### 2.2.1 快照创建

- **FR-017**: 在每个Agent turn开始前自动创建Checkpoint
- **FR-018**: Checkpoint存储在`~/.feinn/checkpoints/`目录下
- **FR-019**: 使用Git shadow repo实现增量快照
- **FR-020**: 支持手动创建Checkpoint（`/checkpoint save`命令）
- **FR-021**: 快照文件限制：最大50,000个文件，避免性能问题

#### 2.2.2 快照管理

- **FR-022**: 列出所有可用的Checkpoint（`/checkpoint list`）
- **FR-023**: 查看Checkpoint详细信息（时间、文件变更统计）
- **FR-024**: 删除不需要的Checkpoint
- **FR-025**: Checkpoint过期策略：默认保留30天

#### 2.2.3 回滚操作

- **FR-026**: 支持恢复到指定Checkpoint（`/checkpoint restore`）
- **FR-027**: 回滚前显示将要恢复的变更内容
- **FR-028**: 回滚后可以重新执行
- **FR-029**: 回滚操作记录到Trajectory

### 2.3 Trajectory轨迹记录

#### 2.3.1 轨迹数据

- **FR-030**: 记录每个Agent turn的完整上下文
- **FR-031**: 记录工具调用：工具名、参数、结果、执行时间
- **FR-032**: 记录LLM响应：文本输出、reasoning内容
- **FR-033**: 记录Token使用量统计
- **FR-034**: 记录错误和异常信息

#### 2.3.2 轨迹格式

- **FR-035**: 使用标准JSON格式存储轨迹
- **FR-036**: 轨迹文件存储在`~/.feinn/trajectories/`目录下
- **FR-037**: 支持轨迹压缩（减少存储空间）
- **FR-038**: 支持轨迹导出为可读格式（Markdown）

#### 2.3.3 轨迹分析

- **FR-039**: 提供轨迹统计：总turn数、Token消耗、工具调用统计
- **FR-040**: 提供执行效率分析：各步骤耗时、瓶颈识别
- **FR-041**: 支持轨迹对比：不同执行的效率对比

### 2.4 中断和恢复

#### 2.4.1 中断机制

- **FR-042**: 支持`/interrupt`命令立即停止执行
- **FR-043**: 中断信号通过threading.Event实现
- **FR-044**: 工具在执行中可以检查中断状态并响应
- **FR-045**: 中断后保留当前执行状态

#### 2.4.2 恢复机制

- **FR-046**: 支持从中断点恢复执行（`/resume`命令）
- **FR-047**: 恢复后保留完整的对话历史
- **FR-048**: 支持查看中断前的执行状态
- **FR-049**: 恢复后可选择继续或放弃当前任务

### 2.5 可视化界面

#### 2.5.1 CLI输出

- **FR-050**: 工具调用显示带颜色和图标
- **FR-051**: 文件修改显示diff对比
- **FR-052**: 进度条显示执行进度
- **FR-053**: 错误信息高亮显示

#### 2.5.2 工具预览

- **FR-054**: 工具执行前显示预览信息
- **FR-055**: 预览包含：工具名、参数摘要、预期结果
- **FR-056**: 支持在预览中确认/取消操作

#### 2.5.3 Kawaii风格界面

- **FR-057**: 使用表情符号展示状态（✨、🎯、✅等）
- **FR-058**: 友好的进度提示
- **FR-059**: 错误提示带有建议

## 3. 非功能需求

### 3.1 性能

- **NFR-001**: Checkpoint创建时间 < 5秒（对于<10,000文件）
- **NFR-002**: 回滚操作时间 < 10秒（对于<10,000文件）
- **NFR-003**: 轨迹记录不影响Agent响应速度
- **NFR-004**: CLI界面刷新率 >= 10fps

### 3.2 可靠性

- **NFR-005**: Checkpoint数据完整性校验
- **NFR-006**: 回滚失败后自动恢复原状态
- **NFR-007**: 轨迹记录支持断点续传
- **NFR-008**: 中断响应延迟 < 100ms

### 3.3 安全性

- **NFR-009**: Checkpoint数据加密存储（可选）
- **NFR-010**: 敏感信息（如API密钥）不记录到轨迹
- **NFR-011**: 回滚操作需要用户确认
- **NFR-012**: 轨迹文件权限控制

### 3.4 可用性

- **NFR-013**: CLI命令帮助信息完整
- **NFR-014**: 错误信息提供解决建议
- **NFR-015**: 新用户快速上手指南
- **NFR-016**: 配置项有合理的默认值

## 4. 用户交互

### 4.1 命令列表

| 命令 | 描述 | 优先级 |
|------|------|--------|
| `/plan` | 显示当前执行计划 | P0 |
| `/plan edit` | 编辑执行计划 | P1 |
| `/checkpoint list` | 列出所有Checkpoint | P0 |
| `/checkpoint save` | 保存当前Checkpoint | P1 |
| `/checkpoint restore <id>` | 恢复到指定Checkpoint | P0 |
| `/interrupt` | 中断当前执行 | P0 |
| `/resume` | 恢复中断的执行 | P1 |
| `/trajectory` | 显示当前执行轨迹 | P1 |
| `/trajectory export` | 导出轨迹到文件 | P2 |

### 4.2 用户流程

#### 流程1：创建和执行计划

```
用户输入任务
  ↓
Agent生成执行计划
  ↓
用户查看计划 (/plan)
  ↓
用户确认或编辑计划
  ↓
按计划执行各步骤
  ↓
展示执行结果
```

#### 流程2：Checkpoint回滚

```
执行过程中发生错误
  ↓
用户查看Checkpoint列表 (/checkpoint list)
  ↓
用户选择恢复点
  ↓
显示将要恢复的变更
  ↓
用户确认回滚
  ↓
恢复到Checkpoint状态
  ↓
用户决定重新执行或放弃
```

#### 流程3：中断和恢复

```
用户输入任务
  ↓
Agent开始执行
  ↓
用户发现问题，输入 /interrupt
  ↓
执行立即停止
  ↓
用户查看当前状态
  ↓
用户决定：/resume 继续 或 /plan 调整计划
```

## 5. 成功标准

### 5.1 功能验收

- [ ] 所有P0优先级命令正常工作
- [ ] Checkpoint创建和恢复功能正常
- [ ] 轨迹记录完整且可查询
- [ ] 中断和恢复机制响应及时
- [ ] 可视化界面清晰易用

### 5.2 性能验收

- [ ] Checkpoint性能满足NFR要求
- [ ] 轨迹记录不影响Agent响应
- [ ] CLI界面流畅无卡顿

### 5.3 测试覆盖

- [ ] 单元测试覆盖率 >= 80%
- [ ] 集成测试覆盖核心流程
- [ ] 回归测试通过率 >= 95%

## 6. 参考资料

- Hermes-agent项目：https://github.com/architect.ai/hermes-agent
- Checkpoint Manager实现：`hermes-agent/tools/checkpoint_manager.py`
- Interrupt机制实现：`hermes-agent/tools/interrupt.py`
- Display模块实现：`hermes-agent/agent/display.py`
- Trajectory格式：`hermes-agent/docs/developer-guide/trajectory-format.md`

## 7. 附录

### 7.1 数据结构

#### Plan结构

```markdown
# 执行计划：{任务标题}

## 任务目标
{描述}

## 执行步骤

1. [ ] 步骤1：{描述}
   - 预期结果：{描述}
   - 依赖：{前置步骤}

2. [x] 步骤2：{描述}
   - 实际结果：{描述}

## 元数据
- 创建时间：{timestamp}
- 最后更新：{timestamp}
- 执行状态：{in_progress|completed|aborted}
```

#### Trajectory结构

```json
{
  "version": "1.0",
  "session_id": "xxx",
  "created_at": "timestamp",
  "turns": [
    {
      "turn": 1,
      "user_message": "...",
      "assistant_response": {
        "text": "...",
        "reasoning": "...",
        "tool_calls": [...]
      },
      "tool_results": [...],
      "tokens": {
        "input": 100,
        "output": 200
      }
    }
  ],
  "checkpoints": [...],
  "interrupts": [...]
}
```

### 7.2 配置项

```yaml
plan:
  enabled: true
  save_directory: "~/.feinn/plans"
  auto_create: true

checkpoint:
  enabled: true
  save_directory: "~/.feinn/checkpoints"
  max_files: 50000
  retention_days: 30

trajectory:
  enabled: true
  save_directory: "~/.feinn/trajectories"
  compression: true
  max_size_mb: 100

interrupt:
  enabled: true
  response_timeout_ms: 100
```
