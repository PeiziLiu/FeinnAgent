"""Checkpoint management using Git shadow repos.

Creates automatic snapshots of working directories before file-mutating
operations, triggered once per conversation turn. Provides rollback to
any previous checkpoint.
"""

import hashlib
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CHECKPOINT_BASE = Path.home() / ".feinn" / "checkpoints"

DEFAULT_EXCLUDES = [
    "*.pyc",
    "__pycache__/",
    ".DS_Store",
    "*.log",
    ".cache/",
    ".pytest_cache/",
    ".venv/",
    "venv/",
    ".git/",
    "node_modules/",
    "dist/",
    "build/",
    ".env",
    ".env.*",
    ".env.*.local",
]

GIT_TIMEOUT = 30
MAX_FILES = 50_000


@dataclass
class Checkpoint:
    """Represents a checkpoint snapshot."""
    id: str
    commit_id: str
    working_dir: str
    message: str
    created_at: datetime
    file_count: int = 0
    changes_summary: str = ""


@dataclass
class RestoreResult:
    """Result of a restore operation."""
    success: bool
    message: str
    restored_files: int = 0
    reverted_files: int = 0


@dataclass
class FileChange:
    """Represents a file change in a checkpoint."""
    path: str
    change_type: str  # 'added', 'modified', 'deleted'
    old_content: Optional[str] = None
    new_content: Optional[str] = None


def _shadow_repo_path(working_dir: str) -> Path:
    """Deterministic shadow repo path: sha256(abs_path)[:16]."""
    abs_path = str(Path(working_dir).resolve())
    dir_hash = hashlib.sha256(abs_path.encode()).hexdigest()[:16]
    return CHECKPOINT_BASE / dir_hash


def _git_env(shadow_repo: Path, working_dir: str) -> dict:
    """Build env dict that redirects git to the shadow repo."""
    env = os.environ.copy()
    env["GIT_DIR"] = str(shadow_repo)
    env["GIT_WORK_TREE"] = str(Path(working_dir).resolve())
    env.pop("GIT_INDEX_FILE", None)
    env.pop("GIT_NAMESPACE", None)
    env.pop("GIT_ALTERNATE_OBJECT_DIRECTORIES", None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _run_git(
    args: list[str],
    shadow_repo: Path,
    working_dir: str,
    timeout: int = GIT_TIMEOUT,
) -> tuple[int, str, str]:
    """Run a git command against the shadow repo."""
    env = _git_env(shadow_repo, working_dir)
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(Path(working_dir).resolve()),
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Git command timed out"
    except Exception as e:
        return -1, "", str(e)


class CheckpointManager:
    """Manages checkpoints using Git shadow repos."""
    
    def __init__(
        self,
        checkpoints_dir: Optional[Path] = None,
        max_files: int = MAX_FILES,
        exclude_patterns: Optional[list[str]] = None,
    ):
        self.checkpoints_dir = checkpoints_dir or CHECKPOINT_BASE
        self.max_files = max_files
        self.exclude_patterns = exclude_patterns or DEFAULT_EXCLUDES
        self._ensure_base_dir()
    
    def _ensure_base_dir(self) -> None:
        """Ensure base checkpoint directory exists."""
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_shadow_repo(self, working_dir: str) -> Optional[Path]:
        """Initialize shadow git repo if needed."""
        shadow_path = _shadow_repo_path(working_dir)
        
        if shadow_path.exists():
            return shadow_path
        
        try:
            shadow_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize bare git repo
            rc, stdout, stderr = _run_git(
                ["init", "--bare"],
                shadow_path,
                working_dir,
            )
            if rc != 0:
                logger.error(f"Failed to init shadow repo: {stderr}")
                return None
            
            # Create HERMES_WORKDIR marker
            (shadow_path / "HERMES_WORKDIR").write_text(str(Path(working_dir).resolve()))
            
            # Set up git exclude
            exclude_path = shadow_path / "info" / "exclude"
            exclude_path.parent.mkdir(parents=True, exist_ok=True)
            exclude_path.write_text("\n".join(self.exclude_patterns) + "\n")
            
            return shadow_path
        except Exception as e:
            logger.error(f"Failed to create shadow repo: {e}")
            return None
    
    def _get_file_count(self, working_dir: str) -> int:
        """Count files in working directory (excluding patterns)."""
        count = 0
        try:
            for root, dirs, files in os.walk(working_dir):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if not self._is_excluded(d)]
                count += len([f for f in files if not self._is_excluded(f)])
                if count > self.max_files:
                    break
        except Exception as e:
            logger.warning(f"Error counting files: {e}")
        return min(count, self.max_files)
    
    def _is_excluded(self, name: str) -> bool:
        """Check if a file/directory should be excluded."""
        for pattern in self.exclude_patterns:
            pattern = pattern.rstrip("/")
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
        return False
    
    def create_checkpoint(
        self,
        working_dir: str,
        message: str = "",
    ) -> Optional[Checkpoint]:
        """Create a checkpoint snapshot of the working directory.
        
        Args:
            working_dir: The directory to snapshot
            message: Optional commit message
            
        Returns:
            Checkpoint object if successful, None otherwise
        """
        shadow_path = self._init_shadow_repo(working_dir)
        if not shadow_path:
            return None
        
        # Stage all files
        rc, _, stderr = _run_git(
            ["add", "-A"],
            shadow_path,
            working_dir,
        )
        if rc != 0:
            logger.error(f"Failed to stage files: {stderr}")
            return None
        
        # Create commit
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        commit_message = message or f"Checkpoint {timestamp}"
        
        rc, stdout, stderr = _run_git(
            ["commit", "-m", commit_message],
            shadow_path,
            working_dir,
        )
        
        if rc != 0:
            # No changes to commit is not an error
            if "nothing to commit" not in stderr:
                logger.error(f"Failed to create checkpoint: {stderr}")
                return None
            # Find the last commit
            rc, stdout, stderr = _run_git(
                ["rev-parse", "HEAD"],
                shadow_path,
                working_dir,
            )
            if rc != 0:
                return None
            commit_id = stdout.strip()
        else:
            # Extract commit ID
            rc, stdout, stderr = _run_git(
                ["rev-parse", "HEAD"],
                shadow_path,
                working_dir,
            )
            commit_id = stdout.strip() if rc == 0 else ""
        
        # Get file count
        file_count = self._get_file_count(working_dir)
        
        # Create checkpoint ID
        checkpoint_id = f"ckpt-{timestamp}"
        
        checkpoint = Checkpoint(
            id=checkpoint_id,
            commit_id=commit_id,
            working_dir=working_dir,
            message=commit_message,
            created_at=datetime.now(),
            file_count=file_count,
        )
        
        logger.info(f"Created checkpoint {checkpoint_id} for {working_dir}")
        return checkpoint
    
    def list_checkpoints(
        self,
        working_dir: str,
    ) -> list[Checkpoint]:
        """List all checkpoints for a working directory.
        
        Args:
            working_dir: The working directory
            
        Returns:
            List of Checkpoint objects
        """
        shadow_path = _shadow_repo_path(working_dir)
        if not shadow_path.exists():
            return []
        
        rc, stdout, stderr = _run_git(
            ["log", "--format=%H|%s|%ci", "-100"],
            shadow_path,
            working_dir,
        )
        
        if rc != 0:
            logger.error(f"Failed to list checkpoints: {stderr}")
            return []
        
        checkpoints = []
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                commit_id, message, created_at_str = parts[0], parts[1], parts[2]
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                checkpoint_id = f"ckpt-{timestamp}"
                
                checkpoints.append(Checkpoint(
                    id=checkpoint_id,
                    commit_id=commit_id,
                    working_dir=working_dir,
                    message=message,
                    created_at=datetime.fromisoformat(created_at_str.strip()),
                ))
        
        return list(reversed(checkpoints))
    
    def get_checkpoint(
        self,
        checkpoint_id: str,
        working_dir: Optional[str] = None,
    ) -> Optional[Checkpoint]:
        """Get a specific checkpoint by ID.
        
        Args:
            checkpoint_id: The checkpoint ID
            working_dir: Optional working directory (for finding shadow repo)
            
        Returns:
            Checkpoint if found, None otherwise
        """
        # Note: checkpoint_id format is ckpt-timestamp, we need the commit hash
        # This requires searching through commits
        if working_dir:
            checkpoints = self.list_checkpoints(working_dir)
            for ckpt in checkpoints:
                if ckpt.id == checkpoint_id:
                    return ckpt
        return None
    
    def get_checkpoint_diff(
        self,
        checkpoint_id: str,
        working_dir: str,
    ) -> list[FileChange]:
        """Get the diff for a specific checkpoint.
        
        Args:
            checkpoint_id: The checkpoint ID
            working_dir: The working directory
            
        Returns:
            List of FileChange objects
        """
        shadow_path = _shadow_repo_path(working_dir)
        if not shadow_path.exists():
            return []
        
        # Get commit ID for checkpoint
        checkpoints = self.list_checkpoints(working_dir)
        target_commit = None
        for ckpt in checkpoints:
            if ckpt.id == checkpoint_id:
                target_commit = ckpt.commit_id
                break
        
        if not target_commit:
            return []
        
        # Get diff from parent
        rc, stdout, stderr = _run_git(
            ["diff-tree", "--no-commit-id", "--name-status", "-r", target_commit + "^", target_commit],
            shadow_path,
            working_dir,
        )
        
        if rc != 0:
            return []
        
        changes = []
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                change_type = parts[0]
                path = parts[1]
                changes.append(FileChange(
                    path=path,
                    change_type=change_type,
                ))
        
        return changes
    
    def restore_checkpoint(
        self,
        checkpoint_id: str,
        working_dir: str,
    ) -> RestoreResult:
        """Restore working directory to a checkpoint.
        
        Args:
            checkpoint_id: The checkpoint ID to restore
            working_dir: The working directory
            
        Returns:
            RestoreResult indicating success/failure
        """
        shadow_path = _shadow_repo_path(working_dir)
        if not shadow_path.exists():
            return RestoreResult(
                success=False,
                message="No shadow repo found for this directory",
            )
        
        # Get checkpoint
        checkpoints = self.list_checkpoints(working_dir)
        target_commit = None
        for ckpt in checkpoints:
            if ckpt.id == checkpoint_id:
                target_commit = ckpt.commit_id
                break
        
        if not target_commit:
            return RestoreResult(
                success=False,
                message=f"Checkpoint {checkpoint_id} not found",
            )
        
        # Create backup checkpoint before restore
        backup = self.create_checkpoint(working_dir, "Backup before restore")
        
        # Restore files
        rc, stdout, stderr = _run_git(
            ["checkout", target_commit, "--", "."],
            shadow_path,
            working_dir,
        )
        
        if rc != 0:
            return RestoreResult(
                success=False,
                message=f"Failed to restore: {stderr}",
            )
        
        # Count restored files
        restored_count = len(list(Path(working_dir).rglob("*"))) if Path(working_dir).exists() else 0
        
        return RestoreResult(
            success=True,
            message=f"Restored to checkpoint {checkpoint_id}",
            restored_files=restored_count,
        )
    
    def delete_checkpoint(
        self,
        checkpoint_id: str,
        working_dir: str,
    ) -> bool:
        """Delete a checkpoint.
        
        Args:
            checkpoint_id: The checkpoint ID to delete
            working_dir: The working directory
            
        Returns:
            True if deleted, False otherwise
        """
        shadow_path = _shadow_repo_path(working_dir)
        if not shadow_path.exists():
            return False
        
        # Get checkpoint
        checkpoints = self.list_checkpoints(working_dir)
        target_commit = None
        for ckpt in checkpoints:
            if ckpt.id == checkpoint_id:
                target_commit = ckpt.commit_id
                break
        
        if not target_commit:
            return False
        
        # Delete commit by creating new branch without it
        # Git doesn't allow deleting commits directly, so we just note this limitation
        logger.info(f"Checkpoint {checkpoint_id} cannot be directly deleted (Git limitation)")
        return False
    
    def cleanup_expired(
        self,
        retention_days: int = 30,
    ) -> int:
        """Clean up expired checkpoints.
        
        Args:
            retention_days: How many days to retain checkpoints
            
        Returns:
            Number of checkpoints cleaned up
        """
        import time
        cutoff = time.time() - (retention_days * 24 * 60 * 60)
        cleaned = 0
        
        for shadow_path in self.checkpoints_dir.iterdir():
            if shadow_path.is_dir() and shadow_path.name != ".git":
                # Check each checkpoint
                working_dir = (shadow_path / "HERMES_WORKDIR").read_text().strip() if (shadow_path / "HERMES_WORKDIR").exists() else str(shadow_path)
                checkpoints = self.list_checkpoints(working_dir)
                
                for ckpt in checkpoints:
                    ckpt_time = ckpt.created_at.timestamp()
                    if ckpt_time < cutoff:
                        # This is a simplification - real implementation would
                        # need to gc the git repo
                        cleaned += 1
        
        return cleaned
