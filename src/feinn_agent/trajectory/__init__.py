"""Trajectory recording and analysis for FeinnAgent.

Records the complete execution history including turns, tool calls,
tokens, checkpoints, and interrupts for analysis and replay.
"""

import gzip
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

TRAJECTORY_BASE = Path.home() / ".feinn" / "trajectories"


@dataclass
class ToolCallRecord:
    """Record of a tool call."""
    id: str
    name: str
    arguments: dict
    result: Optional[str] = None
    duration_ms: int = 0
    error: Optional[str] = None


@dataclass
class TurnRecord:
    """Record of a single agent turn."""
    turn: int
    user_message: dict
    assistant_response: dict
    tool_calls: list[ToolCallRecord]
    tokens: dict
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CheckpointRecord:
    """Record of a checkpoint creation."""
    id: str
    created_at: datetime
    commit_id: str
    message: str


@dataclass
class InterruptRecord:
    """Record of an interrupt."""
    turn: int
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TrajectoryStats:
    """Statistics for a trajectory."""
    total_turns: int
    total_tokens: dict
    total_duration_ms: int
    tool_calls: dict
    checkpoints_count: int
    interrupts_count: int


@dataclass
class Trajectory:
    """Complete trajectory record."""
    version: str = "1.0"
    session_id: str = ""
    agent_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    status: str = "in_progress"
    config: dict = field(default_factory=dict)
    turns: list[TurnRecord] = field(default_factory=list)
    checkpoints: list[CheckpointRecord] = field(default_factory=list)
    interrupts: list[InterruptRecord] = field(default_factory=list)
    error: Optional[str] = None


class TrajectoryRecorder:
    """Records agent execution trajectories."""
    
    def __init__(
        self,
        session_id: str,
        trajectories_dir: Optional[Path] = None,
        compression: bool = True,
    ):
        self.trajectories_dir = trajectories_dir or TRAJECTORY_BASE
        self.session_id = session_id
        self.compression = compression
        self.trajectory = Trajectory(session_id=session_id)
        self._start_time = time.time()
        self._ensure_dir()
    
    def _ensure_dir(self) -> None:
        """Ensure trajectory directory exists."""
        self.trajectories_dir.mkdir(parents=True, exist_ok=True)
    
    def set_config(self, config: dict) -> None:
        """Set agent configuration for this trajectory."""
        self.trajectory.config = config
    
    def set_agent_id(self, agent_id: str) -> None:
        """Set agent ID."""
        self.trajectory.agent_id = agent_id
    
    def record_turn(
        self,
        turn: int,
        user_message: dict,
        assistant_response: dict,
        tool_calls: list[ToolCallRecord],
        tokens: dict,
        duration_ms: int = 0,
    ) -> None:
        """Record a turn.
        
        Args:
            turn: Turn number
            user_message: User message content
            assistant_response: Assistant response
            tool_calls: List of tool calls made
            tokens: Token usage
            duration_ms: Turn duration in milliseconds
        """
        turn_record = TurnRecord(
            turn=turn,
            user_message=user_message,
            assistant_response=assistant_response,
            tool_calls=tool_calls,
            tokens=tokens,
            duration_ms=duration_ms,
        )
        self.trajectory.turns.append(turn_record)
    
    def record_checkpoint(
        self,
        checkpoint_id: str,
        commit_id: str,
        message: str = "",
    ) -> None:
        """Record a checkpoint creation.
        
        Args:
            checkpoint_id: Checkpoint ID
            commit_id: Git commit ID
            message: Checkpoint message
        """
        record = CheckpointRecord(
            id=checkpoint_id,
            created_at=datetime.now(),
            commit_id=commit_id,
            message=message,
        )
        self.trajectory.checkpoints.append(record)
    
    def record_interrupt(
        self,
        turn: int,
        reason: str = "",
    ) -> None:
        """Record an interrupt.
        
        Args:
            turn: Turn number when interrupted
            reason: Reason for interrupt
        """
        record = InterruptRecord(
            turn=turn,
            reason=reason,
        )
        self.trajectory.interrupts.append(record)
    
    def complete(self, status: str = "completed", error: Optional[str] = None) -> None:
        """Mark trajectory as complete.
        
        Args:
            status: Completion status ('completed', 'interrupted', 'error')
            error: Optional error message
        """
        self.trajectory.completed_at = datetime.now()
        self.trajectory.status = status
        self.trajectory.error = error
    
    def get_stats(self) -> TrajectoryStats:
        """Get trajectory statistics.
        
        Returns:
            TrajectoryStats object
        """
        total_input = sum(t.tokens.get("input", 0) for t in self.trajectory.turns)
        total_output = sum(t.tokens.get("output", 0) for t in self.trajectory.turns)
        total_duration = sum(t.duration_ms for t in self.trajectory.turns)
        
        tool_call_counts: dict[str, int] = {}
        for turn in self.trajectory.turns:
            for tc in turn.tool_calls:
                tool_call_counts[tc.name] = tool_call_counts.get(tc.name, 0) + 1
        
        return TrajectoryStats(
            total_turns=len(self.trajectory.turns),
            total_tokens={"input": total_input, "output": total_output},
            total_duration_ms=total_duration,
            tool_calls=tool_call_counts,
            checkpoints_count=len(self.trajectory.checkpoints),
            interrupts_count=len(self.trajectory.interrupts),
        )
    
    def to_dict(self) -> dict:
        """Convert trajectory to dictionary.
        
        Returns:
            Dictionary representation of trajectory
        """
        data = {
            "version": self.trajectory.version,
            "session_id": self.trajectory.session_id,
            "agent_id": self.trajectory.agent_id,
            "created_at": self.trajectory.created_at.isoformat(),
            "completed_at": self.trajectory.completed_at.isoformat() if self.trajectory.completed_at else None,
            "status": self.trajectory.status,
            "config": self.trajectory.config,
            "turns": [],
            "checkpoints": [asdict(c) for c in self.trajectory.checkpoints],
            "interrupts": [asdict(i) for i in self.trajectory.interrupts],
            "error": self.trajectory.error,
        }
        
        for turn in self.trajectory.turns:
            turn_data = {
                "turn": turn.turn,
                "user_message": turn.user_message,
                "assistant": turn.assistant_response,
                "tool_results": [
                    {
                        "tool_call_id": tc.id,
                        "tool_name": tc.name,
                        "result": tc.result,
                        "duration_ms": tc.duration_ms,
                        "error": tc.error,
                    }
                    for tc in turn.tool_calls
                ],
                "tokens": turn.tokens,
                "duration_ms": turn.duration_ms,
                "timestamp": turn.timestamp.isoformat(),
            }
            data["turns"].append(turn_data)
        
        return data
    
    async def save(self) -> Path:
        """Save trajectory to file.
        
        Returns:
            Path to saved file
        """
        data = self.to_dict()
        filename = f"{self.session_id}.json"
        
        if self.compression:
            filename += ".gz"
            filepath = self.trajectories_dir / filename
            with gzip.open(filepath, "wt", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            filepath = self.trajectories_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved trajectory to {filepath}")
        return filepath
    
    @staticmethod
    def load(filepath: Path) -> Trajectory:
        """Load trajectory from file.
        
        Args:
            filepath: Path to trajectory file
            
        Returns:
            Loaded Trajectory object
        """
        if filepath.suffix == ".gz":
            with gzip.open(filepath, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        trajectory = Trajectory(
            version=data.get("version", "1.0"),
            session_id=data.get("session_id", ""),
            agent_id=data.get("agent_id", ""),
            status=data.get("status", "unknown"),
            config=data.get("config", {}),
        )
        
        if data.get("created_at"):
            trajectory.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("completed_at"):
            trajectory.completed_at = datetime.fromisoformat(data["completed_at"])
        
        return trajectory
    
    @staticmethod
    def list_trajectories(trajectories_dir: Optional[Path] = None) -> list[Path]:
        """List all trajectory files.
        
        Args:
            trajectories_dir: Directory to search
            
        Returns:
            List of trajectory file paths
        """
        dir_path = trajectories_dir or TRAJECTORY_BASE
        if not dir_path.exists():
            return []
        
        return sorted(
            list(dir_path.glob("*.json")) + list(dir_path.glob("*.json.gz")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )


class TrajectoryAnalyzer:
    """Analyzes trajectory data."""
    
    @staticmethod
    def analyze_efficiency(trajectory: Trajectory) -> dict:
        """Analyze execution efficiency.
        
        Args:
            trajectory: Trajectory to analyze
            
        Returns:
            Analysis results
        """
        stats = {
            "total_turns": len(trajectory.turns),
            "avg_turn_duration_ms": 0,
            "slowest_turns": [],
            "tool_usage": {},
        }
        
        if not trajectory.turns:
            return stats
        
        durations = [t.duration_ms for t in trajectory.turns]
        stats["avg_turn_duration_ms"] = sum(durations) / len(durations)
        
        # Find slowest turns
        sorted_turns = sorted(
            enumerate(trajectory.turns),
            key=lambda x: x[1].duration_ms,
            reverse=True,
        )
        stats["slowest_turns"] = [
            {"turn": t.turn, "duration_ms": t.duration_ms}
            for _, t in sorted_turns[:3]
        ]
        
        # Tool usage
        tool_usage: dict[str, int] = {}
        for turn in trajectory.turns:
            for tc in turn.tool_calls:
                tool_usage[tc.name] = tool_usage.get(tc.name, 0) + 1
        stats["tool_usage"] = tool_usage
        
        return stats
    
    @staticmethod
    def compare(trajectory1: Trajectory, trajectory2: Trajectory) -> dict:
        """Compare two trajectories.
        
        Args:
            trajectory1: First trajectory
            trajectory2: Second trajectory
            
        Returns:
            Comparison results
        """
        stats1 = {
            "total_turns": len(trajectory1.turns),
            "total_tokens": sum(t.tokens.get("output", 0) for t in trajectory1.turns),
        }
        stats2 = {
            "total_turns": len(trajectory2.turns),
            "total_tokens": sum(t.tokens.get("output", 0) for t in trajectory2.turns),
        }
        
        return {
            "trajectory1": stats1,
            "trajectory2": stats2,
            "turn_diff": stats1["total_turns"] - stats2["total_turns"],
            "token_diff": stats1["total_tokens"] - stats2["total_tokens"],
        }
