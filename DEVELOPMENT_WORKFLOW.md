# FeinnAgent 开发迭代规范

基于 hardness 编程理念的开发流程，确保代码质量、需求完整性和版本控制规范性。

---

## 核心理念

**Hardness Programming**: 像硬件开发一样严谨对待软件开发
- 明确的需求分析
- 严格的版本控制
- 完整的测试验证
- 可追溯的变更历史

---

## 开发前准备

### 1. 需求梳理

每次开发前必须明确回答：

```
□ 这是新增需求还是 roadmap 中的既有需求？
□ 需求的影响范围是什么？
□ 是否需要更新架构设计？
□ 测试策略是什么？
```

**如果是新增需求**：
1. 在 `docs/requirements.md` 中补充需求描述
2. 更新 `docs/roadmap.md` 中的优先级和排期
3. 创建需求追踪 Issue

**如果是 roadmap 需求**：
1. 在 roadmap 中标记为 "进行中"
2. 检查相关需求是否有变更
3. 确认依赖项是否已完成

### 2. 版本确认

```bash
# 1. 确保本地 dev 分支是最新的
git checkout dev
git pull origin dev

# 2. 基于最新版本创建 worktree
git worktree add ../feinn-agent-feature-xxx dev

# 3. 进入 worktree 目录
cd ../feinn-agent-feature-xxx
```

---

## Git Worktree 工作流

### 目录结构

```
~/work/
├── feinn-agent/              # 主仓库 (main/dev 分支)
├── feinn-agent-feature-xxx/  # 功能开发 worktree
├── feinn-agent-bugfix-yyy/   # Bug 修复 worktree
└── feinn-agent-hotfix-zzz/   # 热修复 worktree
```

### Worktree 管理命令

```bash
# 创建新的 worktree (基于 dev 分支)
git worktree add ../feinn-agent-feature-<name> dev

# 列出所有 worktree
git worktree list

# 清理已合并的 worktree
git worktree remove ../feinn-agent-feature-<name>

# 强制清理 (未提交更改会被删除)
git worktree remove -f ../feinn-agent-feature-<name>
```

---

## 开发流程

### Phase 1: 需求确认 (Must Have)

```markdown
## 需求检查清单

- [ ] 阅读相关需求文档 (docs/requirements.md)
- [ ] 确认需求类型 (新增 / roadmap / bugfix)
- [ ] 如果是新增需求，已更新 requirements.md 和 roadmap.md
- [ ] 理解需求的技术影响
- [ ] 预估开发工作量
- [ ] 确认测试策略
```

### Phase 2: 技术设计 (Should Have)

```markdown
## 设计检查清单

- [ ] 是否需要更新架构文档？
- [ ] 接口变更是否向后兼容？
- [ ] 数据库/schema 是否需要迁移？
- [ ] 性能影响评估
- [ ] 安全影响评估
```

### Phase 3: 编码实现

```bash
# 1. 创建功能分支
git checkout -b feature/xxx

# 2. 开发过程中保持提交规范
git commit -m "feat: 添加用户认证模块

- 实现 JWT token 生成和验证
- 添加登录/注册接口
- 集成权限检查中间件

Closes #123"
```

**提交规范** (Conventional Commits):
- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具相关

### Phase 4: 测试验证 (Must Have)

```bash
# 1. 本地测试
python3.11 -m pytest tests/ -v --tb=short

# 2. 代码质量检查
python3.11 -m ruff check src/
python3.11 -m ruff format src/ --check

# 3. 类型检查 (如有配置)
# python3.11 -m mypy src/feinn_agent/
```

**测试通过标准**:
- [ ] 核心测试用例 100% 通过
- [ ] 新增功能有对应的测试覆盖
- [ ] 代码覆盖率不降低
- [ ] 无 lint 错误

### Phase 5: 合并前检查

```markdown
## 合并检查清单

- [ ] 代码审查完成 (self-review 或 peer review)
- [ ] 所有测试通过
- [ ] 文档已更新 (README, API docs 等)
- [ ] CHANGELOG 已更新
- [ ] 无冲突可合并到 dev
```

```bash
# 1. 同步 dev 分支最新更改
git checkout dev
git pull origin dev
git checkout feature/xxx
git rebase dev

# 2. 解决冲突后强制推送
git push origin feature/xxx --force-with-lease

# 3. 创建 PR/MR 到 dev 分支
# 或使用命令行合并
git checkout dev
git merge --no-ff feature/xxx -m "Merge feature/xxx: 功能描述"
git push origin dev
```

---

## 分支策略

```
main (生产分支)
  ↑
dev (开发分支) ←── feature/xxx ── feature/yyy
  ↑
hotfix/zzz (紧急修复)
```

### 分支命名规范

- `feature/<描述>` - 新功能
- `bugfix/<描述>` - Bug 修复
- `hotfix/<描述>` - 紧急修复
- `docs/<描述>` - 文档更新
- `refactor/<描述>` - 重构

---

## 发布流程

### 版本号规范 (SemVer)

`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向下兼容的功能添加
- **PATCH**: 向下兼容的问题修复

### 发布检查清单

```markdown
- [ ] dev 分支稳定运行
- [ ] 所有测试通过
- [ ] 版本号已更新 (pyproject.toml)
- [ ] CHANGELOG 已更新
- [ ] 文档已更新
- [ ] 创建 Git tag
- [ ] 合并到 main 分支
```

```bash
# 1. 更新版本号
# 编辑 pyproject.toml

# 2. 创建发布分支
git checkout -b release/v0.2.0 dev

# 3. 版本修复 (如有必要)
# ...

# 4. 合并到 main
git checkout main
git merge --no-ff release/v0.2.0

# 5. 打标签
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin main --tags

# 6. 合并回 dev
git checkout dev
git merge main
```

---

## 快速参考

### 日常开发命令

```bash
# 开始新功能
git worktree add ../feinn-agent-feature-xxx dev
cd ../feinn-agent-feature-xxx
git checkout -b feature/xxx

# 开发中测试
python3.11 -m pytest tests/test_xxx.py -v

# 提交前检查
python3.11 -m pytest tests/ -v
python3.11 -m ruff check src/

# 合并到 dev
git checkout dev
git pull origin dev
git merge feature/xxx --no-ff
git push origin dev

# 清理 worktree
git worktree remove ../feinn-agent-feature-xxx
git branch -d feature/xxx
```

### 紧急修复流程

```bash
# 从 main 创建 hotfix
git worktree add ../feinn-agent-hotfix-xxx main
cd ../feinn-agent-hotfix-xxx
git checkout -b hotfix/xxx

# 修复 → 测试 → 提交

# 合并到 main 和 dev
git checkout main
git merge hotfix/xxx --no-ff
git tag -a v0.1.1 -m "Hotfix v0.1.1"

git checkout dev
git merge hotfix/xxx --no-ff
```

---

## 相关文档

- [需求文档](docs/requirements.md)
- [架构设计](docs/architecture.md)
- [技术设计](docs/technical.md)
- [开发路线图](docs/roadmap.md)
- [API 文档](docs/api.md)

---

## 工具推荐

- **Git**: worktree, rebase, cherry-pick
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Linting**: ruff, mypy
- **CI/CD**: GitHub Actions / GitLab CI
