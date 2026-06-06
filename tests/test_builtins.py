"""Tests for built-in tools — Glob, Grep, WebFetch, AskUserQuestion, and edge cases."""

import tempfile
from pathlib import Path
import pytest

from feinn_agent.tools.builtins import (
    _read_file,
    _write_file,
    _glob,
    _grep,
    _web_fetch,
    _ask_user,
    _edit_file,
)


class TestReadFile:
    """Test _read_file handler edge cases."""

    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        result = await _read_file({}, {})
        assert "file_path is required" in result

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        result = await _read_file({"file_path": "/tmp/nonexistent-12345.txt"}, {})
        assert "file not found" in result

    @pytest.mark.asyncio
    async def test_is_directory(self, tmp_path):
        result = await _read_file({"file_path": str(tmp_path)}, {})
        assert "is a directory" in result

    @pytest.mark.asyncio
    async def test_read_with_offset_and_limit(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("\n".join([f"line {i}" for i in range(10)]) + "\n")
        result = await _read_file({"file_path": str(f), "offset": 2, "limit": 3}, {})
        lines = result.split("\n")
        assert len(lines) == 3
        assert "line 2" in lines[0]
        assert "line 3" in lines[1]
        assert "line 4" in lines[2]


class TestGlob:
    """Test _glob handler."""

    @pytest.mark.asyncio
    async def test_glob_no_matches(self, tmp_path):
        result = await _glob({"pattern": "*.xyz"}, {"path": str(tmp_path)})
        assert "No files matching" in result

    @pytest.mark.asyncio
    async def test_glob_with_matches(self, tmp_path):
        (tmp_path / "foo.py").write_text("")
        (tmp_path / "bar.py").write_text("")
        (tmp_path / "baz.md").write_text("")
        result = await _glob({"pattern": "*.py", "path": str(tmp_path)}, {})
        assert "foo.py" in result
        assert "bar.py" in result
        assert "baz.md" not in result

    @pytest.mark.asyncio
    async def test_glob_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("")
        result = await _glob({"pattern": "**/*.py", "path": str(tmp_path)}, {})
        assert "sub/deep.py" in result

    @pytest.mark.asyncio
    async def test_glob_empty_pattern(self, tmp_path):
        result = await _glob({"pattern": "", "path": str(tmp_path)}, {})
        assert "unacceptable pattern" in result.lower()

    @pytest.mark.asyncio
    async def test_glob_max_results(self, tmp_path):
        for i in range(300):
            (tmp_path / f"f{i}.txt").write_text("")
        result = await _glob({"pattern": "*.txt", "path": str(tmp_path)}, {})
        lines = result.split("\n")
        assert any("more files" in l for l in lines)


class TestGrep:
    """Test _grep handler."""

    @pytest.mark.asyncio
    async def test_empty_pattern(self):
        result = await _grep({}, {})
        assert "pattern is required" in result

    @pytest.mark.asyncio
    async def test_basic_search(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    return 'world'\n")
        result = await _grep({"pattern": "hello", "path": str(tmp_path)}, {})
        assert "test.py:1: def hello():" in result

    @pytest.mark.asyncio
    async def test_no_matches(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("content")
        result = await _grep({"pattern": "nonexistent", "path": str(tmp_path)}, {})
        assert "No matches" in result

    @pytest.mark.asyncio
    async def test_case_insensitive(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("Hello World")
        result = await _grep({"pattern": "hello", "path": str(tmp_path), "case_insensitive": True}, {})
        assert "Hello World" in result

    @pytest.mark.asyncio
    async def test_glob_filter(self, tmp_path):
        (tmp_path / "a.py").write_text("target")
        (tmp_path / "b.md").write_text("target")
        result = await _grep({"pattern": "target", "path": str(tmp_path), "glob": "*.py"}, {})
        assert "a.py" in result
        assert "b.md" not in result

    @pytest.mark.asyncio
    async def test_invalid_regex(self, tmp_path):
        result = await _grep({"pattern": "[invalid", "path": str(tmp_path)}, {})
        assert "Invalid regex" in result

    @pytest.mark.asyncio
    async def test_max_results_limit(self, tmp_path):
        for i in range(10):
            (tmp_path / f"f{i}.py").write_text(f"match_{i}")
        result = await _grep({"pattern": "match_", "path": str(tmp_path), "max_results": 3}, {})
        lines = result.split("\n")
        assert len(lines) == 3

    @pytest.mark.asyncio
    async def test_skip_large_file(self, tmp_path):
        f = tmp_path / "large.py"
        f.write_text("target" * 200_000)
        result = await _grep({"pattern": "target", "path": str(tmp_path)}, {})
        assert "No matches" in result or result.strip() == ""


class TestWebFetch:
    """Test _web_fetch handler."""

    @pytest.mark.asyncio
    async def test_missing_url(self):
        result = await _web_fetch({}, {})
        assert "url is required" in result


class TestAskUser:
    """Test _ask_user handler."""

    @pytest.mark.asyncio
    async def test_missing_question(self):
        result = await _ask_user({}, {})
        assert "question is required" in result

    @pytest.mark.asyncio
    async def test_ask_question(self):
        result = await _ask_user({"question": "Which file to edit?"}, {})
        assert "[User question: Which file to edit?]" in result


class TestWriteFile:
    """Test _write_file handler edge cases."""

    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        result = await _write_file({}, {})
        assert "file_path is required" in result

    @pytest.mark.asyncio
    async def test_write_new_file(self, tmp_path):
        f = tmp_path / "new.txt"
        result = await _write_file({"file_path": str(f), "content": "hello"}, {})
        assert "Successfully wrote" in result
        assert f.read_text() == "hello"

    @pytest.mark.asyncio
    async def test_write_with_diff(self, tmp_path):
        f = tmp_path / "existing.txt"
        f.write_text("old content")
        result = await _write_file({"file_path": str(f), "content": "new content"}, {})
        assert "Successfully wrote" in result
        assert "-old content" in result or "+new content" in result


class TestEditFile:
    """Test _edit_file handler edge cases."""

    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        result = await _edit_file({}, {})
        assert "file_path and old_string are required" in result
