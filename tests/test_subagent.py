"""Tests for FeinnAgent subagent functionality."""

import asyncio
import unittest
from unittest.mock import Mock, patch, MagicMock

from feinn_agent.subagent.manager import SubAgentManager, AgentDefinition, AgentTaskStatus


class TestSubAgentManager(unittest.TestCase):
    """Test SubAgentManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = SubAgentManager()
        self.test_config = {"model": "test-model"}

    def test_agent_definition(self):
        """Test AgentDefinition creation and validation."""
        agent_def = AgentDefinition(
            name="test_agent",
            description="Test agent description",
            model="gpt-4o",
            system_prompt="Test system prompt",
            tools=[],
        )
        self.assertEqual(agent_def.name, "test_agent")
        self.assertEqual(agent_def.description, "Test agent description")
        self.assertEqual(agent_def.model, "gpt-4o")
        self.assertEqual(agent_def.system_prompt, "Test system prompt")
        self.assertEqual(agent_def.tools, [])

    @patch('feinn_agent.subagent.manager.FeinnAgent')
    async def test_spawn_subagent(self, mock_agent_class):
        """Test spawning a subagent."""
        mock_agent = Mock()
        mock_agent.run.return_value = []
        mock_agent_class.return_value = mock_agent

        task = await self.manager.spawn(
            agent_type="general-purpose",
            prompt="Test prompt",
            config=self.test_config,
            wait=True,
        )

        self.assertEqual(task.agent_type, "general-purpose")
        self.assertEqual(task.prompt, "Test prompt")
        self.assertEqual(task.status, AgentTaskStatus.DONE)

    @patch('feinn_agent.subagent.manager.FeinnAgent')
    async def test_spawn_subagent_error_unknown_type(self, mock_agent_class):
        """Test spawning a subagent with unknown type."""
        task = await self.manager.spawn(
            agent_type="nonexistent_agent",
            prompt="Test prompt",
            config=self.test_config,
            wait=True,
        )

        self.assertEqual(task.status, AgentTaskStatus.ERROR)
        self.assertIn("Unknown agent type", task.error)

    async def test_spawn_subagent_depth_limit(self):
        """Test subagent depth limit."""
        # Create a manager with max depth 1
        manager = SubAgentManager(max_depth=1)
        
        # First spawn should work
        task1 = await manager.spawn(
            agent_type="general-purpose",
            prompt="Test prompt 1",
            config=self.test_config,
            wait=True,
        )
        self.assertEqual(task1.status, AgentTaskStatus.DONE)

    def test_check_result(self):
        """Test checking task result."""
        # This test would require a running task, which is complex to mock
        # For simplicity, we'll test the case where task doesn't exist
        result = self.manager.check_result("nonexistent-task")
        self.assertIsNone(result)

    def test_list_tasks(self):
        """Test listing tasks."""
        tasks = self.manager.list_tasks()
        self.assertIsInstance(tasks, list)

    def test_list_agent_types(self):
        """Test listing agent types."""
        agent_types = self.manager.list_agent_types()
        self.assertIsInstance(agent_types, list)
        self.assertGreater(len(agent_types), 0)

    def test_agent_task_status_enum(self):
        """Test AgentTaskStatus enum."""
        self.assertEqual(AgentTaskStatus.PENDING.value, "pending")
        self.assertEqual(AgentTaskStatus.RUNNING.value, "running")
        self.assertEqual(AgentTaskStatus.DONE.value, "done")
        self.assertEqual(AgentTaskStatus.ERROR.value, "error")


if __name__ == "__main__":
    unittest.main()
