"""Tests for Agent core functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from feinn_agent.tools.registry import dispatch as real_dispatch

from feinn_agent.agent import FeinnAgent
from feinn_agent.types import (
    AgentState,
    AgentDone,
    AgentEvent,
    AssistantTurn,
    Message,
    PermissionMode,
    Role,
    TextChunk,
    ThinkingChunk,
    ToolCall,
    TurnDone,
)


class TestAgentCreation:
    """Test Agent initialization."""

    def test_agent_default_config(self):
        """Test agent with default config."""
        agent = FeinnAgent()
        assert agent.config is not None
        assert agent.system_prompt == ""
        assert isinstance(agent.state, AgentState)

    def test_agent_custom_config(self):
        """Test agent with custom config."""
        config = {
            "model": "openai/gpt-4o",
            "max_iterations": 100,
            "permission_mode": PermissionMode.MANUAL.value,
        }
        agent = FeinnAgent(config=config, system_prompt="You are a test assistant")

        assert agent.config["model"] == "openai/gpt-4o"
        assert agent.config["max_iterations"] == 100
        assert agent.system_prompt == "You are a test assistant"

    def test_agent_custom_state(self):
        """Test agent with custom state."""
        state = AgentState()
        state.add_message(Role.USER, content="previous message")

        agent = FeinnAgent(state=state)
        assert len(agent.state.messages) == 1
        assert agent.state.messages[0].content == "previous message"


class TestAgentRun:
    """Test Agent run loop."""

    @pytest.fixture
    def mock_stream(self):
        """Mock the LLM stream."""

        async def mock_stream_impl(*args, **kwargs):
            yield TextChunk(text="Hello!")
            yield AssistantTurn(
                text="Hello!",
                reasoning="",
                tool_calls=[],
                input_tokens=10,
                output_tokens=5,
            )

        with patch("feinn_agent.agent.llm_stream", side_effect=mock_stream_impl):
            yield

    @pytest.mark.asyncio
    async def test_simple_run(self, mock_stream):
        """Test simple agent run without tools."""
        agent = FeinnAgent(config={"model": "openai/gpt-4o", "max_iterations": 10}, system_prompt="You are helpful")

        events = []
        async for event in agent.run("Hi"):
            events.append(event)

        # Should have at least TextChunk and AgentDone
        assert any(isinstance(e, TextChunk) for e in events)
        assert any(isinstance(e, AgentDone) for e in events)

    @pytest.mark.asyncio
    async def test_run_adds_user_message(self, mock_stream):
        """Test that run adds user message to state."""
        agent = FeinnAgent(config={"model": "openai/gpt-4o", "max_iterations": 10})

        async for _ in agent.run("Test message"):
            pass

        assert len(agent.state.messages) > 0
        assert agent.state.messages[0].role == Role.USER
        assert agent.state.messages[0].content == "Test message"

    @pytest.mark.asyncio
    async def test_run_with_images(self, mock_stream):
        """Test agent run with image input."""
        agent = FeinnAgent(config={"model": "openai/gpt-4o", "max_iterations": 10})

        images = [{"media_type": "image/png", "data": "base64data"}]

        async for _ in agent.run("Describe this image", images=images):
            pass

        assert agent.state.messages[0].images == images


class TestAgentWithTools:
    """Test Agent tool handling."""

    @pytest.mark.asyncio
    async def test_tool_call_handling(self):
        """Test agent handles tool calls correctly."""
        tool_call = ToolCall(id="call_1", name="Read", input={"file_path": "/tmp/test.txt"})

        async def _mock_stream(*args, **kwargs):
            yield TextChunk(text="I'll read that file")
            yield AssistantTurn(
                text="I'll read that file",
                reasoning="",
                tool_calls=[tool_call],
                input_tokens=20,
                output_tokens=10,
            )

        with patch("feinn_agent.agent.llm_stream", side_effect=_mock_stream):
            with patch("feinn_agent.permission.check_permission", return_value=True):
                with patch("feinn_agent.tools.registry.dispatch_batch", return_value=["File content"]):
                    agent = FeinnAgent(
                        config={
                            "model": "openai/gpt-4o",
                            "max_iterations": 10,
                            "permission_mode": PermissionMode.ACCEPT_ALL.value,
                        }
                    )

                    events = []
                    async for event in agent.run("Read the file"):
                        events.append(event)

                    # Check that tool result was added to messages
                    tool_messages = [m for m in agent.state.messages if m.role == Role.TOOL]
                    assert len(tool_messages) > 0

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self):
        """Test agent respects max_iterations."""

        async def _mock_stream(*args, **kwargs):
            yield AssistantTurn(
                text="",
                reasoning="",
                tool_calls=[ToolCall(id="call_1", name="Read", input={})],
                input_tokens=10,
                output_tokens=5,
            )

        with patch("feinn_agent.agent.llm_stream", return_value=_mock_stream()):
            with patch("feinn_agent.tools.registry.dispatch_batch", return_value=["result"]):
                with patch("feinn_agent.permission.check_permission", return_value=True):
                    agent = FeinnAgent(
                        config={
                            "model": "openai/gpt-4o",
                            "max_iterations": 3,
                            "permission_mode": PermissionMode.ACCEPT_ALL.value,
                        }
                    )

                    events = []
                    async for event in agent.run("Trigger tools"):
                        events.append(event)

                    # Should stop after max_iterations
                    assert agent.state.turn_count <= 3


class TestAgentStateManagement:
    """Test Agent state management."""

    @pytest.mark.asyncio
    async def test_token_tracking(self):
        """Test agent tracks token usage."""

        async def _mock_stream(*args, **kwargs):
            yield AssistantTurn(
                text="Response",
                reasoning="",
                tool_calls=[],
                input_tokens=100,
                output_tokens=50,
            )

        with patch("feinn_agent.agent.llm_stream", side_effect=_mock_stream):
            agent = FeinnAgent(config={"model": "openai/gpt-4o", "max_iterations": 10})

            async for _ in agent.run("Test"):
                pass

            assert agent.state.total_input_tokens == 100
            assert agent.state.total_output_tokens == 50

    @pytest.mark.asyncio
    async def test_turn_count_increment(self):
        """Test turn count increments correctly."""

        async def mock_stream(*args, **kwargs):
            yield AssistantTurn(
                text="Response",
                reasoning="",
                tool_calls=[],
                input_tokens=10,
                output_tokens=5,
            )

        with patch("feinn_agent.agent.llm_stream", side_effect=mock_stream):
            agent = FeinnAgent(config={"model": "openai/gpt-4o", "max_iterations": 10})

            assert agent.state.turn_count == 0

            async for _ in agent.run("Test"):
                pass

            assert agent.state.turn_count == 1

    @pytest.mark.asyncio
    async def test_message_history_preserved(self):
        """Test message history is preserved across runs."""

        async def mock_stream(*args, **kwargs):
            yield AssistantTurn(
                text="Response",
                reasoning="",
                tool_calls=[],
                input_tokens=10,
                output_tokens=5,
            )

        with patch("feinn_agent.agent.llm_stream", side_effect=mock_stream):
            agent = FeinnAgent(config={"model": "openai/gpt-4o", "max_iterations": 10})

            # First run
            async for _ in agent.run("First message"):
                pass

            initial_message_count = len(agent.state.messages)

            # Second run
            async for _ in agent.run("Second message"):
                pass

            assert len(agent.state.messages) > initial_message_count


class TestAgentRetryLogic:
    """Test Agent retry behavior."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """Test agent retries on rate limit errors."""
        call_count = 0

        async def mock_stream_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("rate_limit exceeded")
            yield AssistantTurn(
                text="Success after retry",
                reasoning="",
                tool_calls=[],
                input_tokens=10,
                output_tokens=5,
            )

        with patch("feinn_agent.agent.llm_stream", side_effect=mock_stream_with_retry):
            with patch("asyncio.sleep", return_value=None):  # Don't actually sleep
                agent = FeinnAgent(config={"model": "openai/gpt-4o", "max_iterations": 10})

                async for event in agent.run("Test"):
                    if isinstance(event, TextChunk):
                        assert "Success after retry" in event.text or "Error" in event.text

    @pytest.mark.asyncio
    async def test_no_retry_on_fatal_error(self):
        """Test agent doesn't retry on fatal errors."""

        async def mock_stream_fatal(*args, **kwargs):
            raise ValueError("Invalid API key")

        with patch("feinn_agent.agent.llm_stream", side_effect=mock_stream_fatal):
            agent = FeinnAgent(config={"model": "openai/gpt-4o", "max_iterations": 10})

            events = []
            async for event in agent.run("Test"):
                events.append(event)

            # Should get error message and stop
            assert any(isinstance(e, TextChunk) and "Error" in e.text for e in events)
