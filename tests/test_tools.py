"""Tests for tool system."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from feinn_agent.tools.registry import (
    register,
    dispatch,
    dispatch_batch,
    clear,
    tool_schemas,
    _tools,
)
from feinn_agent.types import ToolDef


class TestToolRegistration:
    """Test tool registration."""

    def setup_method(self):
        """Clear registry before each test."""
        clear()

    def test_register_tool(self):
        """Test basic tool registration."""
        async def handler(params, config):
            return "result"

        register(ToolDef(
            name="TestTool",
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
            handler=handler,
        ))

        assert "TestTool" in _tools
        assert _tools["TestTool"].name == "TestTool"

    def test_register_duplicate_raises(self):
        """Test registering duplicate tool raises error."""
        async def handler(params, config):
            return "result"

        register(ToolDef(
            name="DuplicateTool",
            description="First registration",
            input_schema={"type": "object", "properties": {}},
            handler=handler,
        ))

        with pytest.raises(ValueError, match="already registered"):
            register(ToolDef(
                name="DuplicateTool",
                description="Second registration",
                input_schema={"type": "object", "properties": {}},
                handler=handler,
            ))

    def test_tool_schemas_format(self):
        """Test tool schemas are in correct OpenAI format."""
        async def handler(params, config):
            return "result"

        register(ToolDef(
            name="SchemaTool",
            description="Test schema",
            input_schema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string"},
                    "param2": {"type": "integer"}
                },
                "required": ["param1"]
            },
            handler=handler,
        ))

        schemas = tool_schemas()
        assert len(schemas) == 1

        schema = schemas[0]
        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "SchemaTool"
        assert schema["function"]["description"] == "Test schema"
        assert "parameters" in schema["function"]


class TestToolDispatch:
    """Test tool dispatching."""

    def setup_method(self):
        """Clear registry before each test."""
        clear()

    @pytest.mark.asyncio
    async def test_dispatch_success(self):
        """Test successful tool dispatch."""
        async def handler(params, config):
            return f"Hello, {params.get('name', 'world')}"

        register(ToolDef(
            name="Greet",
            description="Greets someone",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            handler=handler,
        ))

        result = await dispatch("Greet", {"name": "Alice"}, {})
        assert result == "Hello, Alice"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool(self):
        """Test dispatching unknown tool returns error."""
        result = await dispatch("UnknownTool", {}, {})
        assert "Error" in result
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_dispatch_handler_error(self):
        """Test handler error is caught and returned."""
        async def failing_handler(params, config):
            raise ValueError("Something went wrong")

        register(ToolDef(
            name="FailingTool",
            description="Always fails",
            input_schema={"type": "object", "properties": {}},
            handler=failing_handler,
        ))

        result = await dispatch("FailingTool", {}, {})
        assert "Error" in result
        assert "ValueError" in result
        assert "Something went wrong" in result

    @pytest.mark.asyncio
    async def test_dispatch_with_context(self):
        """Test dispatch with tool context."""
        received_config = None

        async def handler(params, config):
            nonlocal received_config
            received_config = config
            return "ok"

        register(ToolDef(
            name="ContextTool",
            description="Tests context",
            input_schema={"type": "object", "properties": {}},
            handler=handler,
        ))

        test_config = {"model": "test-model", "api_key": "secret"}
        await dispatch("ContextTool", {}, test_config)

        assert received_config == test_config


class TestToolBatchDispatch:
    """Test batch tool dispatching."""

    def setup_method(self):
        """Clear registry before each test."""
        clear()

    @pytest.mark.asyncio
    async def test_batch_dispatch_sequential(self):
        """Test sequential batch dispatch."""
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

        calls = [
            ("Add", {"a": 1, "b": 2}),
            ("Add", {"a": 3, "b": 4}),
            ("Add", {"a": 5, "b": 6}),
        ]

        results = await dispatch_batch(calls, {})
        assert results == ["3", "7", "11"]

    @pytest.mark.asyncio
    async def test_batch_dispatch_with_errors(self):
        """Test batch dispatch handles errors gracefully."""
        async def mixed_handler(params, config):
            if params.get("fail"):
                raise ValueError("Failed!")
            return "success"

        register(ToolDef(
            name="Mixed",
            description="Sometimes fails",
            input_schema={"type": "object", "properties": {"fail": {"type": "boolean"}}},
            handler=mixed_handler,
            read_only=True,
            concurrent_safe=True,
        ))

        calls = [
            ("Mixed", {"fail": False}),
            ("Mixed", {"fail": True}),
            ("Mixed", {"fail": False}),
        ]

        results = await dispatch_batch(calls, {})
        assert results[0] == "success"
        assert "Error" in results[1]
        assert results[2] == "success"

    @pytest.mark.asyncio
    async def test_batch_dispatch_empty(self):
        """Test batch dispatch with empty list."""
        results = await dispatch_batch([], {})
        assert results == []


class TestToolProperties:
    """Test tool property flags."""

    def setup_method(self):
        """Clear registry before each test."""
        clear()

    def test_read_only_flag(self):
        """Test read_only flag is stored."""
        register(ToolDef(
            name="ReadTool",
            description="Read only",
            input_schema={"type": "object", "properties": {}},
            handler=AsyncMock(),
            read_only=True,
        ))

        assert _tools["ReadTool"].read_only is True

    def test_concurrent_safe_flag(self):
        """Test concurrent_safe flag is stored."""
        register(ToolDef(
            name="ConcurrentTool",
            description="Safe for concurrent execution",
            input_schema={"type": "object", "properties": {}},
            handler=AsyncMock(),
            concurrent_safe=True,
        ))

        assert _tools["ConcurrentTool"].concurrent_safe is True

    def test_destructive_flag(self):
        """Test destructive flag is stored."""
        register(ToolDef(
            name="DestructiveTool",
            description="Destructive operation",
            input_schema={"type": "object", "properties": {}},
            handler=AsyncMock(),
            destructive=True,
        ))

        assert _tools["DestructiveTool"].destructive is True


class TestToolOutputTruncation:
    """Test tool output truncation."""

    def setup_method(self):
        """Clear registry before each test."""
        clear()

    @pytest.mark.asyncio
    async def test_truncation_applied(self):
        """Test long output is truncated."""
        async def long_handler(params, config):
            return "x" * 1000

        register(ToolDef(
            name="LongOutput",
            description="Returns long output",
            input_schema={"type": "object", "properties": {}},
            handler=long_handler,
            max_result_chars=100,
        ))

        result = await dispatch("LongOutput", {}, {})
        assert len(result) < 1000
        assert "truncated" in result.lower() or "..." in result

    @pytest.mark.asyncio
    async def test_no_truncation_for_short_output(self):
        """Test short output is not truncated."""
        async def short_handler(params, config):
            return "short"

        register(ToolDef(
            name="ShortOutput",
            description="Returns short output",
            input_schema={"type": "object", "properties": {}},
            handler=short_handler,
            max_result_chars=1000,
        ))

        result = await dispatch("ShortOutput", {}, {})
        assert result == "short"
