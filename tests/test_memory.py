"""Tests for memory system."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from feinn_agent.memory.store import (
    MemoryEntry,
    save_memory,
    search_memory,
    list_memories,
    delete_memory,
)


class TestMemoryEntry:
    """Test MemoryEntry dataclass."""

    def test_create_entry(self):
        """Test creating a memory entry."""
        entry = MemoryEntry(
            name="test-memory",
            description="A test memory",
            type="feedback",
            content="This is the content",
            scope="user",
            confidence=0.9,
        )

        assert entry.name == "test-memory"
        assert entry.description == "A test memory"
        assert entry.type == "feedback"
        assert entry.content == "This is the content"
        assert entry.scope == "user"
        assert entry.confidence == 0.9

    def test_to_markdown(self):
        """Test conversion to markdown."""
        entry = MemoryEntry(
            name="test",
            description="Test description",
            type="note",
            content="Test content",
            scope="project",
            confidence=0.8,
        )

        md = entry.to_markdown()

        assert "# test" in md
        assert "**Type**: note" in md
        assert "**Description**: Test description" in md
        assert "**Confidence**: 0.8" in md
        assert "Test content" in md

    def test_from_markdown(self):
        """Test parsing from markdown."""
        md = """# test-memory

**Type**: feedback
**Description**: Test description
**Confidence**: 0.95

This is the memory content.
It can span multiple lines.
"""

        entry = MemoryEntry.from_markdown(md, scope="user")

        assert entry is not None
        assert entry.name == "test-memory"
        assert entry.type == "feedback"
        assert entry.description == "Test description"
        assert entry.confidence == 0.95
        assert "This is the memory content" in entry.content

    def test_from_markdown_invalid(self):
        """Test parsing invalid markdown returns None."""
        entry = MemoryEntry.from_markdown("not a valid markdown", scope="user")
        assert entry is None

    def test_roundtrip(self):
        """Test markdown roundtrip preserves data."""
        original = MemoryEntry(
            name="roundtrip-test",
            description="Testing roundtrip",
            type="code-pattern",
            content="def hello():\n    return 'world'",
            scope="project",
            confidence=0.85,
        )

        md = original.to_markdown()
        restored = MemoryEntry.from_markdown(md, scope="project")

        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.type == original.type
        assert restored.content == original.content
        assert restored.scope == original.scope
        assert restored.confidence == original.confidence


class TestMemoryStorage:
    """Test memory storage operations."""

    @pytest.fixture
    def temp_memory_dir(self):
        """Create a temporary directory for memory storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("feinn_agent.memory.store._memory_dir", return_value=Path(tmpdir)):
                yield tmpdir

    def test_save_memory(self, temp_memory_dir):
        """Test saving a memory."""
        result = save_memory(
            name="test-save",
            description="Test saving",
            type="note",
            content="Test content",
            scope="user",
        )

        assert "Saved memory" in result
        assert "test-save" in result

    def test_list_memories(self, temp_memory_dir):
        """Test listing memories."""
        # Create some memories
        for i in range(3):
            save_memory(
                name=f"memory-{i}",
                description=f"Memory {i}",
                type="note",
                content=f"Content {i}",
                scope="user",
            )

        names = list_memories("user")

        assert len(names) == 3
        assert "memory-0" in names
        assert "memory-1" in names
        assert "memory-2" in names

    def test_delete_memory(self, temp_memory_dir):
        """Test deleting a memory."""
        save_memory(
            name="to-delete",
            description="To be deleted",
            type="note",
            content="Delete me",
            scope="user",
        )

        # Verify it exists
        names_before = list_memories("user")
        assert "to-delete" in names_before

        result = delete_memory("to-delete", scope="user")
        assert "deleted" in result.lower() or "removed" in result.lower()

    def test_scope_isolation(self, temp_memory_dir):
        """Test user and project scopes are isolated."""
        save_memory(
            name="shared-name",
            description="User version",
            type="note",
            content="User content",
            scope="user",
        )

        save_memory(
            name="shared-name",
            description="Project version",
            type="note",
            content="Project content",
            scope="project",
        )

        user_names = list_memories("user")
        project_names = list_memories("project")

        assert "shared-name" in user_names
        assert "shared-name" in project_names

    def test_list_empty_memories(self, temp_memory_dir):
        """Test listing when no memories exist."""
        names = list_memories("user")
        assert names == []


class TestMemorySearch:
    """Test memory search functionality."""

    @pytest.fixture
    def temp_memory_dir(self):
        """Create a temporary directory for memory storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("feinn_agent.memory.store._memory_dir", return_value=Path(tmpdir)):
                yield tmpdir

    def test_search_by_keyword(self, temp_memory_dir):
        """Test searching memories by keyword."""
        # Create memories with different content
        save_memory(name="python-tip", description="Python tip", type="code", content="Use list comprehensions", scope="user")
        save_memory(name="git-tip", description="Git tip", type="workflow", content="Use git rebase", scope="user")
        save_memory(name="another-python", description="More Python", type="code", content="Python decorators are useful", scope="user")

        results = search_memory("python", scope="user")

        assert len(results) >= 2
        names = [r.name for r in results]
        assert "python-tip" in names
        assert "another-python" in names

    def test_search_empty_query(self, temp_memory_dir):
        """Test searching with empty query returns all."""
        save_memory(name="mem-1", description="Mem 1", type="note", content="Content 1", scope="user")
        save_memory(name="mem-2", description="Mem 2", type="note", content="Content 2", scope="user")

        results = search_memory("", scope="user")

        assert len(results) == 2

    def test_search_no_results(self, temp_memory_dir):
        """Test searching with no matches."""
        save_memory(name="test", description="Test", type="note", content="Content", scope="user")

        results = search_memory("nonexistent-keyword-12345", scope="user")

        assert len(results) == 0

    def test_search_respects_scope(self, temp_memory_dir):
        """Test search only returns results from specified scope."""
        save_memory(name="user-mem", description="User", type="note", content="User content", scope="user")
        save_memory(name="project-mem", description="Project", type="note", content="Project content", scope="project")

        user_results = search_memory("content", scope="user")
        project_results = search_memory("content", scope="project")

        user_names = [r.name for r in user_results]
        project_names = [r.name for r in project_results]

        assert "user-mem" in user_names
        assert "project-mem" not in user_names

        assert "project-mem" in project_names
        assert "user-mem" not in project_names
