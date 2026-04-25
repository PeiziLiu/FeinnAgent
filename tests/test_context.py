"""Tests for FeinnAgent context functionality."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from feinn_agent.context import build_system_prompt


class TestContext(unittest.TestCase):
    """Test context functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)
        
        # Create test files
        (self.project_dir / "README.md").write_text("# Test Project\nThis is a test project")
        (self.project_dir / "src").mkdir()
        (self.project_dir / "src" / "main.py").write_text("print('hello')")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_build_system_prompt(self):
        """Test building system prompt."""
        config = {"model": "gpt-4o"}
        
        prompt = build_system_prompt(
            config=config,
        )
        
        self.assertIsInstance(prompt, str)
        self.assertIn("You are FeinnAgent", prompt)

    def test_build_system_prompt_with_memory(self):
        """Test building system prompt with memory context."""
        config = {"model": "gpt-4o"}
        
        memory_context = "This is a memory item\nAnother memory item"
        
        prompt = build_system_prompt(
            config=config,
            memory_context=memory_context,
        )
        
        self.assertIsInstance(prompt, str)
        self.assertIn("You are FeinnAgent", prompt)

    def test_build_system_prompt_with_project_context(self):
        """Test building system prompt with project context."""
        config = {"model": "gpt-4o"}
        
        project_context = "# Project Context\nThis is a test project"
        
        prompt = build_system_prompt(
            config=config,
            project_context=project_context,
        )
        
        self.assertIsInstance(prompt, str)
        self.assertIn("You are FeinnAgent", prompt)
        self.assertIn("This is a test project", prompt)


if __name__ == "__main__":
    unittest.main()
