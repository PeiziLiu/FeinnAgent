# FeinnAgent 开发Skill规范

基于 Harness Engineering 的软件开发流程，确保需求完整性和开发质量的可复用开发规范

---

## 1. 概述

### 1.1 目的

本规范沉淀 FeinnAgent 项目开发经验，提供可复用的开发流程模板，降低后续开发的学习成本和维护成本。

### 1.2 核心理念

**Harness Engineering**: 通过约束、工具、文档和反馈循环保持开发正轨

**Hardness Programming**: 像硬件开发一样严谨对待软件开发

### 1.3 开发流程概览

```
需求分析 → 技术设计 → 编码实现 → 测试验证 → 合并部署
    ↑                                            ↓
    └──────────────── feedback ────────────────────┘
```

---

## 2. 需求分析阶段

### 2.1 需求发现清单

每次开发前必须明确回答以下问题：

| # | 问题 | 回答方式 |
|---|------|----------|
| 1 | 这是新增需求还是 roadmap 中的既有需求？ | 查看 docs/roadmap.md |
| 2 | 需求的影响范围是什么？ | 确定涉及的模块 |
| 3 | 是否需要更新架构设计？ | 确定是否影响分层架构 |
| 4 | 测试策略是什么？ | 确定测试覆盖范围 |

### 2.2 需求分类

| 类型 | 处理方式 |
|------|----------|
| **新增需求** | 1. 补充 docs/requirements.md<br>2. 更新 docs/roadmap.md<br>3. 创建需求追踪 Issue |
| **Roadmap需求** | 1. 标记为 "进行中"<br>2. 检查依赖项<br>3. 确认技术方案 |
| **Bug修复** | 1. 复现问题<br>2. 分析根因<br>3. 确定修复方案 |

### 2.3 需求文档模板

```markdown
## [需求标题]

### 背景
[需求产生的业务场景或用户痛点]

### 目标
[希望通过功能达成什么效果]

### 详细描述
[功能的具体行为]

### 验收标准
- [ ] 标准1
- [ ] 标准2

### 技术影响
- 模块影响: [列出受影响模块]
- 依赖项: [列出依赖项]

### 风险评估
- 风险1: [描述]
```

---

## 3. 技术设计阶段

### 3.1 设计检查清单

| # | 检查项 | 通过标准 |
|---|-------|---------|
| 1 | 是否需要更新架构文档？ | 如需更新，已更新 docs/architecture.md |
| 2 | 接口变更是否向后兼容？ | 不破坏现有 API |
| 3 | 数据库/schema 是否需要迁移？ | 如需迁移，已设计迁移脚本 |
| 4 | 性能影响评估 | 延迟增加 < 10% |
| 5 | 安全影响评估 | 无新增安全风险 |

### 3.2 技术设计文档模板

```markdown
# [功能名称] 技术设计

## 概述
[简述要实现的功能]

## 设计方案

### 方案选择
| 方案 | 优点 | 缺点 | 结论 |
|------|-----|-----|------|
| 方案A | ... | ... | ... |

### 详细设计

#### 模块结构
```
[模块A]
  ├── 函数1()
  └── 函数2()

[模块B]
  └── 类C
```

#### API 设计

##### 公共接口
```python
async def public_api(param: Type) -> ReturnType:
    """API 说明"""
```

##### 内部接口
```python
async def _internal_api(param: Type) -> ReturnType:
    """内部使用，不对外暴露"""
```

#### 数据结构
```python
@dataclass
class FeatureData:
    """功能数据"""
    field1: str
    field2: int
```

### 实现计划

| 步骤 | 任务 | 状态 |
|------|------|------|
| 1 | [任务1] | TODO |
| 2 | [任务2] | TODO |

### 测试计划
- 单元测试: [测试文件]
- 集成测试: [测试文件]
- 回归测试: [验证现有功能未被破坏]
```

---

## 4. 编码实现阶段

### 4.1 环境准备

```bash
# 1. 确保本地 dev 分支是��新的
git checkout dev
git pull origin dev

# 2. 基于最新版本创建 worktree
git worktree add ../feinn-agent-feature-xxx dev

# 3. 进入 worktree 目录
cd ../feinn-agent-feature-xxx
```

### 4.2 分支管理

| 分支类型 | 命名规范 | 说明 |
|---------|---------|------|
| 功能 | feature/<描述> | 新功能开发 |
| Bug修复 | bugfix/<描述> | Bug修复 |
| 紧急修复 | hotfix/<描述> | 紧急修复 |
| 文档 | docs/<描述> | 文档更新 |

### 4.3 提交规范

使用 Conventional Commits：

| 类型 | 说明 | 示例 |
|------|------|------|
| feat | 新功能 | `feat: 添加浏览器自动化` |
| fix | Bug修复 | `fix: 修复内存泄漏` |
| docs | 文档 | `docs: 更新README` |
| style | 格式调整 | `style: 格式化代码` |
| refactor | 重构 | `refactor: 简化逻辑` |
| test | 测试 | `test: 添加单元测试` |
| chore | 构建/工具 | `chore: 更新依赖` |

```bash
# 提交示例
git commit -m "feat: 添加浏览器自动化功能

- 实现 browser_navigate/browser_snapshot 等工具
- 支持 local/Browserbase/BrowserUse/Firecrawl 多后端
- 添加 SSRF 保护

Closes #123"
```

---

## 5. 测试验证阶段

### 5.1 测试金字塔

```
        /\
       /  \     端到端测试 (E2E)
      /----\    (~10%)
     /      \   集成测试
    /--------\  (~30%)
   /          \ 单元测试
  /------------\ (~60%)
```

### 5.2 测试文件命名规范

| 被测模块 | 测试文件 |
|----------|---------|
| agent.py | tests/test_agent.py |
| tools/builtins.py | tests/test_tools.py |
| compaction.py | tests/test_compaction.py |
| skill/loader.py | tests/test_skill.py |
| memory/store.py | tests/test_memory.py |

### 5.3 测试编写规范

```python
import pytest
from unittest.mock import AsyncMock

class TestFeatureName:
    """功能名称测试"""

    def test_basic_functionality(self):
        """测试基本功能"""
        # Arrange - 准备测试数据
        input_data = ...
        
        # Act - 执行操作
        result = process(input_data)
        
        # Assert - 验证结果
        assert result == expected

    @pytest.mark.asyncio
    async def test_async_function(self):
        """测试异步功能"""
        # 使用 AsyncMock mock 异步依赖
        mock_provider = AsyncMock()
        ...
```

### 5.4 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v --tb=short

# 运行特定模块测试
python -m pytest tests/test_xxx.py -v

# 带覆盖率
python -m pytest tests/ --cov=src/feinn_agent --cov-report=term-missing

# 快速测试（排除慢速集成测试）
python -m pytest tests/ -v -m "not integration"
```

### 5.5 代码质量检查

```bash
# 代码检查
python -m ruff check src/

# 代码格式化
python -m ruff format src/

# 类型检查（如配置）
python -m mypy src/feinn_agent/
```

---

## 6. 合并部署阶段

### 6.1 合并前检查

| # | 检查项 | 状态 |
|---|-------|------|
| 1 | 代码审查完成 | ☐ |
| 2 | 所有测试通过 | ☐ |
| 3 | 文档已更新 | ☐ |
| 4 | CHANGELOG已更新 | ☐ |
| 5 | 无冲突可合并 | ☐ |

### 6.2 合并流程

```bash
# 1. 同步 dev 最新更改
git checkout dev
git pull origin dev
git checkout feature/xxx
git rebase dev

# 2. 解决冲突后推送
git push origin feature/xxx --force-with-lease

# 3. 合并到 dev
git checkout dev
git merge --no-ff feature/xxx -m "Merge feature/xxx: 功能描述"
git push origin dev

# 4. 清理 worktree
git worktree remove ../feinn-agent-feature-xxx
git branch -d feature/xxx
```

---

## 7. Harness Engineering 检查

### 7.1 Guides（前置引导）

| 检查项 | 说明 |
|-------|------|
| 工具描述 | 清晰描述使用场景和限制 |
| 超时建议 | 包含参数说明 |
| 安全命令 | 相关安全命令添加到白名单 |
| 使用示例 | 工具包含使用示例 |

### 7.2 Sensors（后置检测）

| 检查项 | 说明 |
|-------|------|
| Diff反馈 | 文件变更返回 unified diff |
| 退出码 | 常见退出码有语义解释 |
| 输出截断 | 保留尾部信息 |
| ANSI清理 | 转义码在返回前清理 |

### 7.3 Guardrails（安全护栏）

| 检查项 | 说明 |
|-------|------|
| 进程清理 | 进程/子进程在超时/异常时清理 |
| 输入验证 | 用户输入验证防止注入 |
| 危险命令 | 检测和拦截危险命令 |
| 安全标志 | 工具设置正确安全标志 |

---

## 8. 常用模板速查

### 8.1 新功能开发模板

```bash
# 1. 创建功能分支
git checkout -b feature/my-feature

# 2. 创建需求文档
# 编辑 docs/requirements.md

# 3. 创建技术设计文档
# 编辑 docs/feature-technical.md

# 4. 开发实现
# ...

# 5. 添加测试
# 创建 tests/test_my_feature.py

# 6. 测试验证
python -m pytest tests/test_my_feature.py -v

# 7. 代码质量
python -m ruff check src/

# 8. 提交
git add -A
git commit -m "feat: 添加功能描述"

# 9. 合并
git checkout dev
git merge --no-ff feature/my-feature
```

### 8.2 Bug修复模板

```bash
# 1. 复现问题
# 确认问题可复现

# 2. 分析根因
# 找到问题根因

# 3. 修复
git checkout -b bugfix/issue-description

# 4. 添加回归测试
# 确保问题不会再次出现

# 5. 验证修复
python -m pytest tests/ -v

# 6. 提交
git commit -m "fix: 修复问题描述

解决: [问题根因]
验证: [测试方法]

Closes #xxx"
```

### 8.3 紧急修复模板

```bash
# 1. 从 main 创建 hotfix
git worktree add ../feinn-agent-hotfix-xxx main
cd ../feinn-agent-hotfix-xxx
git checkout -b hotfix/xxx

# 2. 快速修复
# ...

# 3. 合并到 main
git checkout main
git merge --no-ff hotfix/xxx
git tag -a v0.x.x -m "Hotfix v0.x.x"

# 4. 合并到 dev
git checkout dev
git merge --no-ff hotfix/xxx

# 5. 清理
git worktree remove ../feinn-agent-hotfix-xxx
```

---

## 9. 附录

### 9.1 相关文档

- [DEVELOPMENT_WORKFLOW.md](../DEVELOPMENT_WORKFLOW.md) - 开发流程规范
- [docs/requirements.md](requirements.md) - 功能需求文档
- [docs/roadmap.md](roadmap.md) - 开发路线图
- [docs/feature-comparison.md](feature-comparison.md) - 功能对比分析

### 9.2 相关命令速查

```bash
# Git worktree
git worktree add ../feinn-agent-feature-xxx dev
git worktree list

# 测试
python -m pytest tests/ -v --tb=short
python -m pytest tests/test_xxx.py -v -k "test_name"

# 代码质量
python -m ruff check src/
python -m ruff format src/

# 类型检查
python -m mypy src/feinn_agent/
```

### 9.3 版本号规范 (SemVer)

| 版本类型 | 说明 | 示例 |
|---------|------|------|
| MAJOR | 不兼容的API变更 | 1.0.0 → 2.0.0 |
| MINOR | 向下兼容的功能添加 | 1.0.0 → 1.1.0 |
| PATCH | 向下兼容的问题修复 | 1.0.0 → 1.0.1 |

---

## 10. 审查清单

### 10.1 开发前检查

- [ ] 需求文档已更新
- [ ] 技术设计文档已完成
- [ ] 测试策略已确定
- [ ] 工作量已评估

### 10.2 开发中检查

- [ ] 遵循编码规范
- [ ] 包含类型注解
- [ ] 包含文档字符串
- [ ] 编写单元测试

### 10.3 开发后检查

- [ ] 所有测试通过
- [ ] 代码质量检查通过
- [ ] 文档已更新
- [ ] 无冲突可合并
- [ ] CHANGELOG 已更新

---

*本规范基于 FeinnAgent 项目实践总结，将持续迭代更新。*