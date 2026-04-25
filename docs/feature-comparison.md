# FeinnAgent 功能对比分析

## 1. 项目概述

| 项目 | 架构 | 语言 |
|------|------|------|
| opencode | Node.js/TypeScript | TypeScript |
| hermes-agent | Python | Python |
| cheetahclaws | Python | Python |
| feinn-agent | Python | Python |

## 2. 功能对比表

| 功能模块 | opencode | hermes-agent | cheetahclaws | feinn-agent |
|---------|---------|-------------|-------------|------------|
| **核心架构** | Node.js/TypeScript | Python | Python | Python |
| **Agent循环** | ✅ | ✅ | ✅ | ✅ |
| **工具系统** | ✅ | ✅ | ✅ | ✅ |
| **Browser工具** | ❌ | ✅ (browser_tool) | ❌ | ✅ (新增) |
| **Checkpoint** | ❌ | ✅ (checkpoint_manager) | ✅ | ✅ (新增) |
| **执行计划** | ❌ | ❌ | ❌ | ✅ (新增) |
| **轨迹记录** | ❌ | ✅ | ❌ | ✅ (新增) |
| **中断恢复** | ✅ | ❌ | ✅ | ✅ (新增) |
| **可视化UI** | ❌ | ✅ | ❌ | ✅ (新增) |
| **MCP支持** | ❌ | ✅ | ✅ | ✅ |
| **Skills** | ✅ | ✅ | ✅ | ✅ |
| **内存管理** | ✅ | ✅ | ✅ | ✅ |
| **权限控制** | ❌ | ✅ | ❌ | ✅ |
| **上下文压缩** | ❌ | ✅ | ✅ | ✅ (compaction) |
| **多Provider** | ❌ | ✅ | ✅ | ✅ |
| **Server/API** | ✅ | ✅ | ✅ | ✅ |

## 3. feinn-agent 新增特性

| 功能 | 说明 |
|------|------|
| 浏览器自动化 | 支持 local/Browserbase/BrowserUse/Firecrawl 多后端 |
| 执行计划系统 | 计划创建/编辑/执行/管理 |
| Checkpoint | Git-based快照/回滚机制 |
| 轨迹记录 | Turn记录/工具调用/Token统计 |
| 中断信号 | threading.Event实现的中断机制 |
| Kawaii UI | 表情符号风格的可视化输出 |
| Diff显示 | 文件变更对比展示 |
| 工具预览 | 执行前预览工具参数 |

## 4. 各项目模块结构

### 4.1 feinn-agent
```
feinn_agent/
├── agent.py           # Agent核心
├── cli.py             # CLI入口
├── server.py          # API服务
├── checkpoint/       # 快照管理
├── display/           # 可视化展示
├── interrupt/        # 中断信号
├── mcp/              # MCP支持
├── memory/           # 内存管理
├── permission/       # 权限控制
├── plan/             # 执行计划
├── skill/           # Skills系统
├── subagent/         # 子Agent
├── task/             # 任务管理
└── tools/            # 工具系统
```

### 4.2 hermes-agent
```
hermes-agent/
├── agent/            # Agent核心
├── tools/            # 工具系统(含browser_tool, checkpoint_manager)
├── mcp/              # MCP支持
├── constraints/      # 约束管理
└── acp_adapter/      # ACP适配器
```

### 4.3 cheetahclaws
```
cheetahclaws/
├── agent.py          # Agent核心
├── cheetahclaws.py  # 主入口
├── checkpoint/      # 快照管理
├── memory.py       # 内存管理
├── skills.py       # Skills
├── tools.py       # 工具系统
└── subagent.py   # 子Agent
```

### 4.4 opencode
```
packages/
├── app/            # 应用
├── console/        # 控制台
├── desktop/        # 桌面集成
├── enterprise/    # 企业功能
├── extensions/    # 扩展
├── opencode/      # 核心
├── plugin/       # 插件系统
├── sdk/          # SDK
└── web/          # Web界面
```

## 5. 浏览器功能对比

| 特性 | hermes-agent | feinn-agent |
|------|------------|-------------|
| 本地浏览器 | agent-browser | agent-browser |
| Camofox | ✅ | ❌ |
| Cloud (Browserbase) | ✅ | ✅ |
| Browser Use | ❌ | ✅ |
| Firecrawl | ✅ | ✅ |
| CDP连接 | ✅ | ❌ |
| SSRF��护 | ✅ | ✅ |
| 多provider | ❌ | ✅ (fallback自动选择) |

## 6. 测试覆盖对比

| 项目 | 测试文件数 | 功能模块测试 |
|------|-----------|-------------|
| feinn-agent | 20+ | ✅ 完整覆盖 |
| hermes-agent | 10+ | ✅ 基础覆盖 |
| cheetahclaws | 5+ | ⚠️ 基础覆盖 |

## 7. 结论

### feinn-agent 优势
1. **模块化设计** - 清晰的功能模块划分
2. **多浏览器后端** - 支持4种provider自动选择
3. **完整的执行系统** - 计划/Checkpoint/Trajectory/Interrupt
4. **友好的UI** - Kawaii风格可视化

### 与hermes-agent对比
- 功能对齐度: ~90%
- 创新功能: ~30% (执行计划/轨迹分析/可视化)
- 代码质量: 相当 (使用相同模式)

### 待完善功能
- Camofox集成
- CDP直接连接
- 更多权限控制