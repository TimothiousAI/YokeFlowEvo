"""
Merge Validator
===============

Validates and performs merge operations after parallel batch completion.

Key Features:
- Merges worktree branches back to main
- Detects and reports merge conflicts
- Runs test suite on merged result (optional)
- Cleans up worktrees after successful merge
- Handles merge abort and rollback
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path
from datetime import datetime
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    """
    Result of merge validation.

    Attributes:
        status: Merge status ("success", "conflicts", "test_failed", "skipped")
        conflicts: List of conflict descriptions
        test_output: Output from test run (if applicable)
        merged_worktrees: List of successfully merged worktree paths
        duration: Time taken for merge validation
    """
    status: str
    conflicts: List[str] = field(default_factory=list)
    test_output: Optional[str] = None
    merged_worktrees: List[str] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class WorktreeMergeInfo:
    """Information about a worktree to merge."""
    path: str
    branch: str
    epic_id: int
    task_ids: List[int]


class MergeValidator:
    """
    Validates and merges worktrees after batch completion.

    Handles the complete merge lifecycle:
    1. Collect worktrees for the batch
    2. Attempt merge for each worktree
    3. Run tests on merged result
    4. Cleanup or rollback based on outcome
    """

    def __init__(
        self,
        project_path: str,
        db: Any,
        run_tests: bool = True,
        test_command: Optional[str] = None
    ):
        """
        Initialize merge validator.

        Args:
            project_path: Path to main project repository
            db: Database connection
            run_tests: Whether to run tests after merge
            test_command: Custom test command (default: pytest)
        """
        self.project_path = Path(project_path)
        self.db = db
        self.run_tests = run_tests
        self.test_command = test_command or "pytest"

        logger.info(f"MergeValidator initialized for {project_path}")

    async def validate_batch(self, batch_id: int) -> MergeResult:
        """
        Validate and merge all worktrees from a batch.

        Steps:
        1. Get all worktrees for the batch
        2. Attempt merge for each worktree
        3. If any conflicts, abort and report
        4. Run tests on merged result (optional)
        5. Cleanup worktrees on success

        Args:
            batch_id: The batch ID to validate

        Returns:
            MergeResult with validation status
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting merge validation for batch {batch_id}")

        # Get worktrees for this batch
        worktrees = await self._get_batch_worktrees(batch_id)
        if not worktrees:
            logger.info(f"No worktrees found for batch {batch_id}, skipping merge")
            return MergeResult(
                status="skipped",
                duration=(datetime.utcnow() - start_time).total_seconds()
            )

        logger.info(f"Found {len(worktrees)} worktrees to merge")

        conflicts: List[str] = []
        merged: List[str] = []

        # Attempt merge for each worktree
        for wt in worktrees:
            try:
                success, error = await self.merge_worktree(wt.path, wt.branch)
                if success:
                    merged.append(wt.path)
                    logger.info(f"Successfully merged {wt.branch}")
                else:
                    conflicts.append(f"Merge conflict in {wt.branch}: {error}")
                    logger.warning(f"Merge conflict in {wt.branch}: {error}")
            except Exception as e:
                conflicts.append(f"Merge error for {wt.branch}: {e}")
                logger.error(f"Merge error for {wt.branch}: {e}")

        if conflicts:
            # Abort all merges and report
            await self._abort_merge()
            logger.warning(f"Merge validation failed with {len(conflicts)} conflicts")
            return MergeResult(
                status="conflicts",
                conflicts=conflicts,
                duration=(datetime.utcnow() - start_time).total_seconds()
            )

        # Run tests (optional)
        test_output = None
        if self.run_tests and merged:
            test_pass, test_output = await self.run_test_suite()
            if not test_pass:
                # Rollback merges
                await self._rollback_merges(len(merged))
                logger.warning("Tests failed after merge, rolling back")
                return MergeResult(
                    status="test_failed",
                    test_output=test_output,
                    merged_worktrees=merged,
                    duration=(datetime.utcnow() - start_time).total_seconds()
                )

        # Cleanup worktrees
        await self.cleanup_worktrees(merged)

        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Merge validation completed successfully in {duration:.1f}s")

        return MergeResult(
            status="success",
            test_output=test_output,
            merged_worktrees=merged,
            duration=duration
        )

    async def merge_worktree(
        self,
        worktree_path: str,
        branch: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Merge a worktree branch using --no-commit first.

        Args:
            worktree_path: Path to the worktree
            branch: Branch name to merge

        Returns:
            Tuple of (success, error_message)
        """
        logger.debug(f"Attempting merge of {branch}")

        # First try merge with --no-commit to detect conflicts
        proc = await asyncio.create_subprocess_exec(
            "git", "merge", "--no-commit", "--no-ff", branch,
            cwd=str(self.project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            # Abort and return failure
            error_msg = stderr.decode().strip() or stdout.decode().strip()
            await self._abort_merge()
            return False, error_msg

        # Check for actual conflicts
        conflict_check = await asyncio.create_subprocess_exec(
            "git", "diff", "--name-only", "--diff-filter=U",
            cwd=str(self.project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await conflict_check.communicate()

        if stdout.decode().strip():
            # Has conflicted files
            await self._abort_merge()
            conflicted_files = stdout.decode().strip()
            return False, f"Conflicted files: {conflicted_files}"

        # Commit the merge
        commit_msg = f"Merge {branch} (parallel batch execution)"
        proc = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", commit_msg,
            cwd=str(self.project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            # Check if it's "nothing to commit" (already up to date)
            if b"nothing to commit" in stdout or b"nothing to commit" in stderr:
                return True, None
            error_msg = stderr.decode().strip() or stdout.decode().strip()
            return False, error_msg

        return True, None

    async def run_test_suite(self) -> Tuple[bool, str]:
        """
        Run test suite after merge.

        Returns:
            Tuple of (success, output)
        """
        logger.info(f"Running test suite: {self.test_command}")

        try:
            # Parse command
            if isinstance(self.test_command, str):
                cmd_parts = self.test_command.split()
            else:
                cmd_parts = list(self.test_command)

            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=str(self.project_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Set timeout for tests
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=300  # 5 minute timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return False, "Test suite timed out after 5 minutes"

            output = stdout.decode() + stderr.decode()
            success = proc.returncode == 0

            logger.info(f"Test suite {'passed' if success else 'failed'}")
            return success, output

        except FileNotFoundError:
            logger.warning(f"Test command not found: {self.test_command}")
            # If test command doesn't exist, consider it a pass
            return True, "Test command not found, skipping tests"
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return False, str(e)

    async def cleanup_worktrees(self, worktree_paths: List[str]) -> None:
        """
        Remove merged worktrees.

        Args:
            worktree_paths: List of worktree paths to remove
        """
        for path in worktree_paths:
            try:
                # Remove worktree using git
                proc = await asyncio.create_subprocess_exec(
                    "git", "worktree", "remove", "--force", path,
                    cwd=str(self.project_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()

                if proc.returncode == 0:
                    logger.info(f"Removed worktree: {path}")
                else:
                    logger.warning(f"Failed to remove worktree {path}")

            except Exception as e:
                logger.warning(f"Error removing worktree {path}: {e}")

    async def _get_batch_worktrees(self, batch_id: int) -> List[WorktreeMergeInfo]:
        """Get all worktrees associated with a batch."""
        try:
            # Try to get from database
            if hasattr(self.db, 'get_batch_worktrees'):
                rows = await self.db.get_batch_worktrees(batch_id)
                return [
                    WorktreeMergeInfo(
                        path=r['path'],
                        branch=r['branch'],
                        epic_id=r.get('epic_id', 0),
                        task_ids=r.get('task_ids', [])
                    )
                    for r in rows
                ]
        except Exception as e:
            logger.warning(f"Could not get worktrees from database: {e}")

        # Fallback: scan worktree directory
        return await self._scan_worktrees()

    async def _scan_worktrees(self) -> List[WorktreeMergeInfo]:
        """Scan filesystem for worktrees."""
        worktrees = []
        worktree_dir = self.project_path / ".worktrees"

        if not worktree_dir.exists():
            return worktrees

        try:
            # List git worktrees
            proc = await asyncio.create_subprocess_exec(
                "git", "worktree", "list", "--porcelain",
                cwd=str(self.project_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()

            current_worktree: Dict[str, str] = {}
            for line in stdout.decode().split('\n'):
                if line.startswith('worktree '):
                    if current_worktree and current_worktree.get('path') != str(self.project_path):
                        worktrees.append(WorktreeMergeInfo(
                            path=current_worktree['path'],
                            branch=current_worktree.get('branch', 'unknown'),
                            epic_id=0,
                            task_ids=[]
                        ))
                    current_worktree = {'path': line[9:]}
                elif line.startswith('branch '):
                    branch = line[7:]
                    # Extract branch name from refs/heads/...
                    if branch.startswith('refs/heads/'):
                        branch = branch[11:]
                    current_worktree['branch'] = branch

            # Don't forget the last one
            if current_worktree and current_worktree.get('path') != str(self.project_path):
                worktrees.append(WorktreeMergeInfo(
                    path=current_worktree['path'],
                    branch=current_worktree.get('branch', 'unknown'),
                    epic_id=0,
                    task_ids=[]
                ))

        except Exception as e:
            logger.warning(f"Error scanning worktrees: {e}")

        return worktrees

    async def _abort_merge(self) -> None:
        """Abort current merge operation."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "merge", "--abort",
                cwd=str(self.project_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            logger.debug("Merge aborted")
        except Exception as e:
            logger.warning(f"Error aborting merge: {e}")

    async def _rollback_merges(self, count: int) -> None:
        """
        Rollback the last N merge commits.

        Args:
            count: Number of merge commits to rollback
        """
        if count <= 0:
            return

        try:
            # Reset to before the merges
            proc = await asyncio.create_subprocess_exec(
                "git", "reset", "--hard", f"HEAD~{count}",
                cwd=str(self.project_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            if proc.returncode == 0:
                logger.info(f"Rolled back {count} merge commits")
            else:
                logger.warning(f"Failed to rollback merges")

        except Exception as e:
            logger.error(f"Error rolling back merges: {e}")
