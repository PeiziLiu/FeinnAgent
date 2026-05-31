"""Tests for CLI module — FeinnCompleter, permission callback."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from feinn_agent.cli import FeinnCompleter, _make_permission_callback
from feinn_agent.types import PermissionMode

# ── FeinnCompleter tests ──────────────────────────────────────────────


class MockDocument:
    """Minimal mock for prompt_toolkit's Document."""

    def __init__(self, text: str):
        self._text = text

    def get_word_before_cursor(self) -> str:
        return self._text

    def get_before_cursor(self, count: int = 0) -> str:
        return self._text


class MockCompleteEvent:
    pass


class TestFeinnCompleter:
    def setup_method(self):
        self.completer = FeinnCompleter()

    def test_commands_completion(self):
        doc = MockDocument("/h")
        result = list(self.completer.get_completions(doc, MockCompleteEvent()))
        assert len(result) > 0
        texts = [c.text for c in result]
        assert "/help" in texts

    def test_empty_input_no_completions(self):
        doc = MockDocument("")
        result = list(self.completer.get_completions(doc, MockCompleteEvent()))
        assert len(result) == 0

    def test_quit_completion(self):
        doc = MockDocument("/q")
        result = list(self.completer.get_completions(doc, MockCompleteEvent()))
        texts = [c.text for c in result]
        assert "/quit" in texts

    def test_skills_completion(self):
        FeinnCompleter.SKILL_ACTIVATORS = ["/commit", "/review"]
        doc = MockDocument("/c")
        result = list(self.completer.get_completions(doc, MockCompleteEvent()))
        texts = [c.text for c in result]
        assert "/commit" in texts

    def test_at_ref_completion(self):
        doc = MockDocument("@f")
        result = list(self.completer.get_completions(doc, MockCompleteEvent()))
        texts = [c.text for c in result]
        assert "@file:" in texts
        assert "@folder:" in texts

    def test_at_diff_completion(self):
        doc = MockDocument("@d")
        result = list(self.completer.get_completions(doc, MockCompleteEvent()))
        texts = [c.text for c in result]
        assert "@diff" in texts

    def test_file_path_completion_current_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            test_file = os.path.join(tmpdir, "test.txt")
            open(test_file, "w").close()
            doc = MockDocument("./t")
            result = list(self.completer.get_completions(doc, MockCompleteEvent()))
            texts = [c.text for c in result]
            assert any("test" in t for t in texts)

    def test_no_completion_for_regular_word(self):
        doc = MockDocument("hello")
        result = list(self.completer.get_completions(doc, MockCompleteEvent()))
        assert len(result) == 0


# ── Permission callback tests ─────────────────────────────────────────


class TestPermissionCallback:
    @pytest.mark.asyncio
    async def test_session_allowlist(self, monkeypatch):
        config: dict = {"permission_mode": PermissionMode.AUTO.value}
        callback = _make_permission_callback(config)
        request = MagicMock()
        request.name = "Bash"
        request.inputs = {"command": "ls"}

        # Monkey-patch _session_allowlist for this test
        import feinn_agent.cli as cli_mod

        cli_mod._session_allowlist.add("Bash")

        result = await callback(request)
        assert result is True

        cli_mod._session_allowlist.clear()

    @pytest.mark.asyncio
    async def test_deny_returns_false(self):
        config: dict = {"permission_mode": PermissionMode.AUTO.value}
        callback = _make_permission_callback(config)
        request = MagicMock()
        request.name = "Bash"
        request.inputs = {"command": "rm -rf /"}

        with patch("prompt_toolkit.PromptSession") as mock_cls:
            instance = mock_cls.return_value
            instance.prompt_async = AsyncMock(return_value="n")
            result = await callback(request)

        assert result is False

    @pytest.mark.asyncio
    async def test_accept_all_mode(self):
        config: dict = {"permission_mode": PermissionMode.AUTO.value}
        callback = _make_permission_callback(config)
        request = MagicMock()
        request.name = "Bash"
        request.inputs = {"command": "ls"}

        with patch("prompt_toolkit.PromptSession") as mock_cls:
            instance = mock_cls.return_value
            instance.prompt_async = AsyncMock(return_value="a")
            result = await callback(request)

        assert result is True
        assert config["permission_mode"] == PermissionMode.ACCEPT_ALL.value

    @pytest.mark.asyncio
    async def test_session_allowlist_option(self):
        config: dict = {"permission_mode": PermissionMode.AUTO.value}
        callback = _make_permission_callback(config)
        request = MagicMock()
        request.name = "Write"
        request.inputs = {"file_path": "/tmp/test.txt", "content": "hello"}

        import feinn_agent.cli as cli_mod

        cli_mod._session_allowlist.clear()

        with patch("prompt_toolkit.PromptSession") as mock_cls:
            instance = mock_cls.return_value
            instance.prompt_async = AsyncMock(return_value="s")
            result = await callback(request)

        assert result is True
        assert "Write" in cli_mod._session_allowlist

        cli_mod._session_allowlist.clear()
