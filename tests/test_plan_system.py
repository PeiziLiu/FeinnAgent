"""Tests for FeinnAgent execution plan system."""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from feinn_agent.interrupt import (
    set_interrupt,
    clear_interrupt,
    is_interrupted,
    get_interrupt_reason,
    get_interrupt_info,
)
from feinn_agent.plan import (
    PlanManager,
    Plan,
    PlanStep,
    PlanStatus,
    StepStatus,
)
from feinn_agent.display import KawaiiDisplay, DiffDisplay, ToolPreview


class TestInterruptSignal(unittest.TestCase):
    """Test interrupt signal functionality."""

    def setUp(self):
        """Clear interrupt before each test."""
        clear_interrupt()

    def tearDown(self):
        """Clear interrupt after each test."""
        clear_interrupt()

    def test_set_interrupt(self):
        """Test setting interrupt signal."""
        set_interrupt("Test interrupt")
        self.assertTrue(is_interrupted())
        self.assertEqual(get_interrupt_reason(), "Test interrupt")

    def test_clear_interrupt(self):
        """Test clearing interrupt signal."""
        set_interrupt("Test")
        clear_interrupt()
        self.assertFalse(is_interrupted())
        self.assertIsNone(get_interrupt_reason())

    def test_get_interrupt_info(self):
        """Test getting full interrupt info."""
        set_interrupt("Test reason")
        info = get_interrupt_info()
        self.assertTrue(info["is_interrupted"])
        self.assertEqual(info["reason"], "Test reason")
        self.assertIsNotNone(info["timestamp"])

    def test_multiple_set_interrupt(self):
        """Test setting interrupt multiple times."""
        set_interrupt("First")
        first_timestamp = get_interrupt_info()["timestamp"]
        set_interrupt("Second")
        second_timestamp = get_interrupt_info()["timestamp"]
        self.assertEqual(get_interrupt_reason(), "Second")


class TestPlanManager(unittest.TestCase):
    """Test plan management functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.plans_dir = Path(self.temp_dir) / "plans"
        self.plans_dir.mkdir()
        self.manager = PlanManager(plans_dir=self.plans_dir)

    def test_create_plan(self):
        """Test creating a new plan."""
        plan = self.manager.create_plan(
            task="Implement login feature",
            title="Login Feature",
            goal="Implement user authentication",
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan.title, "Login Feature")
        self.assertEqual(plan.status, PlanStatus.DRAFT)

    def test_create_plan_with_steps(self):
        """Test creating a plan with steps."""
        steps = [
            {"description": "Create login form", "expected_result": "HTML form"},
            {"description": "Add validation", "expected_result": "Validated form"},
        ]
        plan = self.manager.create_plan(
            task="Implement form",
            steps=steps,
        )
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].description, "Create login form")
        self.assertEqual(plan.steps[0].status, StepStatus.PENDING)

    def test_get_plan(self):
        """Test retrieving a plan."""
        created = self.manager.create_plan(task="Test plan")
        retrieved = self.manager.get_plan(created.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, created.id)

    def test_list_plans(self):
        """Test listing plans."""
        self.manager.create_plan(task="Plan 1")
        self.manager.create_plan(task="Plan 2")
        plans = self.manager.list_plans()
        self.assertEqual(len(plans), 2)

    def test_update_plan(self):
        """Test updating a plan."""
        plan = self.manager.create_plan(task="Original task")
        plan.title = "Updated title"
        updated = self.manager.update_plan(plan)
        self.assertEqual(updated.title, "Updated title")

    def test_approve_plan(self):
        """Test approving a plan."""
        plan = self.manager.create_plan(task="Test")
        approved = self.manager.approve_plan(plan.id)
        self.assertEqual(approved.status, PlanStatus.APPROVED)

    def test_start_plan(self):
        """Test starting a plan."""
        plan = self.manager.create_plan(task="Test")
        started = self.manager.start_plan(plan.id)
        self.assertEqual(started.status, PlanStatus.IN_PROGRESS)

    def test_complete_plan(self):
        """Test completing a plan."""
        plan = self.manager.create_plan(task="Test")
        completed = self.manager.complete_plan(plan.id)
        self.assertEqual(completed.status, PlanStatus.COMPLETED)

    def test_abort_plan(self):
        """Test aborting a plan."""
        plan = self.manager.create_plan(task="Test")
        aborted = self.manager.abort_plan(plan.id)
        self.assertEqual(aborted.status, PlanStatus.ABORTED)

    def test_delete_plan(self):
        """Test deleting a plan."""
        plan = self.manager.create_plan(task="Test")
        deleted = self.manager.delete_plan(plan.id)
        self.assertTrue(deleted)
        self.assertIsNone(self.manager.get_plan(plan.id))

    def test_update_step_status(self):
        """Test updating a step status."""
        steps = [{"description": "Test step"}]
        plan = self.manager.create_plan(task="Test", steps=steps)
        updated = self.manager.update_step_status(
            plan.id,
            "step-1",
            StepStatus.COMPLETED,
            "Actual result",
        )
        self.assertEqual(updated.steps[0].status, StepStatus.COMPLETED)
        self.assertEqual(updated.steps[0].actual_result, "Actual result")


class TestKawaiiDisplay(unittest.TestCase):
    """Test Kawaii display functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.display = KawaiiDisplay(use_color=False)

    def test_show_status(self):
        """Test showing status message."""
        msg = self.display.show_status("thinking", "Processing...")
        self.assertIn("🤔", msg)
        self.assertIn("Processing...", msg)

    def test_show_progress(self):
        """Test showing progress bar."""
        progress = self.display.show_progress(50, 100)
        self.assertIn("50%", progress)
        self.assertIn("[", progress)
        self.assertIn("]", progress)

    def test_show_tool_start(self):
        """Test showing tool start."""
        start = self.display.show_tool_start("read_file", {"path": "test.py"})
        self.assertIn("read_file", start)

    def test_show_tool_end_success(self):
        """Test showing successful tool end."""
        end = self.display.show_tool_end("read_file", success=True)
        self.assertIn("read_file", end)

    def test_show_tool_end_error(self):
        """Test showing failed tool end."""
        end = self.display.show_tool_end("write_file", success=False, error="Permission denied")
        self.assertIn("write_file", end)

    def test_show_plan_step(self):
        """Test showing plan step."""
        step = self.display.show_plan_step(1, "Create login form", status="pending")
        self.assertIn("Create login form", step)

    def test_show_checkpoint(self):
        """Test showing checkpoint info."""
        ckpt = self.display.show_checkpoint("ckpt-001", "Before changes", 10)
        self.assertIn("ckpt-001", ckpt)

    def test_show_interrupt(self):
        """Test showing interrupt message."""
        intr = self.display.show_interrupt("User cancel")
        self.assertIn("interrupted", intr)

    def test_show_welcome(self):
        """Test showing welcome banner."""
        welcome = self.display.show_welcome("siliconflow/Pro/GLM-5.1")
        self.assertIn("FeinnAgent", welcome)


class TestDiffDisplay(unittest.TestCase):
    """Test diff display functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.diff = DiffDisplay(use_color=False)

    def test_format_unified_diff(self):
        """Test formatting unified diff."""
        old = ["line 1", "line 2", "line 3"]
        new = ["line 1", "modified line 2", "line 3"]
        result = self.diff.format_unified_diff(old, new)
        self.assertIn("---", result)
        self.assertIn("+++", result)

    def test_show_changes_summary(self):
        """Test showing changes summary."""
        summary = self.diff.show_changes_summary(added=5, modified=3, deleted=1)
        self.assertIn("+5", summary)
        self.assertIn("~3", summary)
        self.assertIn("-1", summary)


class TestToolPreview(unittest.TestCase):
    """Test tool preview functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.preview = ToolPreview(use_color=False)

    def test_preview_tool_call(self):
        """Test previewing tool call."""
        result = self.preview.preview_tool_call(
            "write_file",
            {"path": "test.py", "content": "print('hello')"},
        )
        self.assertIn("write_file", result)
        self.assertIn("path", result)

    def test_format_value_string(self):
        """Test formatting string value."""
        result = self.preview._format_value("short string")
        self.assertIn("short string", result)

    def test_format_value_long_string(self):
        """Test formatting long string."""
        long_str = "x" * 100
        result = self.preview._format_value(long_str)
        self.assertIn("...", result)


if __name__ == "__main__":
    unittest.main()
