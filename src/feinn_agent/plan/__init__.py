"""Plan management for FeinnAgent.

Provides execution plan creation, editing, and execution capabilities.
Plans are stored as Markdown files with structured metadata.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PLAN_BASE = Path.home() / ".feinn" / "plans"


class PlanStatus(Enum):
    """Plan status enum."""
    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"


class StepStatus(Enum):
    """Step status enum."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class PlanStep:
    """Represents a single step in a plan."""
    id: str
    order: int
    description: str
    expected_result: str = ""
    dependencies: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    actual_result: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class Plan:
    """Represents an execution plan."""
    id: str
    title: str
    task: str
    goal: str
    steps: list[PlanStep]
    status: PlanStatus = PlanStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


@dataclass
class PlanResult:
    """Result of executing a plan."""
    plan_id: str
    success: bool
    completed_steps: int
    total_steps: int
    message: str


class PlanManager:
    """Manages execution plans."""
    
    def __init__(self, plans_dir: Optional[Path] = None):
        self.plans_dir = plans_dir or PLAN_BASE
        self._ensure_dir()
    
    def _ensure_dir(self) -> None:
        """Ensure plans directory exists."""
        self.plans_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_id(self) -> str:
        """Generate a unique plan ID."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_uuid = uuid.uuid4().hex[:8]
        return f"plan-{timestamp}-{short_uuid}"
    
    def _get_plan_path(self, plan_id: str) -> Path:
        """Get the file path for a plan."""
        return self.plans_dir / f"{plan_id}.md"
    
    def create_plan(
        self,
        task: str,
        title: str = "",
        goal: str = "",
        steps: Optional[list[dict]] = None,
    ) -> Plan:
        """Create a new execution plan.
        
        Args:
            task: The task description
            title: Plan title
            goal: Plan goal
            steps: Optional list of step dicts
            
        Returns:
            Created Plan object
        """
        plan_id = self._generate_id()
        
        if not title:
            title = task[:50] + "..." if len(task) > 50 else task
        
        plan_steps = []
        if steps:
            for i, step_dict in enumerate(steps):
                step = PlanStep(
                    id=f"step-{i+1}",
                    order=i + 1,
                    description=step_dict.get("description", ""),
                    expected_result=step_dict.get("expected_result", ""),
                    dependencies=step_dict.get("dependencies", []),
                )
                plan_steps.append(step)
        
        plan = Plan(
            id=plan_id,
            title=title,
            task=task,
            goal=goal,
            steps=plan_steps,
        )
        
        self.save_plan(plan)
        return plan
    
    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            Plan object or None if not found
        """
        plan_path = self._get_plan_path(plan_id)
        if not plan_path.exists():
            return None
        
        return self._parse_plan(plan_path)
    
    def list_plans(self) -> list[Plan]:
        """List all plans.
        
        Returns:
            List of Plan objects sorted by creation time (newest first)
        """
        plans = []
        
        for plan_path in self.plans_dir.glob("*.md"):
            plan = self._parse_plan(plan_path)
            if plan:
                plans.append(plan)
        
        plans.sort(key=lambda p: p.created_at, reverse=True)
        return plans
    
    def update_plan(self, plan: Plan) -> Plan:
        """Update an existing plan.
        
        Args:
            plan: Plan to update
            
        Returns:
            Updated Plan object
        """
        plan.updated_at = datetime.now()
        self.save_plan(plan)
        return plan
    
    def delete_plan(self, plan_id: str) -> bool:
        """Delete a plan.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            True if deleted, False if not found
        """
        plan_path = self._get_plan_path(plan_id)
        if not plan_path.exists():
            return False
        
        plan_path.unlink()
        return True
    
    def save_plan(self, plan: Plan) -> None:
        """Save a plan to file.
        
        Args:
            plan: Plan to save
        """
        plan_path = self._get_plan_path(plan.id)
        content = self._serialize_plan(plan)
        plan_path.write_text(content, encoding="utf-8")
        logger.info(f"Saved plan {plan.id} to {plan_path}")
    
    def _serialize_plan(self, plan: Plan) -> str:
        """Serialize a plan to Markdown format.
        
        Args:
            plan: Plan to serialize
            
        Returns:
            Markdown string
        """
        lines = [
            "---",
            f"id: {plan.id}",
            f"title: {plan.title}",
            f"status: {plan.status.value}",
            f"created_at: {plan.created_at.isoformat()}",
            f"updated_at: {plan.updated_at.isoformat()}",
            "---",
            "",
            f"# {plan.title}",
            "",
            "## 任务目标",
            plan.goal or plan.task,
            "",
            "## 执行步骤",
            "",
        ]
        
        for step in plan.steps:
            status_icon = {
                StepStatus.PENDING: "[ ]",
                StepStatus.IN_PROGRESS: "[~]",
                StepStatus.COMPLETED: "[x]",
                StepStatus.SKIPPED: "[-]",
                StepStatus.FAILED: "[!]",
            }.get(step.status, "[ ]")
            
            lines.append(f"### {status_icon} 步骤 {step.order}: {step.description}")
            
            if step.expected_result:
                lines.append(f"- 预期结果：{step.expected_result}")
            
            if step.dependencies:
                lines.append(f"- 依赖：{', '.join(step.dependencies)}")
            
            if step.actual_result:
                lines.append(f"- 实际结果：{step.actual_result}")
            
            if step.notes:
                lines.append(f"- 备注：{step.notes}")
            
            lines.append("")
        
        lines.extend([
            "## 元数据",
            f"- 创建时间：{plan.created_at.isoformat()}",
            f"- 最后更新：{plan.updated_at.isoformat()}",
            f"- 状态：{plan.status.value}",
            f"- 步骤数：{len(plan.steps)}",
        ])
        
        return "\n".join(lines)
    
    def _parse_plan(self, plan_path: Path) -> Optional[Plan]:
        """Parse a plan from Markdown file.
        
        Args:
            plan_path: Path to plan file
            
        Returns:
            Plan object or None if parsing failed
        """
        try:
            content = plan_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            
            # Parse frontmatter
            metadata = {}
            in_frontmatter = False
            frontmatter_lines = []
            content_lines = []
            
            for line in lines:
                if line.strip() == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                    else:
                        in_frontmatter = False
                elif in_frontmatter:
                    frontmatter_lines.append(line)
                else:
                    content_lines.append(line)
            
            for fm_line in frontmatter_lines:
                if ":" in fm_line:
                    key, value = fm_line.split(":", 1)
                    metadata[key.strip()] = value.strip()
            
            # Extract plan info
            plan_id = metadata.get("id", plan_path.stem)
            title = metadata.get("title", "Untitled")
            status_str = metadata.get("status", "draft")
            status = PlanStatus(status_str)
            
            created_at_str = metadata.get("created_at")
            updated_at_str = metadata.get("updated_at")
            created_at = datetime.fromisoformat(created_at_str) if created_at_str else datetime.now()
            updated_at = datetime.fromisoformat(updated_at_str) if updated_at_str else datetime.now()
            
            # Parse content
            content_text = "\n".join(content_lines)
            
            # Extract goal (first line after ## 任务目标)
            goal = ""
            goal_section = content_text.split("## 任务目标")
            if len(goal_section) > 1:
                goal_parts = goal_section[1].split("##")
                goal = goal_parts[0].strip()
            
            # Extract task from goal if not separate
            task = goal
            
            # Parse steps
            steps = []
            import re
            step_pattern = re.compile(r"### \[([x~\- ])\] 步骤 (\d+): (.+)")
            
            # Find all step lines by looking for lines starting with ###
            for line in content_lines:
                match = step_pattern.match(line)
                if match:
                    status_char = match.group(1)
                    order = int(match.group(2))
                    description = match.group(3).strip()
                    
                    status_map = {
                        "x": StepStatus.COMPLETED,
                        "~": StepStatus.IN_PROGRESS,
                        "-": StepStatus.SKIPPED,
                        "!": StepStatus.FAILED,
                    }
                    status = status_map.get(status_char, StepStatus.PENDING)
                    
                    step = PlanStep(
                        id=f"step-{order}",
                        order=order,
                        description=description,
                        status=status,
                    )
                    steps.append(step)
            
            return Plan(
                id=plan_id,
                title=title,
                task=task,
                goal=goal,
                steps=steps,
                status=status,
                created_at=created_at,
                updated_at=updated_at,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to parse plan {plan_path}: {e}")
            return None
    
    def approve_plan(self, plan_id: str) -> Optional[Plan]:
        """Approve a plan for execution.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            Updated Plan or None if not found
        """
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        
        plan.status = PlanStatus.APPROVED
        return self.update_plan(plan)
    
    def start_plan(self, plan_id: str) -> Optional[Plan]:
        """Start executing a plan.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            Updated Plan or None if not found
        """
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        
        plan.status = PlanStatus.IN_PROGRESS
        return self.update_plan(plan)
    
    def complete_plan(self, plan_id: str) -> Optional[Plan]:
        """Mark a plan as completed.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            Updated Plan or None if not found
        """
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        
        plan.status = PlanStatus.COMPLETED
        return self.update_plan(plan)
    
    def abort_plan(self, plan_id: str) -> Optional[Plan]:
        """Abort a plan.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            Updated Plan or None if not found
        """
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        
        plan.status = PlanStatus.ABORTED
        return self.update_plan(plan)
    
    def update_step_status(
        self,
        plan_id: str,
        step_id: str,
        status: StepStatus,
        actual_result: Optional[str] = None,
    ) -> Optional[Plan]:
        """Update a step's status.
        
        Args:
            plan_id: Plan ID
            step_id: Step ID
            status: New status
            actual_result: Optional actual result
            
        Returns:
            Updated Plan or None if not found
        """
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        
        for step in plan.steps:
            if step.id == step_id:
                step.status = status
                if actual_result:
                    step.actual_result = actual_result
                break
        
        return self.update_plan(plan)
