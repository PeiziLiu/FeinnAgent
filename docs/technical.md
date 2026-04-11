# FeinnAgent 详细技术设计文档

## 1. 技术栈

### 1.1 核心依赖

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 运行时 |
| asyncio | 内置 | 异步并发 |
| Pydantic | 2.0+ | 数据验证 |
| FastAPI | 0.115+ | API 框架 |
| uvicorn | 0.32+ | ASGI 服务器 |
| aiohttp | 3.10+ | HTTP 客户端 |
| SQLAlchemy | 2.0+ | ORM |
| aiosqlite | 0.20+ | 异步 SQLite |
| Click | 8.0+ | CLI 框架 |
| Rich | 13.0+ | 终端美化 |
| tiktoken | 0.8+ | Token 计算 |
| tenacity | 9.0+ | 重试机制 |

### 1.2 开发依赖

| 组件 | 版本 | 用途 |
|------|------|------|
| pytest | 8.0+ | 测试框架 |
| pytest-asyncio | 0.24+ | 异步测试 |
| pytest-cov | 6.0+ | 覆盖率 |
| ruff | 0.8+ | 代码检查 |
| mypy | 1.13+ | 类型检查 |
| pre-commit | 4.0+ | Git 钩子 |

---

## 2. 核心模块实现

### 2.1 类型系统 (types.py)

```python
"""
核心类型定义

所有数据模型使用 Pydantic v2 定义，提供：
1. 运行时类型验证
2. JSON 序列化
3. 文档生成
"""

from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import uuid4


class MessageRole(str, Enum):
    """消息角色枚举"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """工具调用定义"""
    model_config = ConfigDict(frozen=True)
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(description="工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="调用参数")


class Message(BaseModel):
    """基础消息模型"""
    model_config = ConfigDict(frozen=True)
    
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    reasoning: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentConfig(BaseModel):
    """Agent 配置"""
    model: str = Field(default="openai/gpt-4o", description="模型标识")
    api_key: Optional[str] = Field(default=None, description="API 密钥")
    base_url: Optional[str] = Field(default=None, description="自定义 API 地址")
    max_iterations: int = Field(default=50, ge=1, le=200)
    context_window: int = Field(default=128000, ge=1000)
    temperature: float = Field(default=0.7, ge=0, le=2)
    permission_mode: Literal["accept_all", "auto", "confirm_all"] = "accept_all"
    compact_threshold: float = Field(default=0.8, ge=0.5, le=0.95)
    
    # 并发控制
    max_concurrent_tasks: int = Field(default=5, ge=1, le=20)
    max_concurrent_subagents: int = Field(default=3, ge=1, le=10)
    
    # 超时配置
    tool_timeout: float = Field(default=60.0, ge=1.0)
    subagent_timeout: float = Field(default=300.0, ge=10.0)


class ToolContext(BaseModel):
    """工具执行上下文"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    agent_id: str
    session_id: str
    workspace_dir: str
    readonly: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 2.2 配置管理 (config.py)

```python
"""
配置管理系统

支持多种配置源（优先级从高到低）：
1. 代码中直接传入
2. 环境变量
3. 配置文件
4. 默认值
"""

import os
import yaml
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # LLM 配置
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    default_model: str = "openai/gpt-4o"
    
    # 应用配置
    log_level: str = "INFO"
    database_url: str = "sqlite:///./feinn.db"
    workspace_dir: str = "."
    
    # 权限配置
    default_permission: str = "accept_all"  # accept_all, auto, confirm_all
    
    # 并发配置
    max_concurrent_tasks: int = 5
    max_concurrent_subagents: int = 3
    
    # MCP 配置
    mcp_servers: dict = {}
    
    class Config:
        env_prefix = "FEINN_"
        env_file = ".env"
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        """从 YAML 文件加载配置"""
        if not path.exists():
            return cls()
        
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        return cls(**data)
    
    def to_yaml(self, path: Path) -> None:
        """保存配置到 YAML 文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)


def load_config(config_path: Optional[Path] = None) -> Settings:
    """加载配置"""
    # 1. 从文件加载
    if config_path is None:
        config_path = Path.home() / ".feinn" / "config.yaml"
    
    settings = Settings.from_yaml(config_path)
    
    # 2. 环境变量会自动覆盖（Pydantic Settings 功能）
    
    return settings
```

### 2.3 提供商适配 (providers.py)

```python
"""
LLM 提供商适配器

实现统一的 Provider 接口，支持多种 LLM 服务。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
import aiohttp
import json

from .types import Message, ToolCall, AgentConfig


class Provider(ABC):
    """LLM 提供商抽象基类"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
    
    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """完成对话，返回响应"""
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None
    ) -> AsyncIterator[str]:
        """流式生成"""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """计算 token 数量"""
        pass
    
    def _messages_to_provider_format(self, messages: List[Message]) -> List[Dict]:
        """转换为提供商格式"""
        result = []
        for msg in messages:
            data = {"role": msg.role.value, "content": msg.content}
            if msg.name:
                data["name"] = msg.name
            if msg.tool_calls:
                data["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                data["tool_call_id"] = msg.tool_call_id
            result.append(data)
        return result


class OpenAIProvider(Provider):
    """OpenAI 提供商"""
    
    BASE_URL = "https://api.openai.com/v1"
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found")
        self.base_url = config.base_url or self.BASE_URL
    
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """非流式完成"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self._get_model_name(),
            "messages": self._messages_to_provider_format(messages),
            "temperature": self.config.temperature,
            "max_tokens": 4096
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return self._parse_response(data)
    
    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None
    ) -> AsyncIterator[str]:
        """流式生成"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self._get_model_name(),
            "messages": self._messages_to_provider_format(messages),
            "temperature": self.config.temperature,
            "stream": True
        }
        
        if tools:
            payload["tools"] = tools
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError):
                            continue
    
    def count_tokens(self, text: str) -> int:
        """使用 tiktoken 计算 token"""
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model("gpt-4")
            return len(encoding.encode(text))
        except ImportError:
            # 粗略估算：1 token ≈ 4 字符
            return len(text) // 4
    
    def _get_model_name(self) -> str:
        """获取模型名称"""
        return self.config.model.replace("openai/", "")
    
    def _parse_response(self, data: Dict) -> Dict[str, Any]:
        """解析响应"""
        choice = data["choices"][0]
        message = choice["message"]
        
        result = {
            "content": message.get("content", ""),
            "reasoning": None,
            "tool_calls": None
        }
        
        if "tool_calls" in message:
            result["tool_calls"] = [
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"])
                )
                for tc in message["tool_calls"]
            ]
        
        return result


class AnthropicProvider(Provider):
    """Anthropic Claude 提供商"""
    
    BASE_URL = "https://api.anthropic.com/v1"
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key not found")
        self.base_url = config.base_url or self.BASE_URL
    
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """非流式完成"""
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # 分离系统提示
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg.role.value == "system":
                system_msg = msg.content
            else:
                chat_messages.append({
                    "role": msg.role.value,
                    "content": msg.content
                })
        
        payload = {
            "model": self._get_model_name(),
            "messages": chat_messages,
            "max_tokens": 4096,
            "temperature": self.config.temperature
        }
        
        if system_msg:
            payload["system"] = system_msg
        
        if tools:
            payload["tools"] = tools
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return self._parse_response(data)
    
    async def stream(self, messages, tools=None):
        """流式生成（简化实现）"""
        # 实际实现需要处理 SSE 流
        raise NotImplementedError("Streaming not yet implemented for Anthropic")
    
    def count_tokens(self, text: str) -> int:
        """粗略估算"""
        return len(text) // 4
    
    def _get_model_name(self) -> str:
        """获取模型名称"""
        return self.config.model.replace("anthropic/", "")
    
    def _parse_response(self, data: Dict) -> Dict[str, Any]:
        """解析响应"""
        result = {
            "content": "",
            "reasoning": None,
            "tool_calls": None
        }
        
        content_parts = []
        tool_calls = []
        
        for block in data.get("content", []):
            if block["type"] == "text":
                content_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(
                    id=block["id"],
                    name=block["name"],
                    arguments=block["input"]
                ))
        
        result["content"] = "\n".join(content_parts)
        if tool_calls:
            result["tool_calls"] = tool_calls
        
        return result


class ProviderRegistry:
    """提供商注册表"""
    
    _providers: Dict[str, type] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider
    }
    
    @classmethod
    def register(cls, name: str, provider_class: type) -> None:
        """注册新提供商"""
        cls._providers[name] = provider_class
    
    @classmethod
    def create(cls, config: AgentConfig) -> Provider:
        """创建提供商实例"""
        provider_name = config.model.split("/")[0]
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        return cls._providers[provider_name](config)
```

### 2.4 上下文管理 (context.py)

```python
"""
上下文管理器

负责维护对话历史和状态，支持：
1. 消息存储和检索
2. Token 计数
3. 压缩触发
4. 持久化
"""

from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

from .types import Message, MessageRole


@dataclass
class ContextMetadata:
    """上下文元数据"""
    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    message_count: int = 0
    total_tokens: int = 0
    compression_count: int = 0


class ContextManager:
    """上下文管理器"""
    
    def __init__(
        self,
        session_id: str,
        system_prompt: str,
        max_tokens: int = 128000,
        compact_threshold: float = 0.8
    ):
        self.session_id = session_id
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.compact_threshold = compact_threshold
        
        self.messages: List[Message] = []
        self.metadata = ContextMetadata(session_id=session_id)
        
        # 添加系统消息
        self.add_message(Message(role=MessageRole.SYSTEM, content=system_prompt))
    
    def add_message(self, message: Message) -> None:
        """添加消息"""
        self.messages.append(message)
        self.metadata.message_count += 1
        self.metadata.updated_at = datetime.utcnow()
        self._update_token_count()
    
    def get_messages(self, include_system: bool = True) -> List[Message]:
        """获取消息列表"""
        if include_system:
            return self.messages
        return [m for m in self.messages if m.role != MessageRole.SYSTEM]
    
    def get_token_count(self) -> int:
        """获取当前 token 数"""
        return self.metadata.total_tokens
    
    def needs_compaction(self) -> bool:
        """检查是否需要压缩"""
        return self.metadata.total_tokens > self.max_tokens * self.compact_threshold
    
    def clear(self, keep_system: bool = True) -> None:
        """清空上下文"""
        if keep_system and self.messages:
            system_msg = self.messages[0]
            if system_msg.role == MessageRole.SYSTEM:
                self.messages = [system_msg]
            else:
                self.messages = []
        else:
            self.messages = []
        
        self.metadata.message_count = len(self.messages)
        self._update_token_count()
    
    def replace_messages(self, messages: List[Message]) -> None:
        """替换消息列表（用于压缩后）"""
        self.messages = messages
        self.metadata.message_count = len(messages)
        self.metadata.compression_count += 1
        self._update_token_count()
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "session_id": self.session_id,
            "system_prompt": self.system_prompt,
            "messages": [
                {
                    "role": m.role.value,
                    "content": m.content,
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in m.tool_calls
                    ] if m.tool_calls else None,
                    "tool_call_id": m.tool_call_id,
                    "reasoning": m.reasoning,
                    "timestamp": m.timestamp.isoformat()
                }
                for m in self.messages
            ],
            "metadata": {
                "created_at": self.metadata.created_at.isoformat(),
                "updated_at": self.metadata.updated_at.isoformat(),
                "message_count": self.metadata.message_count,
                "total_tokens": self.metadata.total_tokens,
                "compression_count": self.metadata.compression_count
            }
        }
    
    def _update_token_count(self) -> None:
        """更新 token 计数（粗略估算）"""
        total = 0
        for msg in self.messages:
            # 粗略估算：1 token ≈ 4 字符
            total += len(msg.content) // 4
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    total += len(tc.name) // 4
                    total += len(json.dumps(tc.arguments)) // 4
        
        self.metadata.total_tokens = total
```

### 2.5 上下文压缩 (compaction.py)

```python
"""
上下文压缩引擎

实现多种压缩策略，确保长对话稳定性。
"""

from typing import List, Protocol
from abc import ABC, abstractmethod
import json

from .types import Message, MessageRole
from .context import ContextManager


class CompactionStrategy(ABC):
    """压缩策略基类"""
    
    @abstractmethod
    def apply(self, messages: List[Message]) -> List[Message]:
        """应用压缩策略"""
        pass
    
    def estimate_tokens(self, messages: List[Message]) -> int:
        """估算 token 数"""
        total = 0
        for msg in messages:
            total += len(msg.content) // 4
        return total


class SummarizationStrategy(CompactionStrategy):
    """摘要压缩策略
    
    对早期消息生成摘要，替换原始消息。
    """
    
    def __init__(self, provider):
        self.provider = provider
        self.summary_prompt = """请对以下对话历史生成简洁的摘要，保留关键信息：

{messages}

摘要："""
    
    def apply(self, messages: List[Message]) -> List[Message]:
        """应用摘要压缩"""
        if len(messages) <= 3:
            return messages
        
        # 保留系统消息和最近 3 条
        system_msgs = [m for m in messages if m.role == MessageRole.SYSTEM]
        recent_msgs = messages[-3:]
        to_summarize = messages[len(system_msgs):-3]
        
        if not to_summarize:
            return messages
        
        # 生成摘要（简化实现，实际应调用 LLM）
        summary_content = self._generate_summary(to_summarize)
        
        summary_msg = Message(
            role=MessageRole.SYSTEM,
            content=f"[历史摘要] {summary_content}"
        )
        
        return system_msgs + [summary_msg] + recent_msgs
    
    def _generate_summary(self, messages: List[Message]) -> str:
        """生成摘要（简化版）"""
        # 实际实现应调用 LLM
        topics = set()
        for msg in messages:
            if "文件" in msg.content:
                topics.add("文件操作")
            if "代码" in msg.content:
                topics.add("代码相关")
            if "测试" in msg.content:
                topics.add("测试相关")
        
        if topics:
            return f"讨论了: {', '.join(topics)}"
        return "一般性对话"


class SelectiveDropStrategy(CompactionStrategy):
    """选择性丢弃策略
    
    丢弃低优先级消息（如工具结果中的中间状态）。
    """
    
    def apply(self, messages: List[Message]) -> List[Message]:
        """应用选择性丢弃"""
        result = []
        
        for i, msg in enumerate(messages):
            # 保留系统消息
            if msg.role == MessageRole.SYSTEM:
                result.append(msg)
                continue
            
            # 保留用户消息
            if msg.role == MessageRole.USER:
                result.append(msg)
                continue
            
            # 保留助手消息（有内容或工具调用）
            if msg.role == MessageRole.ASSISTANT:
                if msg.content or msg.tool_calls:
                    result.append(msg)
                continue
            
            # 工具消息：保留错误，丢弃成功但冗长的
            if msg.role == MessageRole.TOOL:
                if msg.content and ("error" in msg.content.lower() or 
                                   "fail" in msg.content.lower()):
                    result.append(msg)
                elif len(msg.content) < 500:  # 保留短结果
                    result.append(msg)
                # 丢弃长成功结果
        
        return result


class TruncationStrategy(CompactionStrategy):
    """截断策略
    
    截断超长消息内容。
    """
    
    def __init__(self, max_length: int = 2000):
        self.max_length = max_length
    
    def apply(self, messages: List[Message]) -> List[Message]:
        """应用截断"""
        result = []
        
        for msg in messages:
            if len(msg.content) > self.max_length:
                truncated = msg.content[:self.max_length] + "\n... [内容已截断]"
                result.append(Message(
                    role=msg.role,
                    content=truncated,
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                    reasoning=msg.reasoning
                ))
            else:
                result.append(msg)
        
        return result


class CompactionEngine:
    """上下文压缩引擎"""
    
    def __init__(self, provider, target_ratio: float = 0.6):
        self.provider = provider
        self.target_ratio = target_ratio
        self.strategies: List[CompactionStrategy] = [
            SummarizationStrategy(provider),
            SelectiveDropStrategy(),
            TruncationStrategy()
        ]
    
    def compact(self, context: ContextManager) -> bool:
        """
        执行压缩
        
        Returns:
            bool: 是否执行了压缩
        """
        if not context.needs_compaction():
            return False
        
        messages = context.get_messages()
        target_tokens = context.max_tokens * self.target_ratio
        
        for strategy in self.strategies:
            if strategy.estimate_tokens(messages) <= target_tokens:
                break
            
            messages = strategy.apply(messages)
        
        context.replace_messages(messages)
        return True
```

---

## 3. 工具系统实现

### 3.1 工具注册表 (tools/registry.py)

```python
"""
工具注册中心

实现工具的发现、注册、调用管理。
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from functools import wraps
import asyncio
import json

from ..types import ToolContext


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable
    is_readonly: bool = False
    is_destructive: bool = False
    is_concurrent_safe: bool = True


class ToolRegistry:
    """工具注册中心（单例）"""
    
    _instance = None
    _tools: Dict[str, Tool] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        is_readonly: bool = False,
        is_destructive: bool = False,
        is_concurrent_safe: bool = True
    ) -> Tool:
        """注册工具"""
        tool = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            is_readonly=is_readonly,
            is_destructive=is_destructive,
            is_concurrent_safe=is_concurrent_safe
        )
        self._tools[name] = tool
        return tool
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)
    
    def get_all_tools(self) -> List[Tool]:
        """获取所有工具"""
        return list(self._tools.values())
    
    def get_schemas(self) -> List[Dict]:
        """获取所有工具 schema（用于 LLM）"""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return schemas
    
    async def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: ToolContext
    ) -> str:
        """执行工具"""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        
        try:
            # 调用处理器
            if asyncio.iscoroutinefunction(tool.handler):
                result = await tool.handler(**arguments, context=context)
            else:
                result = tool.handler(**arguments, context=context)
            
            # 确保返回字符串
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
            
            return result
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


# 全局注册表实例
registry = ToolRegistry()


def register_tool(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    is_readonly: bool = False,
    is_destructive: bool = False,
    is_concurrent_safe: bool = True
):
    """工具注册装饰器"""
    def decorator(func):
        registry.register(
            name=name,
            description=description,
            parameters=parameters,
            handler=func,
            is_readonly=is_readonly,
            is_destructive=is_destructive,
            is_concurrent_safe=is_concurrent_safe
        )
        return func
    return decorator
```

### 3.2 内置工具示例 (tools/builtins.py)

```python
"""
内置工具实现
"""

import os
import glob as glob_module
import re
from pathlib import Path
from typing import Optional
import aiohttp

from .registry import register_tool
from ..types import ToolContext


@register_tool(
    name="Read",
    description="读取文件内容",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "文件绝对路径"
            },
            "offset": {
                "type": "integer",
                "description": "起始行号（从1开始）",
                "default": 1
            },
            "limit": {
                "type": "integer",
                "description": "读取行数",
                "default": 100
            }
        },
        "required": ["file_path"]
    },
    is_readonly=True
)
async def read_file(
    file_path: str,
    offset: int = 1,
    limit: int = 100,
    context: Optional[ToolContext] = None
) -> str:
    """读取文件内容"""
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}"
        
        if not path.is_file():
            return f"Error: Not a file: {file_path}"
        
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        start = max(0, offset - 1)
        end = min(len(lines), start + limit)
        
        selected_lines = lines[start:end]
        content = "".join(selected_lines)
        
        # 添加行号
        numbered = ""
        for i, line in enumerate(selected_lines, start=start + 1):
            numbered += f"{i:6d}\t{line}"
        
        return numbered
    except Exception as e:
        return f"Error reading file: {str(e)}"


@register_tool(
    name="Write",
    description="写入文件内容（覆盖或创建）",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "文件绝对路径"
            },
            "content": {
                "type": "string",
                "description": "文件内容"
            }
        },
        "required": ["file_path", "content"]
    },
    is_destructive=True
)
async def write_file(
    file_path: str,
    content: str,
    context: Optional[ToolContext] = None
) -> str:
    """写入文件"""
    try:
        if context and context.readonly:
            return "Error: Read-only mode"
        
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@register_tool(
    name="Bash",
    description="执行 Bash 命令",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的命令"
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间（秒）",
                "default": 60
            }
        },
        "required": ["command"]
    },
    is_destructive=True
)
async def bash_command(
    command: str,
    timeout: int = 60,
    context: Optional[ToolContext] = None
) -> str:
    """执行 Bash 命令"""
    import asyncio
    
    try:
        if context and context.readonly:
            return "Error: Read-only mode"
        
        # 危险命令检查
        dangerous = ["rm -rf /", "> /dev/sda", "mkfs"]
        for d in dangerous:
            if d in command:
                return f"Error: Dangerous command detected: {d}"
        
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=context.workspace_dir if context else None
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return f"Error: Command timed out after {timeout}s"
        
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")
        
        result = f"Exit code: {proc.returncode}\n"
        if output:
            result += f"\nStdout:\n{output[:5000]}"
        if error:
            result += f"\nStderr:\n{error[:5000]}"
        
        return result
    except Exception as e:
        return f"Error executing command: {str(e)}"
```

---

## 3.5 Skill 系统

### 3.5.1 Skill 定义

Skill 是可复用的提示模板，使用 Markdown + YAML Frontmatter 定义：

```python
@dataclass
class SkillDef:
    """Skill 定义"""
    name: str                      # 唯一标识
    description: str               # 描述
    triggers: list[str]            # 触发器（如 ["/commit"]）
    tools: list[str]               # 允许的工具
    prompt: str                    # 提示模板
    when_to_use: str               # 自动触发条件
    argument_hint: str             # 参数提示
    arguments: list[str]           # 命名参数列表
    model: str                     # 模型覆盖
    user_invocable: bool           # 用户可调用
    context: str                   # "inline" 或 "fork"
    source: str                    # "builtin", "user", "project"
```

### 3.5.2 Skill 文件格式

```markdown
---
name: commit
description: Create a well-structured git commit
triggers: ["/commit", "commit changes"]
tools: ["Bash", "Read"]
when_to_use: "Use when user wants to commit"
argument_hint: "[optional context]"
---

Review the git state and create a commit:
1. Run `git status` and `git diff --staged`
2. Analyze changes and write commit message
3. Execute `git commit -m "<message>"`

User context: $ARGUMENTS
```

### 3.5.3 Skill 加载器

```python
class SkillLoader:
    """Skill 加载器"""
    
    def load_skills(self) -> list[SkillDef]:
        """加载所有 Skill（优先级：project > user > builtin）"""
        paths = [
            Path.cwd() / ".feinn" / "skills",      # 项目级
            Path.home() / ".feinn" / "skills",     # 用户级
        ]
        # 加载并去重...
    
    def find_skill(self, query: str) -> SkillDef | None:
        """通过触发器查找 Skill"""
        # 匹配第一个词...
    
    def substitute_arguments(
        self, 
        prompt: str, 
        args: str, 
        arg_names: list[str]
    ) -> str:
        """替换参数占位符"""
        # $ARGUMENTS → 完整参数
        # $PR → 第一个参数（如果 arg_names=["pr"]）
```

### 3.5.4 Skill 执行器

```python
async def execute_skill(
    skill: SkillDef,
    args: str,
    agent: FeinnAgent,
    config: dict,
) -> AsyncIterator[AgentEvent]:
    """执行 Skill"""
    rendered = substitute_arguments(skill.prompt, args, skill.arguments)
    
    if skill.context == "fork":
        # 在隔离的子代理中执行
        async for event in _execute_forked(skill, rendered, agent, config):
            yield event
    else:
        # 在当前对话中内联执行
        async for event in _execute_inline(rendered, agent, config):
            yield event
```

### 3.5.5 Skill 工具

```python
# Skill 工具定义
SKILL_TOOL_DEF = ToolDef(
    name="Skill",
    description="Invoke a named skill (reusable prompt template)",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name"},
            "args": {"type": "string", "description": "Arguments"},
        },
        "required": ["name"],
    },
    handler=_skill_tool,
)

SKILL_LIST_TOOL_DEF = ToolDef(
    name="SkillList",
    description="List all available skills",
    input_schema={"type": "object", "properties": {}},
    handler=_skill_list_tool,
    read_only=True,
    concurrent_safe=True,
)
```

---

## 4. 数据存储

### 4.1 数据库模型

```python
"""
SQLAlchemy 模型定义
"""

from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, 
    Integer, Float, ForeignKey, JSON, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import enum

Base = declarative_base()


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class Session(Base):
    """会话表"""
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE)
    model = Column(String(100), nullable=False)
    system_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, default=dict)
    
    # 关系
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    """消息表"""
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # system/user/assistant/tool
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON, nullable=True)
    tool_call_id = Column(String(100), nullable=True)
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    token_count = Column(Integer, default=0)
    
    # 关系
    session = relationship("Session", back_populates="messages")


class Memory(Base):
    """内存表"""
    __tablename__ = "memories"
    
    id = Column(String(36), primary_key=True)
    scope = Column(String(20), nullable=False)  # workspace/agent
    agent_id = Column(String(36), nullable=True)  # agent scope 时使用
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # 向量嵌入
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    access_count = Column(Integer, default=0)


class Task(Base):
    """任务表"""
    __tablename__ = "tasks"
    
    id = Column(String(36), primary_key=True)
    parent_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending/running/completed/failed
    priority = Column(Integer, default=5)  # 1-10
    dependencies = Column(JSON, default=list)  # 依赖的任务 ID 列表
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    metadata = Column(JSON, default=dict)
```

---

## 5. API 设计

### 5.1 REST API

```python
"""
FastAPI 路由定义
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import json

app = FastAPI(title="FeinnAgent API", version="1.0.0")


# 请求/响应模型
class CreateSessionRequest(BaseModel):
    model: str = "openai/gpt-4o"
    system_prompt: Optional[str] = None
    name: Optional[str] = None


class SendMessageRequest(BaseModel):
    content: str
    session_id: str


class SessionResponse(BaseModel):
    id: str
    name: Optional[str]
    model: str
    status: str
    created_at: str


# 路由
@app.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """创建新会话"""
    from ..agent import Agent
    from ..config import load_config
    
    config = load_config()
    agent = Agent(config)
    session = await agent.create_session(
        model=request.model,
        system_prompt=request.system_prompt,
        name=request.name
    )
    
    return SessionResponse(
        id=session.id,
        name=session.name,
        model=session.model,
        status=session.status.value,
        created_at=session.created_at.isoformat()
    )


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话信息"""
    # 实现...
    pass


@app.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, request: SendMessageRequest):
    """发送消息（非流式）"""
    # 实现...
    pass


@app.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(session_id: str, request: SendMessageRequest):
    """发送消息（流式）"""
    async def event_generator():
        # 实现 SSE 流
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        
        # 模拟流式输出
        for chunk in ["Hello", " ", "World", "!"]:
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            await asyncio.sleep(0.1)
        
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@app.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, limit: int = 100, offset: int = 0):
    """获取会话消息列表"""
    # 实现...
    pass


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    # 实现...
    pass
```

---

## 6. 测试策略

### 6.1 单元测试

```python
"""
测试示例
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from feinn_agent.tools import ToolRegistry
from feinn_agent.context import ContextManager


@pytest.fixture
def tool_registry():
    """工具注册表 fixture"""
    return ToolRegistry()


@pytest.fixture
def context_manager():
    """上下文管理器 fixture"""
    return ContextManager(
        session_id="test-session",
        system_prompt="You are a helpful assistant."
    )


class TestToolRegistry:
    """工具注册表测试"""
    
    def test_register_tool(self, tool_registry):
        """测试工具注册"""
        mock_handler = Mock(return_value="result")
        
        tool = tool_registry.register(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object", "properties": {}},
            handler=mock_handler
        )
        
        assert tool.name == "test_tool"
        assert tool_registry.get_tool("test_tool") == tool
    
    @pytest.mark.asyncio
    async def test_execute_tool(self, tool_registry):
        """测试工具执行"""
        mock_handler = AsyncMock(return_value="async result")
        
        tool_registry.register(
            name="async_tool",
            description="Async tool",
            parameters={"type": "object", "properties": {}},
            handler=mock_handler
        )
        
        result = await tool_registry.execute(
            name="async_tool",
            arguments={},
            context=Mock()
        )
        
        assert result == "async result"
        mock_handler.assert_called_once()


class TestContextManager:
    """上下文管理器测试"""
    
    def test_add_message(self, context_manager):
        """测试添加消息"""
        from feinn_agent.types import Message, MessageRole
        
        msg = Message(role=MessageRole.USER, content="Hello")
        context_manager.add_message(msg)
        
        assert len(context_manager.get_messages()) == 2  # system + user
        assert context_manager.metadata.message_count == 2
    
    def test_needs_compaction(self, context_manager):
        """测试压缩触发"""
        from feinn_agent.types import Message, MessageRole
        
        # 添加大量消息
        for i in range(100):
            msg = Message(role=MessageRole.USER, content="x" * 1000)
            context_manager.add_message(msg)
        
        assert context_manager.needs_compaction()
```

### 6.2 集成测试

```python
"""
集成测试
"""

import pytest
import asyncio
from httpx import AsyncClient

from feinn_agent.server import app


@pytest.fixture
async def client():
    """HTTP 客户端 fixture"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_create_session(client):
    """测试创建会话"""
    response = await client.post("/sessions", json={
        "model": "openai/gpt-4o",
        "name": "Test Session"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["model"] == "openai/gpt-4o"


@pytest.mark.asyncio
async def test_send_message_stream(client):
    """测试流式消息"""
    # 先创建会话
    session_resp = await client.post("/sessions", json={})
    session_id = session_resp.json()["id"]
    
    # 发送流式消息
    response = await client.post(
        f"/sessions/{session_id}/messages/stream",
        json={"content": "Hello", "session_id": session_id}
    )
    
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
```

---

## 7. 部署配置

### 7.1 Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir -e "."

# 复制代码
COPY src/ ./src/

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "feinn_agent.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.2 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  feinn-agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FEINN_LOG_LEVEL=INFO
      - FEINN_DATABASE_URL=sqlite:///data/feinn.db
    volumes:
      - ./data:/app/data
      - ./workspace:/app/workspace
    restart: unless-stopped
```

---

## 8. 监控与日志

### 8.1 日志配置

```python
"""
日志配置
"""

import logging
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: Optional[Path] = None):
    """配置日志"""
    
    # 创建格式化器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # 根日志配置
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
```

### 8.2 指标收集

```python
"""
Prometheus 指标
"""

from prometheus_client import Counter, Histogram, Gauge

# 请求指标
request_count = Counter(
    "feinn_requests_total",
    "Total requests",
    ["method", "endpoint", "status"]
)

request_duration = Histogram(
    "feinn_request_duration_seconds",
    "Request duration",
    ["method", "endpoint"]
)

# Agent 指标
active_sessions = Gauge(
    "feinn_active_sessions",
    "Number of active sessions"
)

tool_calls = Counter(
    "feinn_tool_calls_total",
    "Total tool calls",
    ["tool_name", "status"]
)

llm_tokens = Counter(
    "feinn_llm_tokens_total",
    "Total LLM tokens",
    ["model", "type"]  # type: input/output
)
```

---

## 9. 附录

### 9.1 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| FEINN_LOG_LEVEL | 日志级别 | INFO |
| FEINN_DATABASE_URL | 数据库连接 | sqlite:///./feinn.db |
| FEINN_DEFAULT_PERMISSION | 默认权限模式 | accept_all |
| FEINN_MAX_CONCURRENT_TASKS | 最大并发任务 | 5 |
| FEINN_MAX_CONCURRENT_SUBAGENTS | 最大并发子代理 | 3 |
| OPENAI_API_KEY | OpenAI API 密钥 | - |
| ANTHROPIC_API_KEY | Anthropic API 密钥 | - |

### 9.2 配置文件示例

```yaml
# ~/.feinn/config.yaml
log_level: INFO
default_model: openai/gpt-4o
default_permission: auto

max_concurrent_tasks: 5
max_concurrent_subagents: 3

context:
  window_size: 128000
  compact_threshold: 0.8

mcp_servers:
  filesystem:
    command: npx
    args:
      - -y
      - "@modelcontextprotocol/server-filesystem"
      - /home/user/workspace
```
