# FeinnAgent 架构设计文档

## 1. 架构概述

### 1.1 设计哲学

FeinnAgent 采用**分层架构**与**模块化设计**，遵循以下原则：

1. **单一职责**: 每个模块只负责一个明确的功能领域
2. **依赖倒置**: 高层模块不依赖低层模块，都依赖抽象
3. **开闭原则**: 对扩展开放，对修改关闭
4. **异步优先**: 所有 IO 操作都采用异步方式

### 1.2 架构分层

```
┌─────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  CLI Module  │  │  API Server  │  │  WebSocket (Future)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                         Core Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │    Agent     │  │   Context    │  │     Compaction       │  │
│  │    Engine    │  │   Manager    │  │      Engine          │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Subsystem Layer                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │  Tools  │ │  Memory │ │  Tasks  │ │ Subagent│ │ Permission│ │
│  │  System │ │  System │ │  System │ │  System │ │   System  │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └───────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     Infrastructure Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Provider   │  │     MCP      │  │     Storage          │  │
│  │   Adapter    │  │   Client     │  │    (SQLite)          │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 核心组件

| 组件 | 职责 | 关键技术 |
|------|------|----------|
| Agent Engine | 对话循环、工具调度 | asyncio, Pydantic |
| Context Manager | 消息管理、状态维护 | 滑动窗口, LRU |
| Compaction Engine | 上下文压缩、摘要生成 | LLM 摘要, 分层策略 |
| Tool System | 工具注册、调用、管理 | 装饰器, 插件化 |
| Memory System | 知识存储、语义检索 | SQLite, 向量相似度 |
| Task System | 任务编排、依赖管理 | DAG, 拓扑排序 |
| Subagent System | 子代理管理、并发控制 | asyncio.Task, 信号量 |

---

## 2. 详细架构

### 2.1 Agent 引擎

Agent 是系统的核心执行单元，负责协调所有子系统。

```python
class Agent:
    """
    Agent 核心类
    
    职责：
    1. 管理对话循环
    2. 协调工具调用
    3. 维护上下文状态
    4. 处理并发请求
    """
    
    # 核心依赖
    config: AgentConfig          # 配置
    provider: Provider           # LLM 提供商
    context: ContextManager      # 上下文管理
    tools: ToolRegistry          # 工具注册表
    memory: MemoryManager        # 内存管理
    task: TaskManager            # 任务管理
    subagent: SubagentManager    # 子代理管理
    permission: PermissionManager # 权限管理
```

**对话循环流程**:

```
┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────┐
│  Start  │───▶│  Send to    │───▶│  Parse      │───▶│  Tool   │
│         │    │  LLM        │    │  Response   │    │  Call?  │
└─────────┘    └─────────────┘    └─────────────┘    └────┬────┘
     ▲                                                    │
     │                                                    │ No
     │                                                    ▼
     │                                             ┌─────────────┐
     │                                             │  Return     │
     │                                             │  Result     │
     │                                             └─────────────┘
     │ Yes
     │                                                    │
     │                                                    ▼
     │                                             ┌─────────────┐
     └─────────────────────────────────────────────│  Execute    │
                                                   │  Tool       │
                                                   └─────────────┘
```

### 2.2 上下文管理

上下文管理器负责维护对话历史和状态。

```python
class ContextManager:
    """
    上下文管理器
    
    功能：
    1. 消息存储（系统提示、用户消息、助手消息、工具结果）
    2. 长度监控（实时计算 token 数）
    3. 压缩触发（达到阈值时触发压缩）
    4. 状态持久化（保存到 SQLite）
    """
    
    messages: List[Message]           # 消息列表
    system_prompt: str                # 系统提示
    metadata: ContextMetadata         # 元数据
    
    # 核心方法
    def add_message(self, msg: Message)    # 添加消息
    def get_messages(self) -> List[Message] # 获取所有消息
    def get_token_count(self) -> int        # 获取 token 数
    def clear(self)                         # 清空上下文
```

**消息类型层次**:

```
Message (基类)
├── SystemMessage      # 系统提示
├── UserMessage        # 用户输入
├── AssistantMessage   # 助手回复
│   ├── content: str
│   ├── reasoning: Optional[str]
│   └── tool_calls: List[ToolCall]
└── ToolResultMessage  # 工具执行结果
    ├── tool_call_id: str
    ├── content: str
    └── is_error: bool
```

### 2.3 上下文压缩引擎

当上下文接近 LLM 的窗口限制时，压缩引擎自动执行压缩。

```python
class CompactionEngine:
    """
    上下文压缩引擎
    
    压缩策略（按优先级）：
    1. 摘要压缩 - 对早期消息生成摘要
    2. 选择性丢弃 - 丢弃低优先级消息
    3. 截断处理 - 截断超长消息
    """
    
    strategies: List[CompactionStrategy]
    
    def compact(self, messages: List[Message], target_tokens: int) -> List[Message]:
        """执行压缩"""
        for strategy in self.strategies:
            if self.get_token_count(messages) <= target_tokens:
                break
            messages = strategy.apply(messages)
        return messages
```

**压缩策略链**:

```
原始消息 [m1, m2, m3, m4, m5, m6, m7, m8]
                │
                ▼
        ┌───────────────┐
        │  摘要策略      │  m1,m2,m3 → summary1
        └───────────────┘
                │
                ▼
    [summary1, m4, m5, m6, m7, m8]
                │
                ▼
        ┌───────────────┐
        │  丢弃策略      │  丢弃 m4 (tool result)
        └───────────────┘
                │
                ▼
    [summary1, m5, m6, m7, m8]
                │
                ▼
        ┌───────────────┐
        │  截断策略      │  截断超长消息
        └───────────────┘
                │
                ▼
    压缩后消息 [summary1', m5', m6', m7', m8']
```

### 2.4 工具系统

工具系统采用**注册表模式**，支持动态发现和加载。

```python
class ToolRegistry:
    """
    工具注册中心
    
    功能：
    1. 工具注册（装饰器方式）
    2. 工具发现（自动扫描）
    3. 工具调用（统一接口）
    4. 权限检查（调用前验证）
    """
    
    _tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)
    
    def get_schemas(self) -> List[Dict]:
        """获取所有工具 schema"""
        return [tool.schema for tool in self._tools.values()]
    
    async def execute(self, name: str, args: Dict, context: ToolContext) -> str:
        """执行工具"""
        tool = self.get_tool(name)
        return await tool.handler(args, context)
```

**工具分类**:

```
Tools
├── Builtins (8个)
│   ├── Read/Write/Edit    # 文件操作
│   ├── Glob/Grep          # 代码搜索
│   ├── Bash               # 命令执行
│   ├── WebFetch           # Web 访问
│   └── AskUserQuestion    # 用户交互
├── Memory (4个)
│   ├── MemorySave
│   ├── MemorySearch
│   ├── MemoryList
│   └── MemoryDelete
├── Task (4个)
│   ├── TaskCreate
│   ├── TaskGet
│   ├── TaskList
│   └── TaskUpdate
└── Subagent (4个)
    ├── Agent
    ├── CheckAgentResult
    ├── ListAgentTasks
    └── ListAgentTypes
```

### 2.5 内存系统

内存系统提供**双作用域**知识管理。

```python
class MemoryManager:
    """
    内存管理器
    
    作用域：
    - workspace: 项目级，跨会话共享
    - agent: 会话级，临时存储
    """
    
    workspace_scope: MemoryScope
    agent_scope: MemoryScope
    
    def save(self, content: str, scope: Scope, metadata: Dict) -> str:
        """保存记忆"""
        memory = Memory(content=content, metadata=metadata)
        return self._get_scope(scope).save(memory)
    
    def search(self, query: str, scope: Scope, limit: int = 5) -> List[Memory]:
        """语义搜索"""
        return self._get_scope(scope).search(query, limit)
```

**内存数据结构**:

```python
@dataclass
class Memory:
    id: str                    # UUID
    content: str               # 内容
    scope: Scope               # 作用域
    created_at: datetime       # 创建时间
    updated_at: datetime       # 更新时间
    access_count: int          # 访问次数
    metadata: Dict             # 元数据
    embedding: Optional[List[float]]  # 向量嵌入
```

### 2.6 任务系统

任务系统基于 **DAG（有向无环图）** 实现依赖管理。

```python
class TaskManager:
    """
    任务管理器
    
    功能：
    1. 任务创建与配置
    2. 依赖管理（DAG）
    3. 状态追踪
    4. 并发控制
    """
    
    tasks: Dict[str, Task]
    dag: DAG
    semaphore: asyncio.Semaphore
    
    async def create_task(self, config: TaskConfig) -> Task:
        """创建任务"""
        task = Task(config)
        self.tasks[task.id] = task
        self.dag.add_node(task.id, dependencies=config.dependencies)
        return task
    
    async def execute_dag(self) -> None:
        """执行 DAG"""
        execution_order = self.dag.topological_sort()
        for batch in execution_order:  # 并行批次
            await asyncio.gather(*[
                self._execute_task(task_id) for task_id in batch
            ])
```

**任务状态机**:

```
                    ┌─────────────┐
         ┌─────────│   pending   │◀────────┐
         │         └─────────────┘         │
         │                │                │
         │                │ start          │ retry
         │                ▼                │
    cancel │         ┌─────────────┐       │
         │         │   running   │───────┘
         │         └─────────────┘
         │           │      │
         │     fail  │      │ complete
         │           ▼      ▼
         │    ┌─────────┐ ┌───────────┐
         └───▶│  failed │ │ completed │
                └─────────┘ └───────────┘
```

### 2.7 子代理系统

子代理系统支持**并发创建和监控**多个子代理。

```python
class SubagentManager:
    """
    子代理管理器
    
    功能：
    1. 子代理创建（指定类型）
    2. 并发执行控制
    3. 结果收集
    4. 生命周期管理
    """
    
    active_agents: Dict[str, Subagent]
    agent_types: Dict[str, AgentTypeConfig]
    
    async def create_agent(self, task: str, agent_type: str) -> Subagent:
        """创建子代理"""
        config = self.agent_types[agent_type]
        agent = Subagent(task=task, config=config)
        self.active_agents[agent.id] = agent
        asyncio.create_task(agent.run())  # 后台执行
        return agent
    
    async def get_result(self, agent_id: str, timeout: float) -> str:
        """获取结果（带超时）"""
        agent = self.active_agents[agent_id]
        return await asyncio.wait_for(agent.result, timeout)
```

**预定义代理类型**:

| 类型 | 描述 | 专用工具 | 模型 |
|------|------|----------|------|
| analyzer | 代码分析 | 代码搜索、静态分析 | gpt-4o |
| coder | 代码生成 | 文件操作、代码编辑 | gpt-4o |
| reviewer | 代码审查 | 代码搜索、对比工具 | claude-3-5 |
| tester | 测试生成 | 测试框架、覆盖率 | gpt-4o |
| doc | 文档生成 | 文件操作、格式转换 | gpt-4o |

### 2.8 权限系统

权限系统提供**三级控制**机制。

```python
class PermissionManager:
    """
    权限管理器
    
    模式：
    - accept_all: 自动接受所有
    - auto: 智能判断（破坏性操作需确认）
    - confirm_all: 所有操作需确认
    """
    
    mode: PermissionMode
    
    async def check_permission(self, tool: Tool, args: Dict) -> PermissionResult:
        """检查权限"""
        if self.mode == PermissionMode.ACCEPT_ALL:
            return PermissionResult(allowed=True)
        
        if self.mode == PermissionMode.CONFIRM_ALL:
            return await self._request_confirmation(tool, args)
        
        # auto 模式
        if tool.is_destructive:
            return await self._request_confirmation(tool, args)
        
        return PermissionResult(allowed=True)
```

**工具风险分级**:

| 级别 | 工具 | 说明 |
|------|------|------|
| read-only | Read, Glob, Grep, WebFetch | 只读操作，自动通过 |
| concurrent-safe | Memory*, Task* | 线程安全，自动通过 |
| destructive | Write, Edit, Bash | 破坏性操作，需确认 |

---

## 3. 数据流

### 3.1 请求处理流程

```
User Request
     │
     ▼
┌─────────────┐
│  API/CLI    │
│  Interface  │
└─────────────┘
     │
     ▼
┌─────────────┐
│   Agent     │
│   Engine    │
└─────────────┘
     │
     ├──▶ Context Manager (加载历史)
     │
     ├──▶ Compaction Engine (检查压缩)
     │
     ▼
┌─────────────┐
│   Provider  │
│   (LLM API) │
└─────────────┘
     │
     ▼
┌─────────────┐
│   Parse     │
│   Response  │
└─────────────┘
     │
     ├──▶ Text Response ─────────▶ Return to User
     │
     └──▶ Tool Call
            │
            ├──▶ Permission Check
            │
            ├──▶ Tool Execution
            │
            ├──▶ Result Storage
            │
            └──▶ Loop Back to Provider
```

### 3.2 工具调用流程

```
Tool Call Request
        │
        ▼
┌───────────────┐
│  ToolRegistry │
│  .execute()   │
└───────────────┘
        │
        ├──▶ PermissionManager.check()
        │          │
        │          ├──▶ Denied ───▶ Error
        │          │
        │          └──▶ Allowed
        │
        ▼
┌───────────────┐
│  Tool Handler │
└───────────────┘
        │
        ├──▶ File Tools ───▶ File System
        │
        ├──▶ Web Tools ────▶ HTTP Client
        │
        ├──▶ Memory Tools ─▶ SQLite
        │
        ├──▶ Task Tools ───▶ TaskManager
        │
        └──▶ Subagent ─────▶ SubagentManager
```

---

## 4. 扩展点

### 4.1 添加新提供商

```python
class MyProvider(Provider):
    """自定义 LLM 提供商"""
    
    async def complete(self, messages: List[Message], tools: List[Dict]) -> Response:
        # 实现 API 调用
        pass
    
    def count_tokens(self, text: str) -> int:
        # 实现 token 计算
        pass

# 注册
ProviderRegistry.register("myprovider", MyProvider)
```

### 4.2 添加新工具

```python
from feinn_agent.tools import register_tool

@register_tool(
    name="my_tool",
    description="工具描述",
    parameters={...}
)
async def my_tool(arg1: str, context: ToolContext) -> str:
    return "result"
```

### 4.3 添加新代理类型

```python
# 在配置中定义
config.agent_types["my_agent"] = AgentTypeConfig(
    name="my_agent",
    description="自定义代理",
    system_prompt="...",
    tools=["read", "write", "my_tool"],
    model="openai/gpt-4o"
)
```

---

## 5. 部署架构

### 5.1 单机部署

```
┌─────────────────────────────────────┐
│           Single Node               │
│  ┌─────────────────────────────┐   │
│  │      FeinnAgent Server      │   │
│  │  ┌─────┐ ┌─────┐ ┌─────┐   │   │
│  │  │ API │ │ CLI │ │ SSE │   │   │
│  │  └──┬──┘ └──┬──┘ └──┬──┘   │   │
│  │     └───────┼───────┘      │   │
│  │             ▼              │   │
│  │      ┌──────────┐          │   │
│  │      │  Engine  │          │   │
│  │      └────┬─────┘          │   │
│  │           ▼                │   │
│  │      ┌──────────┐          │   │
│  │      │ SQLite   │          │   │
│  │      └──────────┘          │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

### 5.2 集群部署

```
┌─────────────────────────────────────────┐
│              Load Balancer              │
│            (Nginx/Traefik)              │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌───────┐    ┌───────┐    ┌───────┐
│Node 1 │    │Node 2 │    │Node 3 │
│Agent  │    │Agent  │    │Agent  │
└───┬───┘    └───┬───┘    └───┬───┘
    │            │            │
    └────────────┼────────────┘
                 ▼
        ┌────────────────┐
        │  Shared Store  │
        │  (PostgreSQL)  │
        └────────────────┘
```

---

## 6. 性能考虑

### 6.1 并发模型

- 使用 `asyncio` 实现高并发
- 每个会话独立 Task
- 工具调用使用线程池（阻塞操作）

### 6.2 缓存策略

- 系统提示缓存
- 工具 schema 缓存
- 内存向量缓存

### 6.3 数据库优化

- SQLite WAL 模式
- 连接池
- 索引优化

---

## 7. 安全考虑

### 7.1 输入验证

- Pydantic 模型校验
- 参数类型检查
- 范围限制

### 7.2 命令沙箱

- Bash 命令白名单
- 文件路径限制
- 超时控制

### 7.3 密钥管理

- 环境变量存储
- 内存中不持久化
- 定期轮换

---

## 8. 附录

### 8.1 术语表

| 术语 | 定义 |
|------|------|
| DAG | 有向无环图，用于任务依赖管理 |
| SSE | Server-Sent Events，服务器推送 |
| MCP | Model Context Protocol |
| Scope | 内存作用域（workspace/agent） |
| Compaction | 上下文压缩 |

### 8.2 参考文档

- [FastAPI 架构](https://fastapi.tiangolo.com/advanced/async-tests/)
- [Pydantic 文档](https://docs.pydantic.dev/)
- [asyncio 指南](https://docs.python.org/3/library/asyncio.html)
