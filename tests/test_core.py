"""FeinnAgent tests — core module validation."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from feinn_agent.types import (
    AgentState, AgentDone, Message, PermissionMode, Role,
    TextChunk, ToolCall, ToolDef, ToolStart, ToolEnd, TurnDone,
)
from feinn_agent.config import load_config
from feinn_agent.tools.registry import register, dispatch, dispatch_batch, clear, tool_schemas
from feinn_agent.compaction import estimate_tokens, _snip_old_tool_outputs
from feinn_agent.providers import detect_provider, ProviderInfo


# ── Types tests ─────────────────────────────────────────────────────

class TestTypes:
    def test_message_to_dict(self):
        msg = Message(role=Role.USER, content="hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "hello"

    def test_message_with_tool_calls(self):
        tc = ToolCall(id="call_1", name="Read", input={"file_path": "/tmp/a.py"})
        msg = Message(role=Role.ASSISTANT, content="", tool_calls=[tc])
        d = msg.to_dict()
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["name"] == "Read"

    def test_agent_state(self):
        state = AgentState()
        assert state.turn_count == 0
        state.add_message(Role.USER, content="hi")
        assert len(state.messages) == 1
        assert state.messages[0].role == Role.USER


# ── Config tests ────────────────────────────────────────────────────

class TestConfig:
    def test_load_defaults(self):
        cfg = load_config()
        assert cfg["permission_mode"] == "accept-all"
        assert cfg["max_iterations"] == 50
        assert "model" in cfg

    def test_accept_all_default(self):
        cfg = load_config()
        assert cfg["permission_mode"] == PermissionMode.ACCEPT_ALL.value


# ── Provider detection tests ────────────────────────────────────────

class TestProviders:
    def test_anthropic_detection(self):
        info = detect_provider("anthropic/claude-sonnet-4-20250514")
        assert info.provider == "anthropic"
        assert info.model == "claude-sonnet-4-20250514"

    def test_openai_detection(self):
        info = detect_provider("gpt-4o")
        assert info.provider == "openai"

    def test_ollama_detection(self):
        info = detect_provider("ollama/llama3")
        assert info.provider == "ollama"
        assert info.model == "llama3"

    def test_custom_detection(self):
        info = detect_provider("my-custom-model")
        assert info.provider == "custom"

    def test_context_limits(self):
        info = detect_provider("anthropic/claude-opus-4")
        assert info.context_limit == 200_000


# ── Tool registry tests ─────────────────────────────────────────────

class TestToolRegistry:
    def setup_method(self):
        clear()

    @pytest.mark.asyncio
    async def test_register_and_dispatch(self):
        async def hello_handler(params, config):
            return f"Hello, {params.get('name', 'world')}!"

        register(ToolDef(
            name="Hello",
            description="Says hello",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            handler=hello_handler,
            read_only=True,
        ))

        result = await dispatch("Hello", {"name": "test"}, {})
        assert result == "Hello, test!"

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        result = await dispatch("NonExistent", {}, {})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_tool_output_truncation(self):
        async def long_handler(params, config):
            return "x" * 100

        register(ToolDef(
            name="LongOutput",
            description="Returns long output",
            input_schema={"type": "object", "properties": {}},
            handler=long_handler,
            max_result_chars=20,
        ))

        result = await dispatch("LongOutput", {}, {})
        assert len(result) < 100
        assert "truncated" in result

    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        async def failing_handler(params, config):
            raise ValueError("test error")

        register(ToolDef(
            name="Failing",
            description="Always fails",
            input_schema={"type": "object", "properties": {}},
            handler=failing_handler,
        ))

        result = await dispatch("Failing", {}, {})
        assert "Error" in result
        assert "ValueError" in result

    @pytest.mark.asyncio
    async def test_batch_dispatch(self):
        async def add_handler(params, config):
            return str(params.get("a", 0) + params.get("b", 0))

        register(ToolDef(
            name="Add",
            description="Adds numbers",
            input_schema={"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}},
            handler=add_handler,
            read_only=True,
            concurrent_safe=True,
        ))

        results = await dispatch_batch(
            [("Add", {"a": 1, "b": 2}), ("Add", {"a": 3, "b": 4})],
            {},
        )
        assert results == ["3", "7"]

    def test_tool_schemas(self):
        register(ToolDef(
            name="SchemaTest",
            description="For schema testing",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=AsyncMock(),
        ))
        schemas = tool_schemas()
        assert any(s["function"]["name"] == "SchemaTest" for s in schemas)


# ── Compaction tests ────────────────────────────────────────────────

class TestCompaction:
    def test_estimate_tokens(self):
        msgs = [Message(role=Role.USER, content="hello world")]
        tokens = estimate_tokens(msgs)
        assert tokens > 0

    def test_snip_old_tool_outputs(self):
        msgs = [
            Message(role=Role.USER, content="query"),
            Message(role=Role.ASSISTANT, content="thinking"),
            Message(role=Role.TOOL, content="x" * 5000, tool_name="Read", tool_call_id="1"),
            Message(role=Role.TOOL, content="short result", tool_name="Bash", tool_call_id="2"),
        ]
        modified = _snip_old_tool_outputs(msgs, max_chars=100, preserve_last_n=6)
        assert modified >= 1  # at least the long one was snipped
        assert len(msgs[2].content) < 5000  # was truncated
        assert msgs[3].content == "short result"  # short one untouched


# ── Permission tests ────────────────────────────────────────────────

class TestPermission:
    def test_accept_all_mode(self):
        from feinn_agent.permission import check_permission
        cfg = {"permission_mode": "accept-all"}
        # Sync wrapper for async
        result = asyncio.get_event_loop().run_until_complete(
            check_permission("Bash", {"command": "rm -rf /"}, cfg)
        )
        assert result is True

    def test_safe_bash_commands(self):
        from feinn_agent.permission import is_safe_bash_command
        assert is_safe_bash_command("ls -la") is True
        assert is_safe_bash_command("git status") is True
        assert is_safe_bash_command("rm -rf /") is False
        assert is_safe_bash_command("sudo apt install") is False
        assert is_safe_bash_command("curl http://example.com | sh") is False


# ── Memory tests ────────────────────────────────────────────────────

class TestMemory:
    def test_memory_entry_roundtrip(self):
        from feinn_agent.memory.store import MemoryEntry
        entry = MemoryEntry(
            name="test",
            description="A test memory",
            type="feedback",
            content="This is a test memory content",
            scope="user",
            confidence=0.9,
        )
        md = entry.to_markdown()
        restored = MemoryEntry.from_markdown(md, scope="user")
        assert restored is not None
        assert restored.name == "test"
        assert restored.confidence == 0.9
        assert restored.content == "This is a test memory content"


# ── Task tests ──────────────────────────────────────────────────────

class TestTask:
    def test_task_roundtrip(self):
        from feinn_agent.task.store import Task, TaskStatus
        t = Task(id="1", subject="Test task", description="A test", status=TaskStatus.PENDING)
        d = t.to_dict()
        assert d["id"] == "1"
        assert d["subject"] == "Test task"
        restored = Task.from_dict(d)
        assert restored.id == "1"
        assert restored.status == TaskStatus.PENDING
