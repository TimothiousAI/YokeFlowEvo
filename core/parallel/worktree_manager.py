"""
Git Worktree Manager

Manages git worktrees for isolated parallel task execution, including
creation, merging, conflict detection, and cleanup.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path
import asyncio
import logging

logger = logging.getLogger(__name__)


class GitCommandError(Exception):
    """Raised when a git command fails."""
    pass


class WorktreeConflictError(Exception):
    """Raised when a merge conflict is detected."""
    pass


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""
    path: Path
    branch: str
    epic_id: int
    status: str  # 'active', 'merged', 'conflict', 'cleaned'
    created_at: datetime = field(default_factory=datetime.utcnow)
    merged_at: Optional[datetime] = None
    merge_commit: Optional[str] = None


class WorktreeManager:
    """
    Manages git worktrees for isolated parallel execution.

    Each epic gets its own worktree, allowing parallel agents to work
    on different parts of the codebase without conflicts.
    """

    def __init__(
        self,
        project_path: Path,
        project_id: int,
        worktree_dir: str = ".worktrees"
    ):
        """
        Initialize the worktree manager.

        Args:
            project_path: Path to the main git repository
            project_id: The project ID for database tracking
            worktree_dir: Directory name for worktrees (relative to project_path)
        """
        self.project_path = Path(project_path)
        self.project_id = project_id
        self.worktree_dir = self.project_path / worktree_dir
        self._worktrees: Dict[int, WorktreeInfo] = {}

    async def initialize(self) -> None:
        """
        Initialize the worktree manager.

        Creates the worktree directory if it doesn't exist and loads
        existing worktree state from the database.
        """
        # TODO: Implement initialization
        raise NotImplementedError("WorktreeManager.initialize() not yet implemented")

    async def create_worktree(self, epic_id: int, epic_name: str) -> WorktreeInfo:
        """
        Create a new worktree for an epic.

        Args:
            epic_id: The epic ID
            epic_name: The epic name (used for branch naming)

        Returns:
            WorktreeInfo for the created worktree
        """
        # TODO: Implement worktree creation
        raise NotImplementedError("WorktreeManager.create_worktree() not yet implemented")

    async def merge_worktree(self, epic_id: int, squash: bool = False) -> str:
        """
        Merge a worktree back to main.

        Args:
            epic_id: The epic ID
            squash: Whether to squash commits

        Returns:
            The merge commit hash
        """
        # TODO: Implement worktree merge
        raise NotImplementedError("WorktreeManager.merge_worktree() not yet implemented")

    async def cleanup_worktree(self, epic_id: int) -> None:
        """
        Remove a worktree and its branch.

        Args:
            epic_id: The epic ID
        """
        # TODO: Implement worktree cleanup
        raise NotImplementedError("WorktreeManager.cleanup_worktree() not yet implemented")

    def get_worktree_status(self, epic_id: int) -> Optional[WorktreeInfo]:
        """
        Get the status of a worktree.

        Args:
            epic_id: The epic ID

        Returns:
            WorktreeInfo or None if not found
        """
        return self._worktrees.get(epic_id)

    def list_worktrees(self) -> List[WorktreeInfo]:
        """
        List all worktrees for this project.

        Returns:
            List of WorktreeInfo objects
        """
        return list(self._worktrees.values())

    async def sync_worktree_from_main(self, epic_id: int) -> None:
        """
        Sync a worktree with the latest changes from main.

        Args:
            epic_id: The epic ID
        """
        # TODO: Implement sync from main
        raise NotImplementedError("WorktreeManager.sync_worktree_from_main() not yet implemented")

    async def _run_git(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        timeout: int = 60
    ) -> str:
        """
        Run a git command asynchronously.

        Args:
            args: Git command arguments
            cwd: Working directory (defaults to project_path)
            timeout: Command timeout in seconds

        Returns:
            Command stdout

        Raises:
            GitCommandError: If the command fails
        """
        # TODO: Implement async git execution
        raise NotImplementedError("WorktreeManager._run_git() not yet implemented")

    def _sanitize_branch_name(self, name: str) -> str:
        """
        Sanitize a string for use as a git branch name.

        Handles Windows reserved names, invalid characters, and length limits.

        Args:
            name: The raw name to sanitize

        Returns:
            A valid git branch name
        """
        # Windows reserved names
        RESERVED_NAMES = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }

        # Convert to lowercase and replace spaces
        result = name.lower().replace(' ', '-')

        # Remove invalid characters
        invalid_chars = ':*?"<>|\\/.'
        for char in invalid_chars:
            result = result.replace(char, '')

        # Remove consecutive hyphens
        while '--' in result:
            result = result.replace('--', '-')

        # Strip leading/trailing hyphens
        result = result.strip('-')

        # Handle reserved names
        if result.upper() in RESERVED_NAMES:
            result = f"epic-{result}"

        # Enforce max length
        if len(result) > 200:
            result = result[:200]

        return result or "unnamed-epic"
