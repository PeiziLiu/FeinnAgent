"""Tests for FeinnAgent task functionality."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from feinn_agent.task.store import Task, TaskStatus, task_create, task_update, task_list, task_get


class TestTask(unittest.TestCase):
    """Test Task functionality."""

    def test_task_creation(self):
        """Test Task creation."""
        task = Task(
            id="test-task-1",
            subject="Test Task",
            description="Test description",
            status=TaskStatus.PENDING,
            blocks=["task-2"],
            blocked_by=["task-3"],
        )
        self.assertEqual(task.id, "test-task-1")
        self.assertEqual(task.subject, "Test Task")
        self.assertEqual(task.description, "Test description")
        self.assertEqual(task.status, TaskStatus.PENDING)
        self.assertEqual(task.blocks, ["task-2"])
        self.assertEqual(task.blocked_by, ["task-3"])

    def test_task_to_dict(self):
        """Test Task.to_dict() method."""
        task = Task(
            id="test-task-1",
            subject="Test Task",
            description="Test description",
            status=TaskStatus.PENDING,
        )
        task_dict = task.to_dict()
        self.assertEqual(task_dict["id"], "test-task-1")
        self.assertEqual(task_dict["subject"], "Test Task")
        self.assertEqual(task_dict["description"], "Test description")
        self.assertEqual(task_dict["status"], "pending")

    def test_task_from_dict(self):
        """Test Task.from_dict() method."""
        task_dict = {
            "id": "test-task-1",
            "subject": "Test Task",
            "description": "Test description",
            "status": "pending",
        }
        task = Task.from_dict(task_dict)
        self.assertEqual(task.id, "test-task-1")
        self.assertEqual(task.subject, "Test Task")
        self.assertEqual(task.description, "Test description")
        self.assertEqual(task.status, TaskStatus.PENDING)


class TestTaskFunctions(unittest.TestCase):
    """Test task functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)

    def test_task_create(self):
        """Test creating a task."""
        result = task_create(
            subject="Test Task",
            description="Test description",
        )
        self.assertIn("Task created", result)

    def test_task_list(self):
        """Test listing tasks."""
        # Create tasks
        task_create(subject="Task 1")
        task_create(subject="Task 2")
        
        result = task_list()
        self.assertIn("Task 1", result)
        self.assertIn("Task 2", result)

    def test_task_get(self):
        """Test getting a task."""
        # Create task
        create_result = task_create(subject="Test Task")
        task_id = create_result.split("#")[-1].strip()
        
        # Get task
        result = task_get(task_id)
        self.assertIn("Test Task", result)

    def test_task_update(self):
        """Test updating a task."""
        # Create task
        create_result = task_create(subject="Test Task")
        task_id = create_result.split("#")[-1].strip()
        
        # Update task
        update_result = task_update(
            task_id=task_id,
            subject="Updated Task",
            status="in_progress",
        )
        
        self.assertIn("Task #" + task_id + " updated", update_result)

    def test_task_create_with_dependencies(self):
        """Test creating a task with dependencies."""
        # Create tasks
        task1_result = task_create(subject="Task 1")
        task1_id = task1_result.split("#")[-1].strip()
        
        task2_result = task_create(subject="Task 2")
        task2_id = task2_result.split("#")[-1].strip()
        
        # Create task with dependencies
        task3_result = task_create(
            subject="Task 3",
            blocked_by=[task1_id, task2_id],
        )
        
        self.assertIn("Task created", task3_result)

    def test_task_create_invalid_dependency(self):
        """Test creating a task with invalid dependency."""
        result = task_create(
            subject="Task with invalid dependency",
            blocked_by=["nonexistent"],
        )
        self.assertIn("Error", result)


if __name__ == "__main__":
    unittest.main()
