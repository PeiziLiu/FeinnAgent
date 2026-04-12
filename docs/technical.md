# FeinnAgent Detailed Technical Design Document

## 1. Technology Stack

### 1.1 Core Dependencies

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10+ | Runtime |
| asyncio | Built-in | Async concurrency |
| Pydantic | 2.0+ | Data validation |
| FastAPI | 0.115+ | API framework |
| uvicorn | 0.32+ | ASGI server |
| aiohttp | 3.10+ | HTTP client |
| SQLAlchemy | 2.0+ | ORM |
| aiosqlite | 0.20+ | Async SQLite |
| Click | 8.0+ | CLI framework |
| Rich | 13.0+ | Terminal UI |
| tiktoken | 0.8+ | Token counting |
| tenacity | 9.0+ | Retry mechanism |

### 1.2 Development Dependencies

| Component | Version | Purpose |
|-----------|---------|---------|
| pytest | 8.0+ | Testing framework |
| pytest-asyncio | 0.24+ | Async testing |
| pytest-cov | 6.0+ | Coverage |
| ruff | 0.8+ | Linting |
| mypy | 1.13+ | Type checking |
| pre-commit | 4.0+ | Git hooks |

---

## 2. Core Module Implementation

### 2.1 Type System (types.py)

```python
"""
Core type definitions

All data models use Pydantic v2, providing:
1. Runtime type validation
2. JSON serialization
3. Documentation generation
"""

from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import uuid4


class MessageRole(str, Enum):
    """Message role enumeration"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """Tool call definition"""
    model_config = ConfigDict(frozen=True)
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(description="Tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Call arguments")


class Message(BaseModel):
    """Base message model"""
    model_config = ConfigDict(frozen=True)
    
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    reasoning: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentConfig(BaseModel):
    """Agent configuration"""
    model: str = Field(default="openai/gpt-4o", description="Model identifier")
    api_key: Optional[str] = Field(default=None, description="API key")
    base_url: Optional[str] = Field(default=None, description="Custom API URL")
    max_iterations: int = Field(default=50, ge=1, le=200)
    context_window: int = Field(default=128000, ge=1000)
    temperature: float = Field(default=0.7, ge=0, le=2)
    permission_mode: Literal["accept_all", "auto", "confirm_all"] = "accept_all"
    compact_threshold: float = Field(default=0.8, ge=0.5, le=0.95)
    
    # Concurrency control
    max_concurrent_tasks: int = Field(default=5, ge=1, le=20)
    max_concurrent_subagents: int = Field(default=3, ge=1, le=10)
    
    # Timeout configuration
    tool_timeout: float = Field(default=60.0, ge=1.0)
    subagent_timeout: float = Field(default=300.0, ge=10.0)


class ToolContext(BaseModel):
    """Tool execution context"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    agent_id: str
    session_id: str
    workspace_dir: str
    readonly: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 2.2 Configuration Management (config.py)

```python
"""
Configuration management system

Supports multiple configuration sources (priority from high to low):
1. Direct code injection
2. Environment variables
3. Configuration files
4. Default values
"""

import os
import yaml
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # LLM configuration
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    default_model: str = "openai/gpt-4o"
    
    # Application configuration
    log_level: str = "INFO"
    database_url: str = "sqlite:///./feinn.db"
    workspace_dir: str = "."
    
    # Permission configuration
    default_permission: str = "accept_all"  # accept_all, auto, confirm_all
    
    # Concurrency configuration
    max_concurrent_tasks: int = 5
    max_concurrent_subagents: int = 3
    
    # MCP configuration
    mcp_servers: dict = {}
    
    class Config:
        env_prefix = "FEINN_"
        env_file = ".env"
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        """Load configuration from YAML file"""
        if not path.exists():
            return cls()
        
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        return cls(**data)
    
    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)


def load_config(config_path: Optional[Path] = None) -> Settings:
    """Load configuration"""
    # 1. Load from file
    if config_path is None:
        config_path = Path.home() / ".feinn" / "config.yaml"
    
    settings = Settings.from_yaml(config_path)
    
    # 2. Environment variables auto-override (Pydantic Settings feature)
    
    return settings
```

### 2.3 Provider Adapter (providers.py)

```python
"""
LLM provider adapter

Unified interface supporting multiple LLM providers:
- OpenAI
- Anthropic
- Azure OpenAI
- vLLM
- Local models
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any, Optional
import aiohttp
import tiktoken


class Provider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None
    ) -> AsyncIterator[Message]:
        """Send completion request and return streaming response"""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Calculate token count"""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        pass


class OpenAIProvider(Provider):
    """OpenAI API provider"""
    
    BASE_URL = "https://api.openai.com/v1"
    
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None
    ) -> AsyncIterator[Message]:
        url = f"{self.config.base_url or self.BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.config.model,
            "messages": [m.model_dump() for m in messages],
            "temperature": self.config.temperature,
            "stream": True
        }
        
        if tools:
            payload["tools"] = tools
        
        async with self.session.post(url, headers=headers, json=payload) as resp:
            async for line in resp.content:
                if line.startswith(b"data: "):
                    data = line[6:].decode("utf-8").strip()
                    if data == "[DONE]":
                        break
                    # Parse and yield message
                    yield self._parse_chunk(data)
    
    def count_tokens(self, text: str) -> int:
        try:
            encoding = tiktoken.encoding_for_model(self.config.model)
            return len(encoding.encode(text))
        except:
            # Fallback: approximate with character count / 3
            return len(text) // 3
    
    def _parse_chunk(self, data: str) -> Message:
        """Parse SSE chunk"""
        import json
        chunk = json.loads(data)
        delta = chunk["choices"][0]["delta"]
        
        return Message(
            role=MessageRole.ASSISTANT,
            content=delta.get("content", ""),
            tool_calls=self._parse_tool_calls(delta.get("tool_calls"))
        )


class AnthropicProvider(Provider):
    """Anthropic Claude API provider"""
    
    BASE_URL = "https://api.anthropic.com/v1"
    
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None
    ) -> AsyncIterator[Message]:
        url = f"{self.config.base_url or self.BASE_URL}/messages"
        headers = {
            "x-api-key": self.config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # Convert messages to Anthropic format
        anthropic_messages = self._convert_messages(messages)
        
        payload = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "temperature": self.config.temperature,
            "max_tokens": 4096,
            "stream": True
        }
        
        if tools:
            payload["tools"] = tools
        
        async with self.session.post(url, headers=headers, json=payload) as resp:
            async for line in resp.content:
                if line.startswith(b"data: "):
                    data = line[6:].decode("utf-8").strip()
                    if data == "[DONE]":
                        break
                    yield self._parse_chunk(data)
    
    def count_tokens(self, text: str) -> int:
        # Claude uses different tokenizer
        # Approximate: character count / 3.5
        return int(len(text) / 3.5)
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict]:
        """Convert to Anthropic message format"""
        result = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # System message handled separately in Anthropic
                continue
            result.append({
                "role": msg.role.value,
                "content": msg.content
            })
        return result


class ProviderRegistry:
    """Provider registry"""
    
    _providers: Dict[str, type[Provider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        # Add more providers...
    }
    
    @classmethod
    def get_provider(cls, model: str, config: AgentConfig) -> Provider:
        """Get provider instance by model identifier"""
        provider_name = model.split("/")[0]
        provider_class = cls._providers.get(provider_name)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")
        return provider_class(config)
    
    @classmethod
    def register(cls, name: str, provider_class: type[Provider]):
        """Register new provider"""
        cls._providers[name] = provider_class
```

### 2.4 Context Management (context.py)

```python
"""
Context management system

Manages conversation history, state, and compression.
"""

from typing import List, Optional
from dataclasses import dataclass, field
import sqlite3
import json


@dataclass
class ContextWindow:
    """Context window"""
    messages: List[Message] = field(default_factory=list)
    system_prompt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, message: Message) -> None:
        """Add message"""
        self.messages.append(message)
    
    def get_messages(self) -> List[Message]:
        """Get all messages"""
        return self.messages.copy()
    
    def get_token_count(self, provider: Provider) -> int:
        """Calculate total token count"""
        total = 0
        for msg in self.messages:
            total += provider.count_tokens(msg.content)
        return total
    
    def clear(self) -> None:
        """Clear context"""
        self.messages.clear()


class ContextManager:
    """Context manager"""
    
    def __init__(self, config: AgentConfig, provider: Provider):
        self.config = config
        self.provider = provider
        self.window = ContextWindow()
        self.compaction_engine = CompactionEngine(config)
    
    async def add_message(self, message: Message) -> None:
        """Add message and check if compression needed"""
        self.window.add_message(message)
        
        # Check if compression needed
        token_count = self.window.get_token_count(self.provider)
        threshold = int(self.config.context_window * self.config.compact_threshold)
        
        if token_count > threshold:
            await self._compact_context()
    
    async def _compact_context(self) -> None:
        """Execute context compression"""
        self.window.messages = await self.compaction_engine.compact(
            self.window.messages,
            target_tokens=int(self.config.context_window * 0.6)
        )
    
    def get_messages_for_llm(self) -> List[Dict]:
        """Get messages in LLM API format"""
        result = []
        if self.window.system_prompt:
            result.append({
                "role": "system",
                "content": self.window.system_prompt
            })
        for msg in self.window.messages:
            result.append({
                "role": msg.role.value,
                "content": msg.content,
                **({"tool_calls": msg.tool_calls} if msg.tool_calls else {}),
                **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {})
            })
        return result
```

### 2.5 Tool System (tools.py)

```python
"""
Tool system

Dynamic tool registration and execution.
"""

from typing import Callable, Dict, Any, Optional
from functools import wraps
import inspect
import json


class Tool:
    """Tool definition"""
    
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        is_destructive: bool = False
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.is_destructive = is_destructive
    
    @property
    def schema(self) -> Dict[str, Any]:
        """Get OpenAI-compatible tool schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> str:
        """Execute tool"""
        # Check if handler is async
        if inspect.iscoroutinefunction(self.handler):
            result = await self.handler(**arguments, context=context)
        else:
            result = self.handler(**arguments, context=context)
        
        # Convert result to string
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False)
        return str(result)


class ToolRegistry:
    """Tool registry"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(
        self,
        name: str,
        description: str,
        parameters: Optional[Dict] = None,
        is_destructive: bool = False
    ) -> Callable:
        """Tool registration decorator"""
        def decorator(func: Callable) -> Callable:
            tool = Tool(
                name=name,
                description=description,
                parameters=parameters or self._infer_parameters(func),
                handler=func,
                is_destructive=is_destructive
            )
            self._tools[name] = tool
            return func
        return decorator
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool"""
        return self._tools.get(name)
    
    def get_all_schemas(self) -> List[Dict]:
        """Get all tool schemas"""
        return [tool.schema for tool in self._tools.values()]
    
    def _infer_parameters(self, func: Callable) -> Dict[str, Any]:
        """Infer parameters from function signature"""
        sig = inspect.signature(func)
        properties = {}
        required = []
        
        for name, param in sig.parameters.items():
            if name == "context":  # Skip context parameter
                continue
            
            param_type = param.annotation
            if param_type == str:
                properties[name] = {"type": "string"}
            elif param_type == int:
                properties[name] = {"type": "integer"}
            elif param_type == bool:
                properties[name] = {"type": "boolean"}
            else:
                properties[name] = {"type": "string"}
            
            if param.default == inspect.Parameter.empty:
                required.append(name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }


# Global registry instance
registry = ToolRegistry()


# Example tool definitions
@registry.register(
    name="Read",
    description="Read file content",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "File path"},
            "limit": {"type": "integer", "description": "Max lines to read"}
        },
        "required": ["file_path"]
    }
)
async def read_file(file_path: str, limit: int = 100, context: ToolContext = None) -> str:
    """Read file"""
    from pathlib import Path
    path = Path(file_path)
    if not path.exists():
        return f"Error: File {file_path} does not exist"
    
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")[:limit]
    return "\n".join(lines)


@registry.register(
    name="Bash",
    description="Execute bash command",
    is_destructive=True
)
async def bash_command(command: str, context: ToolContext = None) -> str:
    """Execute bash command"""
    import asyncio
    
    # Security check
    dangerous_commands = ["rm -rf /", ":(){ :|:& };:"]
    for dangerous in dangerous_commands:
        if dangerous in command:
            return f"Error: Dangerous command detected: {dangerous}"
    
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=context.workspace_dir if context else None
    )
    
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        return f"Error (exit {proc.returncode}): {stderr.decode()}"
    
    return stdout.decode()[:10000]  # Limit output
```

### 2.6 Agent Core (agent.py)

```python
"""
Agent core implementation

Main execution engine coordinating all components.
"""

from typing import AsyncIterator, Optional, List, Dict, Any
import asyncio


class Agent:
    """Agent core class"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.provider = ProviderRegistry.get_provider(config.model, config)
        self.context = ContextManager(config, self.provider)
        self.tool_registry = registry
        self.permission_manager = PermissionManager(config.permission_mode)
        self.iteration_count = 0
    
    async def run(
        self,
        user_input: str,
        conversation_id: Optional[str] = None
    ) -> AsyncIterator[Message]:
        """
        Main execution entry
        
        Yields:
            Message objects (assistant responses, tool results)
        """
        # Add user message
        user_message = Message(role=MessageRole.USER, content=user_input)
        await self.context.add_message(user_message)
        
        while self.iteration_count < self.config.max_iterations:
            self.iteration_count += 1
            
            # Call LLM
            async for message in self._call_llm():
                if message.tool_calls:
                    # Handle tool calls
                    for tool_call in message.tool_calls:
                        result = await self._execute_tool(tool_call)
                        yield Message(
                            role=MessageRole.TOOL,
                            content=result,
                            tool_call_id=tool_call.id
                        )
                else:
                    yield message
            
            # Check if conversation should end
            if not message.tool_calls:
                break
        
        if self.iteration_count >= self.config.max_iterations:
            yield Message(
                role=MessageRole.ASSISTANT,
                content="Reached maximum iteration limit"
            )
    
    async def _call_llm(self) -> AsyncIterator[Message]:
        """Call LLM and stream response"""
        messages = self.context.get_messages_for_llm()
        tools = self.tool_registry.get_all_schemas()
        
        async with self.provider:
            async for message in self.provider.complete(messages, tools):
                await self.context.add_message(message)
                yield message
    
    async def _execute_tool(self, tool_call: ToolCall) -> str:
        """Execute tool call"""
        tool = self.tool_registry.get_tool(tool_call.name)
        if not tool:
            return f"Error: Tool {tool_call.name} not found"
        
        # Permission check
        context = ToolContext(
            agent_id="agent_1",
            session_id="session_1",
            workspace_dir=self.config.workspace_dir
        )
        
        permission = await self.permission_manager.check(tool, tool_call.arguments)
        if not permission.allowed:
            return f"Error: Permission denied - {permission.reason}"
        
        # Execute tool
        try:
            result = await asyncio.wait_for(
                tool.execute(tool_call.arguments, context),
                timeout=self.config.tool_timeout
            )
            return result
        except asyncio.TimeoutError:
            return f"Error: Tool execution timeout ({self.config.tool_timeout}s)"
        except Exception as e:
            return f"Error: {str(e)}"
```

---

## 3. Database Design

### 3.1 Schema

```sql
-- Conversations table
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config JSON,
    metadata JSON
);

-- Messages table
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls JSON,
    tool_call_id TEXT,
    reasoning TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Memories table
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,  -- 'workspace' or 'agent'
    content TEXT NOT NULL,
    embedding BLOB,  -- Vector embedding
    metadata JSON,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks table
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES tasks(id),
    status TEXT NOT NULL,  -- pending, running, completed, failed
    priority INTEGER DEFAULT 0,
    config JSON,
    result JSON,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Task dependencies table
CREATE TABLE task_dependencies (
    task_id TEXT REFERENCES tasks(id),
    depends_on TEXT REFERENCES tasks(id),
    PRIMARY KEY (task_id, depends_on)
);

-- Audit log table
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level TEXT NOT NULL,
    agent_id TEXT,
    session_id TEXT,
    action TEXT NOT NULL,
    details JSON
);
```

---

## 4. API Design

### 4.1 REST API Endpoints

```python
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import StreamingResponse

app = FastAPI(title="FeinnAgent API")


@app.post("/conversations")
async def create_conversation(config: AgentConfig):
    """Create new conversation"""
    conversation_id = str(uuid4())
    # Save to database
    return {"id": conversation_id, "config": config}


@app.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, content: str):
    """Send message and get streaming response"""
    agent = await get_agent(conversation_id)
    
    async def generate():
        async for message in agent.run(content):
            yield f"data: {message.model_dump_json()}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


@app.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, limit: int = 100):
    """Get conversation history"""
    messages = await load_messages(conversation_id, limit)
    return {"messages": messages}


@app.post("/tasks")
async def create_task(config: TaskConfig):
    """Create task"""
    task = await task_manager.create_task(config)
    return {"id": task.id, "status": task.status}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task status"""
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    """WebSocket for real-time communication"""
    await websocket.accept()
    agent = await get_agent(conversation_id)
    
    try:
        while True:
            message = await websocket.receive_text()
            async for response in agent.run(message):
                await websocket.send_json(response.model_dump())
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
```

---

## 5. Testing Strategy

### 5.1 Unit Tests

```python
import pytest
from unittest.mock import Mock, AsyncMock


@pytest.mark.asyncio
async def test_agent_run():
    """Test agent execution"""
    config = AgentConfig(model="openai/gpt-4o")
    agent = Agent(config)
    
    # Mock provider
    agent.provider = AsyncMock()
    agent.provider.complete.return_value = [
        Message(role=MessageRole.ASSISTANT, content="Hello!")
    ]
    
    messages = []
    async for msg in agent.run("Hi"):
        messages.append(msg)
    
    assert len(messages) > 0
    assert messages[0].role == MessageRole.ASSISTANT


@pytest.mark.asyncio
async def test_tool_execution():
    """Test tool execution"""
    tool = registry.get_tool("Read")
    context = ToolContext(
        agent_id="test",
        session_id="test",
        workspace_dir="/tmp"
    )
    
    result = await tool.execute(
        {"file_path": "/tmp/test.txt"},
        context
    )
    
    assert isinstance(result, str)
```

### 5.2 Integration Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_conversation():
    """Test complete conversation flow"""
    config = AgentConfig(
        model="openai/gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    agent = Agent(config)
    
    # Multi-turn conversation
    responses = []
    async for msg in agent.run("What is Python?"):
        responses.append(msg)
    
    assert any("programming" in msg.content.lower() for msg in responses)
```

---

## 6. Deployment

### 6.1 Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY src/ ./src/
COPY pyproject.toml .

# Install package
RUN pip install -e .

# Expose port
EXPOSE 8000

# Run
CMD ["feinn", "--serve", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.2 Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: feinn-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: feinn-agent
  template:
    metadata:
      labels:
        app: feinn-agent
    spec:
      containers:
      - name: feinn
        image: feinn-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: openai
        - name: DATABASE_URL
          value: "postgresql://user:pass@db/feinn"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
---
apiVersion: v1
kind: Service
metadata:
  name: feinn-service
spec:
  selector:
    app: feinn-agent
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## 7. Monitoring

### 7.1 Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
request_count = Counter('feinn_requests_total', 'Total requests')
request_duration = Histogram('feinn_request_duration_seconds', 'Request duration')

# Token metrics
token_count = Counter('feinn_tokens_total', 'Total tokens', ['type'])

# Active sessions
active_sessions = Gauge('feinn_active_sessions', 'Active sessions')

# Tool execution
tool_executions = Counter('feinn_tool_executions_total', 'Tool executions', ['tool'])
```

### 7.2 Logging

```python
import logging
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
```

---

## 8. Appendix

### 8.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FEINN_LOG_LEVEL` | Log level | INFO |
| `FEINN_DATABASE_URL` | Database URL | sqlite:///./feinn.db |
| `FEINN_WORKSPACE_DIR` | Workspace directory | . |
| `FEINN_DEFAULT_MODEL` | Default model | openai/gpt-4o |
| `FEINN_MAX_CONCURRENT_TASKS` | Max concurrent tasks | 5 |
| `FEINN_MCP_SERVERS` | MCP server config | {} |

### 8.2 File Structure

```
feinn-agent/
├── src/feinn_agent/
│   ├── __init__.py
│   ├── agent.py          # Core agent
│   ├── types.py          # Type definitions
│   ├── config.py         # Configuration
│   ├── providers.py      # LLM providers
│   ├── context.py        # Context management
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py   # Tool registry
│   │   ├── builtins.py   # Built-in tools
│   │   └── mcp.py        # MCP client
│   ├── memory/
│   │   ├── __init__.py
│   │   └── store.py      # Memory storage
│   ├── task/
│   │   ├── __init__.py
│   │   └── manager.py    # Task management
│   └── server.py         # API server
├── tests/
├── docs/
├── pyproject.toml
└── README.md
```
