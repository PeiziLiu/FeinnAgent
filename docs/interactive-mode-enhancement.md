# Interactive Mode Enhancement - 需求文档

## 1. 概述

### 背景
当前 feinn -i 交互模式缺少任务规划和执行进度的可视化，用户难以了解当前处理状态。

### 目标
增强 feinn -i 模式体验，显示：
1. 任务规划的 todo 列表
2. 执行进度条
3. 处理过程中的关键信息（工具调用、thinking等）

### 验收标准
- [ ] 显示任务 todo 列表（待处理）
- [ ] 显示执行进度（百分比/进度条）
- [ ] 工具执行时显示状态图标
- [ ] Thinking 信息可折叠显示
- [ ] Token 消耗和成本显示

---

## 2. 设计方案

### 方案选择

| 方案 | 优点 | 缺点 | 结论 |
|------|-----|-----|------|
| A: 仅用 emoji | 简单 | 信息量少 | ❌ |
| B: 显示模块 | 可复用 | 需要新模块 | ✅ |
| C: 混合方案 | 平衡 | 需拆分类 | 推荐 |

### 详细设计

#### 1. 增强 KawaiiDisplay 类

```python
class KawaiiDisplay:
    # 新增方法
    def show_todo_list(self, items: list[dict]) -> str
    def show_progress_detailed(self, current, total, step_name) -> str
    def show_thinking_collapsed(self, thinking) -> str
```

#### 2. 增强 CLI交互

```python
# 显示 todo 列表
# ┌─ 📋 任务规划 ─────────────┐
# │ ☐ [1] step 1        │
# │ ☐ [2] step 2        │
# │ ▶ [3] 执行中...     │
# │ ✅ [4] 已完成      │
# └────────────────────┘

# 显示工具执行
# ⚡ [tool_name] 读取文件
# ⚙️ 处理中...
# ✅ success

# 显示进度
# ⚡ [3/5] 60% [██████░░░░] step-name
```

---

## 3. 实现计划

| 步骤 | 任务 | 状态 |
|------|------|------|
| 1 | 增强 KawaiiDisplay 添加 todo/进度方法 | TODO |
| 2 | 修改 cli.py 使用新的显示方法 | TODO |
| 3 | 添加测试 | TODO |
| 4 | 验证功能 | TODO |