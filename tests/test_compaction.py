"""Tests for context compaction."""

import pytest
from feinn_agent.compaction import (
    estimate_tokens,
    _snip_old_tool_outputs,
    maybe_compact,
)
from feinn_agent.types import Message, Role


class TestEstimateTokens:
    """Test token estimation."""

    def test_empty_messages(self):
        """Test estimation with no messages."""
        tokens = estimate_tokens([])
        assert tokens == 0

    def test_single_message(self):
        """Test estimation with single message."""
        msgs = [Message(role=Role.USER, content="hello")]
        tokens = estimate_tokens(msgs)
        assert tokens > 0

    def test_multiple_messages(self):
        """Test estimation with multiple messages."""
        msgs = [
            Message(role=Role.USER, content="hello"),
            Message(role=Role.ASSISTANT, content="hi there"),
        ]
        tokens = estimate_tokens(msgs)
        assert tokens > 0

    def test_long_message(self):
        """Test estimation with long message."""
        msgs = [Message(role=Role.USER, content="x" * 1000)]
        tokens = estimate_tokens(msgs)
        # Should be roughly 1000/3 = 333 tokens + framing
        assert tokens > 300

    def test_message_with_tool_calls(self):
        """Test estimation with tool calls."""
        from feinn_agent.types import ToolCall
        tc = ToolCall(id="1", name="Read", input={"file_path": "/tmp/test.txt"})
        msgs = [
            Message(role=Role.ASSISTANT, content="", tool_calls=[tc]),
        ]
        tokens = estimate_tokens(msgs)
        assert tokens > 0


class TestSnipToolOutputs:
    """Test tool output snipping."""

    def test_snips_long_outputs(self):
        """Test long tool outputs are snipped."""
        msgs = [
            Message(role=Role.USER, content="query"),
            Message(role=Role.TOOL, content="x" * 10000, tool_name="Read", tool_call_id="1"),
        ]

        modified = _snip_old_tool_outputs(msgs, max_chars=100, preserve_last_n=6)

        assert modified == 1
        assert len(msgs[1].content) < 10000
        assert "..." in msgs[1].content or "truncated" in msgs[1].content

    def test_preserves_short_outputs(self):
        """Test short tool outputs are preserved."""
        msgs = [
            Message(role=Role.USER, content="query"),
            Message(role=Role.TOOL, content="short result", tool_name="Read", tool_call_id="1"),
        ]

        modified = _snip_old_tool_outputs(msgs, max_chars=1000, preserve_last_n=6)

        assert modified == 0
        assert msgs[1].content == "short result"

    def test_preserves_last_n(self):
        """Test last N messages are preserved."""
        msgs = [
            Message(role=Role.TOOL, content="x" * 1000, tool_name="Read", tool_call_id="1"),
            Message(role=Role.TOOL, content="x" * 1000, tool_name="Read", tool_call_id="2"),
            Message(role=Role.TOOL, content="x" * 1000, tool_name="Read", tool_call_id="3"),
        ]

        modified = _snip_old_tool_outputs(msgs, max_chars=100, preserve_last_n=2)

        # Last 2 should be preserved (not modified)
        assert msgs[1].content == "x" * 1000  # Second to last
        assert msgs[2].content == "x" * 1000  # Last

    def test_no_tool_messages(self):
        """Test function with no tool messages."""
        msgs = [
            Message(role=Role.USER, content="query"),
            Message(role=Role.ASSISTANT, content="response"),
        ]

        modified = _snip_old_tool_outputs(msgs, max_chars=100, preserve_last_n=6)

        assert modified == 0
        assert msgs[0].content == "query"
        assert msgs[1].content == "response"


class TestMaybeCompact:
    """Test compaction decision logic."""

    def test_no_compact_when_under_threshold(self):
        """Test no compaction when under threshold."""
        config = {"compaction_threshold": 0.8, "compaction_preserve_last_n": 6}

        # Create messages that are well under threshold
        msgs = [Message(role=Role.USER, content="short")]

        # Mock estimate_tokens to return low value
        with pytest.mock.patch("feinn_agent.compaction.estimate_tokens", return_value=100):
            with pytest.mock.patch("feinn_agent.compaction._snip_old_tool_outputs") as mock_snip:
                maybe_compact(msgs, config, context_limit=10000)
                # Should not call snip
                mock_snip.assert_not_called()

    def test_compact_when_over_threshold(self):
        """Test compaction when over threshold."""
        config = {"compaction_threshold": 0.5, "compaction_preserve_last_n": 6}

        msgs = [Message(role=Role.USER, content="x" * 1000)]

        # Mock to simulate being over threshold
        with pytest.mock.patch("feinn_agent.compaction.estimate_tokens", return_value=6000):
            with pytest.mock.patch("feinn_agent.compaction._snip_old_tool_outputs") as mock_snip:
                mock_snip.return_value = 1
                maybe_compact(msgs, config, context_limit=10000)
                # Should call snip
                mock_snip.assert_called_once()

    def test_force_compact(self):
        """Test forced compaction."""
        config = {"compaction_threshold": 0.9, "compaction_preserve_last_n": 6}

        msgs = [Message(role=Role.USER, content="short")]

        with pytest.mock.patch("feinn_agent.compaction._snip_old_tool_outputs") as mock_snip:
            mock_snip.return_value = 0
            maybe_compact(msgs, config, force=True)
            # Should call snip even when under threshold
            mock_snip.assert_called_once()
