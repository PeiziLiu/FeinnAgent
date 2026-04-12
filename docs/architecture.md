# FeinnAgent Architecture Design Document

## 1. Architecture Overview

### 1.1 Design Philosophy

FeinnAgent adopts a **layered architecture** and **modular design**, following these principles:

1. **Single Responsibility**: Each module is responsible for one clear functional domain
2. **Dependency Inversion**: High-level modules don't depend on low-level modules; both depend on abstractions
3. **Open/Closed Principle**: Open for extension, closed for modification
4. **Async-First**: All IO operations are asynchronous

### 1.2 Architecture Layers

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

### 1.3 Core Components

| Component | Responsibility | Key Technologies |
|-----------|---------------|------------------|
| Agent Engine | Conversation loop, tool dispatch | asyncio, Pydantic |
| Context Manager | Message management, state maintenance | Sliding window, LRU |
| Compaction Engine | Context compression, summary generation | LLM summarization, hierarchical strategy |
| Tool System | Tool registration, invocation, management | Decorators, plugin architecture |
| Memory System | Knowledge storage, semantic retrieval | SQLite, vector similarity |
| Task System | Task orchestration, dependency management | DAG, topological sorting |
| Subagent System | Sub-agent management, concurrency control | asyncio.Task, semaphore |

---

## 2. Detailed Architecture

### 2.1 Agent Engine

The Agent is the core execution unit of the system, responsible for coordinating all subsystems.

```python
class Agent:
    """
    Agent Core Class
    
    Responsibilities:
    1. Manage conversation loop
    2. Coordinate tool calls
    3. Maintain context state
    4. Handle concurrent requests
    """
    
    # Core dependencies
    config: AgentConfig          # Configuration
    provider: Provider           # LLM provider
    context: ContextManager      # Context management
    tools: ToolRegistry          # Tool registry
    memory: MemoryManager        # Memory management
    task: TaskManager            # Task management
    subagent: SubagentManager    # Sub-agent management
    permission: PermissionManager # Permission management
```

**Conversation Loop Flow**:

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

### 2.2 Context Management

The Context Manager is responsible for maintaining conversation history and state.

```python
class ContextManager:
    """
    Context Manager
    
    Features:
    1. Message storage (system prompts, user messages, assistant messages, tool results)
    2. Length monitoring (real-time token counting)
    3. Compression trigger (trigger compression when threshold reached)
    4. State persistence (save to SQLite)
    """
    
    messages: List[Message]           # Message list
    system_prompt: str                # System prompt
    metadata: ContextMetadata         # Metadata
    
    # Core methods
    def add_message(self, msg: Message)    # Add message
    def get_messages(self) -> List[Message] # Get all messages
    def get_token_count(self) -> int        # Get token count
    def clear(self)                         # Clear context
```

**Message Type Hierarchy**:

```
Message (base class)
├── SystemMessage      # System prompt
├── UserMessage        # User input
├── AssistantMessage   # Assistant response
│   ├── content: str
│   ├── reasoning: Optional[str]
│   └── tool_calls: List[ToolCall]
└── ToolResultMessage  # Tool execution result
    ├── tool_call_id: str
    ├── content: str
    └── is_error: bool
```

### 2.3 Context Compaction Engine

When context approaches the LLM window limit, the compaction engine automatically performs compression.

```python
class CompactionEngine:
    """
    Context Compaction Engine
    
    Compression strategies (by priority):
    1. Summary compression - Generate summaries for early messages
    2. Selective dropping - Drop low-priority messages
    3. Truncation - Truncate overly long messages
    """
    
    strategies: List[CompactionStrategy]
    
    def compact(self, messages: List[Message], target_tokens: int) -> List[Message]:
        """Execute compression"""
        for strategy in self.strategies:
            if self.get_token_count(messages) <= target_tokens:
                break
            messages = strategy.apply(messages)
        return messages
```

**Compression Strategy Chain**:

```
Original messages [m1, m2, m3, m4, m5, m6, m7, m8]
                │
                ▼
        ┌───────────────┐
        │  Summary      │  m1,m2,m3 → summary1
        │  Strategy     │
        └───────────────┘
                │
                ▼
    [summary1, m4, m5, m6, m7, m8]
                │
                ▼
        ┌───────────────┐
        │  Drop         │  Drop m4 (tool result)
        │  Strategy     │
        └───────────────┘
                │
                ▼
    [summary1, m5, m6, m7, m8]
                │
                ▼
        ┌───────────────┐
        │  Truncate     │  Truncate long messages
        │  Strategy     │
        └───────────────┘
                │
                ▼
    Compressed messages [summary1', m5', m6', m7', m8']
```

### 2.4 Tool System

The Tool System adopts a **registry pattern**, supporting dynamic discovery and loading.

```python
class ToolRegistry:
    """
    Tool Registration Center
    
    Features:
    1. Tool registration (decorator pattern)
    2. Tool discovery (auto-scan)
    3. Tool invocation (unified interface)
    4. Permission checking (pre-invocation validation)
    """
    
    _tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register tool"""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool"""
        return self._tools.get(name)
    
    def get_schemas(self) -> List[Dict]:
        """Get all tool schemas"""
        return [tool.schema for tool in self._tools.values()]
    
    async def execute(self, name: str, args: Dict, context: ToolContext) -> str:
        """Execute tool"""
        tool = self.get_tool(name)
        return await tool.handler(args, context)
```

**Tool Categories**:

```
Tools
├── Builtins (8)
│   ├── Read/Write/Edit    # File operations
│   ├── Glob/Grep          # Code search
│   ├── Bash               # Command execution
│   ├── WebFetch           # Web access
│   └── AskUserQuestion    # User interaction
├── Memory (4)
│   ├── MemorySave
│   ├── MemorySearch
│   ├── MemoryList
│   └── MemoryDelete
├── Task (4)
│   ├── TaskCreate
│   ├── TaskGet
│   ├── TaskList
│   └── TaskUpdate
└── Subagent (4)
    ├── Agent
    ├── CheckAgentResult
    ├── ListAgentTasks
    └── ListAgentTypes
```

### 2.5 Memory System

The Memory System provides **dual-scope** knowledge management.

```python
class MemoryManager:
    """
    Memory Manager
    
    Scopes:
    - workspace: Project-level, shared across sessions
    - agent: Session-level, temporary storage
    """
    
    workspace_scope: MemoryScope
    agent_scope: MemoryScope
    
    def save(self, content: str, scope: Scope, metadata: Dict) -> str:
        """Save memory"""
        memory = Memory(content=content, metadata=metadata)
        return self._get_scope(scope).save(memory)
    
    def search(self, query: str, scope: Scope, limit: int = 5) -> List[Memory]:
        """Semantic search"""
        return self._get_scope(scope).search(query, limit)
```

**Memory Data Structure**:

```python
@dataclass
class Memory:
    id: str                    # UUID
    content: str               # Content
    scope: Scope               # Scope
    created_at: datetime       # Creation time
    updated_at: datetime       # Update time
    access_count: int          # Access count
    metadata: Dict             # Metadata
    embedding: Optional[List[float]]  # Vector embedding
```

### 2.6 Task System

The Task System implements dependency management based on **DAG (Directed Acyclic Graph)**.

```python
class TaskManager:
    """
    Task Manager
    
    Features:
    1. Task creation and configuration
    2. Dependency management (DAG)
    3. State tracking
    4. Concurrency control
    """
    
    tasks: Dict[str, Task]
    dag: DAG
    semaphore: asyncio.Semaphore
    
    async def create_task(self, config: TaskConfig) -> Task:
        """Create task"""
        task = Task(config)
        self.tasks[task.id] = task
        self.dag.add_node(task.id, dependencies=config.dependencies)
        return task
    
    async def execute_dag(self) -> None:
        """Execute DAG"""
        execution_order = self.dag.topological_sort()
        for batch in execution_order:  # Parallel batches
            await asyncio.gather(*[
                self._execute_task(task_id) for task_id in batch
            ])
```

**Task State Machine**:

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

### 2.7 Subagent System

The Subagent System supports **concurrent creation and monitoring** of multiple sub-agents.

```python
class SubagentManager:
    """
    Subagent Manager
    
    Features:
    1. Sub-agent creation (specify type)
    2. Concurrent execution control
    3. Result collection
    4. Lifecycle management
    """
    
    active_agents: Dict[str, Subagent]
    agent_types: Dict[str, AgentTypeConfig]
    
    async def create_agent(self, task: str, agent_type: str) -> Subagent:
        """Create sub-agent"""
        config = self.agent_types[agent_type]
        agent = Subagent(task=task, config=config)
        self.active_agents[agent.id] = agent
        asyncio.create_task(agent.run())  # Background execution
        return agent
    
    async def get_result(self, agent_id: str, timeout: float) -> str:
        """Get result (with timeout)"""
        agent = self.active_agents[agent_id]
        return await asyncio.wait_for(agent.result, timeout)
```

**Predefined Agent Types**:

| Type | Description | Specialized Tools | Model |
|------|-------------|-------------------|-------|
| analyzer | Code analysis | Code search, static analysis | gpt-4o |
| coder | Code generation | File operations, code editing | gpt-4o |
| reviewer | Code review | Code search, diff tools | claude-3-5 |
| tester | Test generation | Test framework, coverage | gpt-4o |
| doc | Documentation generation | File operations, format conversion | gpt-4o |

### 2.8 Permission System

The Permission System provides a **three-level control** mechanism.

```python
class PermissionManager:
    """
    Permission Manager
    
    Modes:
    - accept_all: Auto-accept all
    - auto: Smart judgment (destructive operations require confirmation)
    - confirm_all: All operations require confirmation
    """
    
    mode: PermissionMode
    
    async def check_permission(self, tool: Tool, args: Dict) -> PermissionResult:
        """Check permission"""
        if self.mode == PermissionMode.ACCEPT_ALL:
            return PermissionResult(allowed=True)
        
        if self.mode == PermissionMode.CONFIRM_ALL:
            return await self._request_confirmation(tool, args)
        
        # auto mode
        if tool.is_destructive:
            return await self._request_confirmation(tool, args)
        
        return PermissionResult(allowed=True)
```

**Tool Risk Levels**:

| Level | Tools | Description |
|-------|-------|-------------|
| read-only | Read, Glob, Grep, WebFetch | Read-only operations, auto-approved |
| concurrent-safe | Memory*, Task* | Thread-safe, auto-approved |
| destructive | Write, Edit, Bash | Destructive operations, require confirmation |

---

## 3. Data Flow

### 3.1 Request Processing Flow

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
     ├──▶ Context Manager (load history)
     │
     ├──▶ Compaction Engine (check compression)
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

### 3.2 Tool Invocation Flow

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

## 4. Extension Points

### 4.1 Adding New Providers

```python
class MyProvider(Provider):
    """Custom LLM Provider"""
    
    async def complete(self, messages: List[Message], tools: List[Dict]) -> Response:
        # Implement API call
        pass
    
    def count_tokens(self, text: str) -> int:
        # Implement token counting
        pass

# Register
ProviderRegistry.register("myprovider", MyProvider)
```

### 4.2 Adding New Tools

```python
from feinn_agent.tools import register_tool

@register_tool(
    name="my_tool",
    description="Tool description",
    parameters={...}
)
async def my_tool(arg1: str, context: ToolContext) -> str:
    return "result"
```

### 4.3 Adding New Agent Types

```python
# Define in configuration
config.agent_types["my_agent"] = AgentTypeConfig(
    name="my_agent",
    description="Custom agent",
    system_prompt="...",
    tools=["read", "write", "my_tool"],
    model="openai/gpt-4o"
)
```

---

## 5. Deployment Architecture

### 5.1 Single Node Deployment

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

### 5.2 Cluster Deployment

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

## 6. Performance Considerations

### 6.1 Concurrency Model

- Use `asyncio` for high concurrency
- Independent Task per session
- Thread pool for tool calls (blocking operations)

### 6.2 Caching Strategy

- System prompt caching
- Tool schema caching
- Memory vector caching

### 6.3 Database Optimization

- SQLite WAL mode
- Connection pooling
- Index optimization

---

## 7. Security Considerations

### 7.1 Input Validation

- Pydantic model validation
- Parameter type checking
- Range limiting

### 7.2 Command Sandbox

- Bash command whitelist
- File path restrictions
- Timeout control

### 7.3 Key Management

- Environment variable storage
- No persistence in memory
- Regular rotation

---

## 8. Appendix

### 8.1 Glossary

| Term | Definition |
|------|------------|
| DAG | Directed Acyclic Graph, used for task dependency management |
| SSE | Server-Sent Events, server push |
| MCP | Model Context Protocol |
| Scope | Memory scope (workspace/agent) |
| Compaction | Context compression |

### 8.2 Reference Documentation

- [FastAPI Architecture](https://fastapi.tiangolo.com/advanced/async-tests/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [asyncio Guide](https://docs.python.org/3/library/asyncio.html)
