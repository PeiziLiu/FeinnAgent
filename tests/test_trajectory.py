"""Tests for FeinnAgent trajectory functionality."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from feinn_agent.trajectory import (
    TrajectoryRecorder,
    Trajectory,
    ToolCallRecord,
    TurnRecord,
    CheckpointRecord,
    InterruptRecord,
    TrajectoryStats,
    TrajectoryAnalyzer,
)


class TestTrajectoryRecorder(unittest.TestCase):
    """Test TrajectoryRecorder functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.trajectories_dir = Path(self.temp_dir) / "trajectories"
        self.session_id = "test-session-1"
        self.recorder = TrajectoryRecorder(
            session_id=self.session_id,
            trajectories_dir=self.trajectories_dir,
            compression=False,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_set_config(self):
        """Test setting agent configuration."""
        config = {"model": "gpt-4o", "max_iterations": 50}
        self.recorder.set_config(config)
        self.assertEqual(self.recorder.trajectory.config, config)

    def test_set_agent_id(self):
        """Test setting agent ID."""
        agent_id = "test-agent-1"
        self.recorder.set_agent_id(agent_id)
        self.assertEqual(self.recorder.trajectory.agent_id, agent_id)

    def test_record_turn(self):
        """Test recording a turn."""
        tool_calls = [
            ToolCallRecord(
                id="call-1",
                name="read_file",
                arguments={"path": "test.py"},
                result="print('hello')",
                duration_ms=100,
            )
        ]
        
        self.recorder.record_turn(
            turn=1,
            user_message={"content": "Test query"},
            assistant_response={"text": "Test response"},
            tool_calls=tool_calls,
            tokens={"input": 100, "output": 200},
            duration_ms=500,
        )
        
        self.assertEqual(len(self.recorder.trajectory.turns), 1)
        turn = self.recorder.trajectory.turns[0]
        self.assertEqual(turn.turn, 1)
        self.assertEqual(turn.tokens, {"input": 100, "output": 200})

    def test_record_checkpoint(self):
        """Test recording a checkpoint."""
        self.recorder.record_checkpoint(
            checkpoint_id="ckpt-1",
            commit_id="abc123",
            message="Test checkpoint",
        )
        
        self.assertEqual(len(self.recorder.trajectory.checkpoints), 1)
        checkpoint = self.recorder.trajectory.checkpoints[0]
        self.assertEqual(checkpoint.id, "ckpt-1")
        self.assertEqual(checkpoint.commit_id, "abc123")

    def test_record_interrupt(self):
        """Test recording an interrupt."""
        self.recorder.record_interrupt(
            turn=1,
            reason="User interrupt",
        )
        
        self.assertEqual(len(self.recorder.trajectory.interrupts), 1)
        interrupt = self.recorder.trajectory.interrupts[0]
        self.assertEqual(interrupt.turn, 1)
        self.assertEqual(interrupt.reason, "User interrupt")

    def test_complete(self):
        """Test completing a trajectory."""
        self.recorder.complete(status="completed", error=None)
        self.assertEqual(self.recorder.trajectory.status, "completed")
        self.assertIsNotNone(self.recorder.trajectory.completed_at)

    def test_get_stats(self):
        """Test getting trajectory statistics."""
        # Record a turn
        tool_calls = [
            ToolCallRecord(
                id="call-1",
                name="read_file",
                arguments={"path": "test.py"},
                result="print('hello')",
            )
        ]
        
        self.recorder.record_turn(
            turn=1,
            user_message={"content": "Test query"},
            assistant_response={"text": "Test response"},
            tool_calls=tool_calls,
            tokens={"input": 100, "output": 200},
        )
        
        stats = self.recorder.get_stats()
        self.assertIsInstance(stats, TrajectoryStats)
        self.assertEqual(stats.total_turns, 1)
        self.assertEqual(stats.total_tokens, {"input": 100, "output": 200})
        self.assertEqual(stats.tool_calls, {"read_file": 1})

    async def test_save(self):
        """Test saving trajectory to file."""
        # Record some data
        self.recorder.record_turn(
            turn=1,
            user_message={"content": "Test query"},
            assistant_response={"text": "Test response"},
            tool_calls=[],
            tokens={"input": 100, "output": 200},
        )
        
        # Save trajectory
        filepath = await self.recorder.save()
        self.assertTrue(filepath.exists())
        self.assertIn(self.session_id, str(filepath))

    def test_list_trajectories(self):
        """Test listing trajectories."""
        trajectories = TrajectoryRecorder.list_trajectories(
            trajectories_dir=self.trajectories_dir
        )
        self.assertIsInstance(trajectories, list)


class TestTrajectoryAnalyzer(unittest.TestCase):
    """Test TrajectoryAnalyzer functionality."""

    def test_analyze_efficiency(self):
        """Test analyzing trajectory efficiency."""
        trajectory = Trajectory()
        
        # Add some turns
        trajectory.turns.append(
            TurnRecord(
                turn=1,
                user_message={"content": "Test 1"},
                assistant_response={"text": "Response 1"},
                tool_calls=[],
                tokens={"input": 100, "output": 200},
                duration_ms=500,
            )
        )
        
        trajectory.turns.append(
            TurnRecord(
                turn=2,
                user_message={"content": "Test 2"},
                assistant_response={"text": "Response 2"},
                tool_calls=[],
                tokens={"input": 150, "output": 250},
                duration_ms=1000,
            )
        )
        
        analysis = TrajectoryAnalyzer.analyze_efficiency(trajectory)
        self.assertIsInstance(analysis, dict)
        self.assertEqual(analysis["total_turns"], 2)
        self.assertIn("avg_turn_duration_ms", analysis)
        self.assertIn("slowest_turns", analysis)
        self.assertIn("tool_usage", analysis)

    def test_compare(self):
        """Test comparing two trajectories."""
        trajectory1 = Trajectory()
        trajectory1.turns.append(
            TurnRecord(
                turn=1,
                user_message={"content": "Test 1"},
                assistant_response={"text": "Response 1"},
                tool_calls=[],
                tokens={"input": 100, "output": 200},
            )
        )
        
        trajectory2 = Trajectory()
        trajectory2.turns.append(
            TurnRecord(
                turn=1,
                user_message={"content": "Test 1"},
                assistant_response={"text": "Response 1"},
                tool_calls=[],
                tokens={"input": 150, "output": 250},
            )
        )
        
        comparison = TrajectoryAnalyzer.compare(trajectory1, trajectory2)
        self.assertIsInstance(comparison, dict)
        self.assertIn("trajectory1", comparison)
        self.assertIn("trajectory2", comparison)
        self.assertIn("turn_diff", comparison)
        self.assertIn("token_diff", comparison)


if __name__ == "__main__":
    unittest.main()
