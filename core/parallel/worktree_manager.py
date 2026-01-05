"""
Worktree Manager
================

Manages git worktrees for isolated parallel task execution.
Each epic gets its own worktree with an isolated branch.

Key Features:
- Creates and manages git worktrees per epic
- Handles branch creation and naming (Windows-safe)
- Merges worktrees back to main branch
- Detects and reports merge conflicts
- Cleans up worktrees after use
- Syncs state with database
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class GitCommandError(Exception):
    """Raised when a git command fails."""
    pass


class WorktreeConflictError(Exception):
    """Raised when a worktree merge has conflicts."""
    pass


@dataclass
class WorktreeInfo:
    """
    Information about a worktree.

    Attributes:
        path: Filesystem path to worktree
        branch: Git branch name
        epic_id: Epic ID this worktree belongs to
        status: Current status (active/merged/conflict/cleanup)
        created_at: When worktree was created
        merged_at: When worktree was merged (if applicable)
    """
    path: str
    branch: str
    epic_id: int
    status: str
    created_at: datetime
    merged_at: Optional[datetime] = None


class WorktreeManager:
    """
    Manages git worktrees for parallel execution isolation.

    Creates one worktree per epic, allowing multiple agents to work
    on different epics simultaneously without conflicts.
    """

    def __init__(
        self,
        project_path: str,
        project_id: str,
        worktree_dir: str = ".worktrees",
        db=None
    ):
        """
        Initialize worktree manager.

        Args:
            project_path: Path to project repository
            project_id: Project UUID
            worktree_dir: Directory for worktrees (relative to project root)
            db: Database connection (optional, for state persistence)
        """
        self.project_path = Path(project_path)
        self.project_id = project_id
        self.worktree_dir = worktree_dir
        self.db = db
        self._worktrees: Dict[int, WorktreeInfo] = {}  # epic_id -> WorktreeInfo
        logger.info(f"WorktreeManager initialized for project {project_id}")

    async def initialize(self) -> None:
        """
        Initialize worktree manager and create worktree directory.
        Creates the .worktrees directory if it doesn't exist and loads
        existing worktree state from the database.
        """
        # Create worktrees directory
        worktree_path = self.project_path / self.worktree_dir
        worktree_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Worktree directory initialized at {worktree_path}")

        # Load existing worktrees from database if available
        if self.db:
            try:
                from uuid import UUID
                worktrees_data = await self.db.list_worktrees(UUID(self.project_id))
                for wt_data in worktrees_data:
                    worktree_info = WorktreeInfo(
                        path=wt_data['worktree_path'],
                        branch=wt_data['branch_name'],
                        epic_id=wt_data['epic_id'],
                        status=wt_data['status'],
                        created_at=wt_data['created_at'],
                        merged_at=wt_data.get('merged_at')
                    )
                    self._worktrees[wt_data['epic_id']] = worktree_info
                logger.info(f"Loaded {len(self._worktrees)} existing worktrees from database")
            except Exception as e:
                logger.warning(f"Could not load worktrees from database: {e}")

    async def recover_state(self) -> Dict[str, Any]:
        """
        Recover worktree state from both git and database.

        This method reconciles the state between:
        1. Actual git worktrees on disk
        2. Database records
        3. In-memory state

        Useful for recovery after crashes or restarts.

        Returns:
            Dictionary with recovery results:
            - recovered_count: Number of worktrees recovered
            - cleaned_count: Number of stale entries cleaned
            - errors: List of errors encountered
        """
        logger.info("Recovering worktree state from git and database")

        recovered_count = 0
        cleaned_count = 0
        errors = []

        try:
            # Get list of actual git worktrees
            try:
                worktrees_output = await self._run_git(['worktree', 'list', '--porcelain'], timeout=30)

                # Parse git worktree list
                git_worktrees = {}  # path -> branch mapping
                current_worktree = {}

                for line in worktrees_output.split('\n'):
                    line = line.strip()
                    if line.startswith('worktree '):
                        if current_worktree:
                            path = current_worktree.get('worktree')
                            branch = current_worktree.get('branch')
                            if path and branch:
                                git_worktrees[path] = branch
                        current_worktree = {'worktree': line.split(' ', 1)[1]}
                    elif line.startswith('branch '):
                        # Format: "branch refs/heads/branch-name"
                        branch_ref = line.split(' ', 1)[1]
                        # Extract branch name from ref
                        branch_name = branch_ref.replace('refs/heads/', '')
                        current_worktree['branch'] = branch_name

                # Don't forget the last one
                if current_worktree:
                    path = current_worktree.get('worktree')
                    branch = current_worktree.get('branch')
                    if path and branch:
                        git_worktrees[path] = branch

                logger.info(f"Found {len(git_worktrees)} git worktrees on disk")

            except GitCommandError as e:
                logger.warning(f"Could not list git worktrees: {e}")
                git_worktrees = {}

            # Load database records if available
            db_worktrees = {}  # epic_id -> worktree_data mapping
            if self.db:
                try:
                    from uuid import UUID
                    worktrees_data = await self.db.list_worktrees(UUID(self.project_id))
                    for wt_data in worktrees_data:
                        db_worktrees[wt_data['epic_id']] = wt_data
                    logger.info(f"Found {len(db_worktrees)} worktrees in database")
                except Exception as e:
                    logger.warning(f"Could not load from database: {e}")
                    errors.append(f"Database load error: {e}")

            # Reconcile state
            # 1. Update in-memory state from database
            for epic_id, wt_data in db_worktrees.items():
                worktree_path = wt_data['worktree_path']

                # Check if worktree still exists on disk
                if worktree_path in git_worktrees or Path(worktree_path).exists():
                    # Worktree exists, restore to in-memory state
                    worktree_info = WorktreeInfo(
                        path=wt_data['worktree_path'],
                        branch=wt_data['branch_name'],
                        epic_id=wt_data['epic_id'],
                        status=wt_data['status'],
                        created_at=wt_data['created_at'],
                        merged_at=wt_data.get('merged_at')
                    )
                    self._worktrees[epic_id] = worktree_info
                    recovered_count += 1
                    logger.info(f"Recovered worktree for epic {epic_id}: {worktree_path}")
                else:
                    # Worktree doesn't exist on disk but is in database
                    # Mark as stale in database
                    logger.warning(f"Stale database entry for epic {epic_id}, worktree not found at {worktree_path}")
                    if self.db:
                        try:
                            from uuid import UUID
                            await self.db.update_worktree(
                                worktree_id=epic_id,
                                status='stale'
                            )
                            cleaned_count += 1
                        except Exception as e:
                            logger.warning(f"Could not update stale worktree in database: {e}")
                            errors.append(f"Failed to mark worktree {epic_id} as stale: {e}")

            # 2. Check for git worktrees not in database
            worktree_dir_path = self.project_path / self.worktree_dir
            worktree_dir_str = str(worktree_dir_path).replace('\\', '/')

            for worktree_path, branch in git_worktrees.items():
                # Normalize path for comparison (Windows compatibility)
                normalized_path = worktree_path.replace('\\', '/')

                # Only care about worktrees in our worktree directory
                if worktree_dir_str in normalized_path:
                    # Extract epic_id from path (format: .worktrees/epic-{id})
                    try:
                        path_parts = Path(worktree_path).parts
                        dir_name = path_parts[-1]
                        if dir_name.startswith('epic-'):
                            epic_id = int(dir_name.split('-')[1])

                            # Check if we have this in database or memory
                            if epic_id not in self._worktrees:
                                logger.warning(f"Found worktree on disk not in database: epic {epic_id} at {worktree_path}")
                                # Create in-memory entry (will be synced to database on next operation)
                                worktree_info = WorktreeInfo(
                                    path=worktree_path,
                                    branch=branch,
                                    epic_id=epic_id,
                                    status='active',
                                    created_at=datetime.now()
                                )
                                self._worktrees[epic_id] = worktree_info
                                recovered_count += 1
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Could not parse epic_id from path {worktree_path}: {e}")

            logger.info(f"State recovery complete: {recovered_count} recovered, {cleaned_count} cleaned")

            return {
                'recovered_count': recovered_count,
                'cleaned_count': cleaned_count,
                'errors': errors
            }

        except Exception as e:
            logger.error(f"Error during state recovery: {e}")
            errors.append(f"Recovery error: {e}")
            return {
                'recovered_count': recovered_count,
                'cleaned_count': cleaned_count,
                'errors': errors
            }

    def get_worktree_status(self) -> Dict[str, Any]:
        """
        Get current worktree status.

        Returns:
            Dict with worktree status information including:
            - total_worktrees: Total number of worktrees
            - active_worktrees: Number of active worktrees
            - merged_worktrees: Number of merged worktrees
            - worktrees: List of worktree info dicts
        """
        active_count = sum(1 for wt in self._worktrees.values() if wt.status == 'active')
        merged_count = sum(1 for wt in self._worktrees.values() if wt.status == 'merged')

        return {
            'total_worktrees': len(self._worktrees),
            'active_worktrees': active_count,
            'merged_worktrees': merged_count,
            'worktrees': [
                {
                    'epic_id': wt.epic_id,
                    'path': wt.path,
                    'branch': wt.branch,
                    'status': wt.status,
                    'created_at': wt.created_at.isoformat() if wt.created_at else None,
                    'merged_at': wt.merged_at.isoformat() if wt.merged_at else None
                }
                for wt in self._worktrees.values()
            ]
        }

    def list_worktrees(self) -> List[WorktreeInfo]:
        """
        List all worktrees for this project.

        Returns:
            List of WorktreeInfo objects
        """
        return list(self._worktrees.values())

    async def create_worktree(self, epic_id: int, epic_name: str) -> WorktreeInfo:
        """
        Create a new worktree for an epic.

        Args:
            epic_id: Epic ID
            epic_name: Epic name (used for branch naming)

        Returns:
            WorktreeInfo for created worktree

        Raises:
            GitCommandError: If worktree creation fails
        """
        logger.info(f"Creating worktree for epic {epic_id}: {epic_name}")

        # Check if worktree already exists for this epic
        if epic_id in self._worktrees:
            existing = self._worktrees[epic_id]
            logger.info(f"Worktree already exists for epic {epic_id}: {existing.path}")

            # Check if the worktree directory still exists and is valid
            worktree_path = Path(existing.path)
            if worktree_path.exists() and worktree_path.is_dir():
                # Verify it's a valid git worktree
                try:
                    await self._run_git(['status'], cwd=worktree_path, timeout=10)
                    logger.info(f"Reusing existing worktree: {existing.path}")
                    return existing
                except GitCommandError:
                    logger.warning(f"Existing worktree is invalid, will recreate")

            # Worktree is stale, remove from tracking
            del self._worktrees[epic_id]

        # Create sanitized branch name
        branch_name = f"epic-{epic_id}-{self._sanitize_branch_name(epic_name)}"
        logger.info(f"Branch name: {branch_name}")

        # Get main branch
        main_branch = await self._get_main_branch()

        # Create worktree path
        worktree_path = self.project_path / self.worktree_dir / f"epic-{epic_id}"
        worktree_path_str = str(worktree_path)

        try:
            # Check if branch already exists
            try:
                await self._run_git(['rev-parse', '--verify', branch_name], timeout=10)
                branch_exists = True
                logger.info(f"Branch {branch_name} already exists")
            except GitCommandError:
                branch_exists = False
                logger.info(f"Branch {branch_name} does not exist, will create")

            # Create branch from main if it doesn't exist
            if not branch_exists:
                await self._run_git(
                    ['branch', branch_name, main_branch],
                    timeout=30
                )
                logger.info(f"Created branch {branch_name} from {main_branch}")

            # Create worktree directory if it exists (cleanup old worktree)
            if worktree_path.exists():
                logger.warning(f"Worktree directory already exists, removing: {worktree_path}")
                import shutil
                shutil.rmtree(worktree_path, ignore_errors=True)

            # Create worktree
            await self._run_git(
                ['worktree', 'add', worktree_path_str, branch_name],
                timeout=60
            )
            logger.info(f"Created worktree at {worktree_path}")

            # Create WorktreeInfo
            worktree_info = WorktreeInfo(
                path=worktree_path_str,
                branch=branch_name,
                epic_id=epic_id,
                status='active',
                created_at=datetime.now()
            )

            # Store in memory
            self._worktrees[epic_id] = worktree_info

            # Record in database if available
            if self.db:
                try:
                    from uuid import UUID
                    await self.db.create_worktree(
                        project_id=UUID(self.project_id),
                        epic_id=epic_id,
                        branch_name=branch_name,
                        worktree_path=worktree_path_str,
                        status='active'
                    )
                    logger.info(f"Worktree recorded in database")
                except Exception as e:
                    logger.warning(f"Failed to record worktree in database: {e}")

            logger.info(f"Worktree creation complete: {worktree_info.path}")
            return worktree_info

        except Exception as e:
            logger.error(f"Failed to create worktree: {e}")
            # Cleanup on failure
            if worktree_path.exists():
                try:
                    import shutil
                    shutil.rmtree(worktree_path, ignore_errors=True)
                except Exception:
                    pass
            raise

    async def merge_worktree(self, epic_id: int, squash: bool = False) -> str:
        """
        Merge worktree back to main branch.

        Args:
            epic_id: Epic ID
            squash: Whether to squash commits

        Returns:
            Merge commit SHA

        Raises:
            GitCommandError: If merge fails
            WorktreeConflictError: If merge has conflicts
        """
        logger.info(f"Merging worktree for epic {epic_id} (squash={squash})")

        # Get worktree info
        if epic_id not in self._worktrees:
            raise GitCommandError(f"No worktree found for epic {epic_id}")

        worktree_info = self._worktrees[epic_id]
        worktree_path = Path(worktree_info.path)

        if not worktree_path.exists():
            raise GitCommandError(f"Worktree directory does not exist: {worktree_path}")

        # Check for uncommitted changes in worktree
        has_changes = await self._has_uncommitted_changes(cwd=worktree_path)
        if has_changes:
            logger.info(f"Committing uncommitted changes in worktree")
            try:
                # Add all changes
                await self._run_git(['add', '-A'], cwd=worktree_path, timeout=30)

                # Commit changes
                commit_msg = f"Auto-commit changes before merge (epic {epic_id})"
                await self._run_git(
                    ['commit', '-m', commit_msg],
                    cwd=worktree_path,
                    timeout=30
                )
                logger.info(f"Committed changes in worktree")
            except GitCommandError as e:
                logger.warning(f"Failed to commit changes: {e}")
                # Continue anyway - might be okay

        # Get main branch
        main_branch = await self._get_main_branch()

        # Switch to main branch in main repo
        logger.info(f"Switching to {main_branch} in main repo")
        current_branch = await self._get_current_branch()

        if current_branch != main_branch:
            try:
                await self._run_git(['checkout', main_branch], timeout=30)
                logger.info(f"Switched to {main_branch}")
            except GitCommandError as e:
                # Check if main is locked by another worktree
                if 'already used by worktree' in str(e):
                    logger.warning(f"Cannot checkout {main_branch} - in use by another worktree")
                    logger.info(f"Will perform merge from current branch: {current_branch}")
                    # Continue with merge from current branch
                    # This is safe when we're in a worktree ourselves
                else:
                    raise

        # Check for merge conflicts using dry run
        logger.info(f"Checking for potential merge conflicts")
        try:
            # Use merge-tree for dry-run conflict detection (Git 2.38+)
            # Fallback: just attempt the merge
            merge_base_output = await self._run_git(
                ['merge-base', main_branch, worktree_info.branch],
                timeout=10
            )
            merge_base = merge_base_output.strip()

            try:
                # Try merge-tree (newer git versions)
                conflicts = await self._run_git(
                    ['merge-tree', merge_base, main_branch, worktree_info.branch],
                    timeout=30
                )

                # Check if output indicates conflicts (contains conflict markers)
                if '<<<<<<< ' in conflicts:
                    logger.warning(f"Merge would have conflicts")
                    # Continue anyway - will handle during actual merge
                else:
                    logger.info(f"No conflicts detected in dry run")
            except GitCommandError:
                # merge-tree not available or failed, continue with actual merge
                logger.debug(f"merge-tree not available, will attempt merge")

        except GitCommandError as e:
            logger.warning(f"Could not check for conflicts: {e}")

        # Perform the merge
        try:
            if squash:
                logger.info(f"Performing squash merge of {worktree_info.branch}")
                await self._run_git(
                    ['merge', '--squash', worktree_info.branch],
                    timeout=60
                )

                # Squash merge requires manual commit
                commit_msg = f"Merge epic {epic_id}: {worktree_info.branch}"
                await self._run_git(
                    ['commit', '-m', commit_msg],
                    timeout=30
                )
                logger.info(f"Squash merge committed")
            else:
                logger.info(f"Performing regular merge of {worktree_info.branch}")
                commit_msg = f"Merge epic {epic_id}: {worktree_info.branch}"
                await self._run_git(
                    ['merge', '--no-ff', '-m', commit_msg, worktree_info.branch],
                    timeout=60
                )
                logger.info(f"Regular merge completed")

        except GitCommandError as e:
            # Check if it's a merge conflict
            if 'CONFLICT' in str(e) or 'conflict' in str(e).lower():
                logger.error(f"Merge conflict detected")

                # Abort the merge
                try:
                    await self._run_git(['merge', '--abort'], timeout=30)
                    logger.info(f"Merge aborted")
                except GitCommandError:
                    pass

                # Update worktree status
                worktree_info.status = 'conflict'

                # Update database if available
                if self.db:
                    try:
                        from uuid import UUID
                        await self.db.update_worktree(
                            worktree_id=epic_id,  # Note: This assumes worktree_id = epic_id
                            status='conflict'
                        )
                    except Exception as db_error:
                        logger.warning(f"Failed to update database: {db_error}")

                raise WorktreeConflictError(
                    f"Merge conflict for epic {epic_id}. Please resolve manually."
                )
            else:
                # Other merge error
                logger.error(f"Merge failed: {e}")
                raise

        # Get merge commit hash
        merge_commit = await self._run_git(
            ['rev-parse', 'HEAD'],
            timeout=10
        )
        merge_commit = merge_commit.strip()
        logger.info(f"Merge commit: {merge_commit}")

        # Update worktree info
        worktree_info.status = 'merged'
        worktree_info.merged_at = datetime.now()

        # Update database if available
        if self.db:
            try:
                from uuid import UUID
                await self.db.update_worktree(
                    worktree_id=epic_id,  # Note: This assumes worktree_id = epic_id
                    status='merged',
                    merge_commit=merge_commit
                )
                logger.info(f"Database updated with merge status")
            except Exception as e:
                logger.warning(f"Failed to update database: {e}")

        logger.info(f"Worktree merge complete: {merge_commit}")
        return merge_commit

    async def sync_worktree_from_main(
        self,
        epic_id: int,
        strategy: str = 'merge'
    ) -> Dict[str, Any]:
        """
        Sync worktree with latest changes from main branch.

        This pulls the latest changes from main branch into the worktree,
        allowing the worktree to stay up-to-date with ongoing main branch development.

        Args:
            epic_id: Epic ID
            strategy: Sync strategy - 'merge' (default) or 'rebase'

        Returns:
            Dictionary with sync status:
            - status: 'success', 'conflict', or 'error'
            - strategy: Strategy used ('merge' or 'rebase')
            - message: Description of result
            - conflicts: List of conflicting files (if status is 'conflict')

        Raises:
            GitCommandError: If worktree not found or sync fails
            ValueError: If invalid strategy specified
        """
        logger.info(f"Syncing worktree for epic {epic_id} from main (strategy={strategy})")

        # Validate strategy
        valid_strategies = ['merge', 'rebase']
        if strategy not in valid_strategies:
            raise ValueError(
                f"Invalid strategy '{strategy}'. Must be one of: {', '.join(valid_strategies)}"
            )

        # Get worktree info
        if epic_id not in self._worktrees:
            raise GitCommandError(f"No worktree found for epic {epic_id}")

        worktree_info = self._worktrees[epic_id]
        worktree_path = Path(worktree_info.path)
        branch_name = worktree_info.branch

        if not worktree_path.exists():
            raise GitCommandError(f"Worktree directory does not exist: {worktree_path}")

        # Get main branch name
        main_branch = await self._get_main_branch()
        logger.info(f"Syncing from {main_branch} branch")

        try:
            # Fetch latest changes from main (in main repo, not worktree)
            logger.info(f"Fetching latest changes from {main_branch}")
            try:
                # Fetch to update refs
                await self._run_git(['fetch', '.', f'{main_branch}:{main_branch}'], timeout=60)
                logger.info(f"Fetched latest {main_branch}")
            except GitCommandError as e:
                # Fetch might fail if we're already up to date or in a worktree
                logger.debug(f"Fetch had issues (may be okay): {e}")

            # Switch to worktree directory
            logger.info(f"Syncing changes into worktree branch {branch_name}")

            # Check for uncommitted changes in worktree
            has_changes = await self._has_uncommitted_changes(cwd=worktree_path)
            if has_changes:
                logger.warning(f"Worktree has uncommitted changes, committing before sync")
                try:
                    # Commit uncommitted changes
                    await self._run_git(['add', '-A'], cwd=worktree_path, timeout=30)
                    commit_msg = f"Auto-commit before sync from {main_branch}"
                    await self._run_git(
                        ['commit', '-m', commit_msg],
                        cwd=worktree_path,
                        timeout=30
                    )
                    logger.info(f"Committed uncommitted changes")
                except GitCommandError as e:
                    logger.warning(f"Failed to commit changes: {e}")

            # Perform sync based on strategy
            if strategy == 'merge':
                logger.info(f"Merging {main_branch} into {branch_name}")
                try:
                    # Merge main into current branch
                    await self._run_git(
                        ['merge', main_branch, '--no-edit'],
                        cwd=worktree_path,
                        timeout=60
                    )
                    logger.info(f"Merge successful")

                    return {
                        'status': 'success',
                        'strategy': 'merge',
                        'message': f'Successfully merged {main_branch} into worktree'
                    }

                except GitCommandError as e:
                    # Check if it's a merge conflict
                    if 'CONFLICT' in str(e) or 'conflict' in str(e).lower():
                        logger.warning(f"Merge conflict during sync")

                        # Get list of conflicted files
                        try:
                            status_output = await self._run_git(
                                ['status', '--short'],
                                cwd=worktree_path,
                                timeout=10
                            )
                            conflicted_files = []
                            for line in status_output.split('\n'):
                                if line.startswith('UU ') or line.startswith('AA ') or line.startswith('DD '):
                                    file_path = line[3:].strip()
                                    conflicted_files.append(file_path)

                            logger.info(f"Found {len(conflicted_files)} conflicted files")

                            return {
                                'status': 'conflict',
                                'strategy': 'merge',
                                'message': f'Merge conflicts detected in {len(conflicted_files)} file(s)',
                                'conflicts': conflicted_files
                            }

                        except GitCommandError:
                            return {
                                'status': 'conflict',
                                'strategy': 'merge',
                                'message': 'Merge conflicts detected',
                                'conflicts': []
                            }
                    else:
                        # Other merge error
                        logger.error(f"Merge failed: {e}")
                        raise

            else:  # rebase strategy
                logger.info(f"Rebasing {branch_name} onto {main_branch}")
                try:
                    # Rebase current branch onto main
                    await self._run_git(
                        ['rebase', main_branch],
                        cwd=worktree_path,
                        timeout=120
                    )
                    logger.info(f"Rebase successful")

                    return {
                        'status': 'success',
                        'strategy': 'rebase',
                        'message': f'Successfully rebased onto {main_branch}'
                    }

                except GitCommandError as e:
                    # Check if it's a rebase conflict
                    if 'CONFLICT' in str(e) or 'conflict' in str(e).lower():
                        logger.warning(f"Rebase conflict during sync")

                        # Get list of conflicted files
                        try:
                            status_output = await self._run_git(
                                ['status', '--short'],
                                cwd=worktree_path,
                                timeout=10
                            )
                            conflicted_files = []
                            for line in status_output.split('\n'):
                                if line.startswith('UU ') or line.startswith('AA ') or line.startswith('DD '):
                                    file_path = line[3:].strip()
                                    conflicted_files.append(file_path)

                            logger.info(f"Found {len(conflicted_files)} conflicted files")

                            # Abort the rebase to leave in clean state
                            try:
                                await self._run_git(
                                    ['rebase', '--abort'],
                                    cwd=worktree_path,
                                    timeout=30
                                )
                                logger.info(f"Rebase aborted")
                            except GitCommandError:
                                pass

                            return {
                                'status': 'conflict',
                                'strategy': 'rebase',
                                'message': f'Rebase conflicts detected in {len(conflicted_files)} file(s)',
                                'conflicts': conflicted_files
                            }

                        except GitCommandError:
                            # Abort the rebase
                            try:
                                await self._run_git(
                                    ['rebase', '--abort'],
                                    cwd=worktree_path,
                                    timeout=30
                                )
                            except GitCommandError:
                                pass

                            return {
                                'status': 'conflict',
                                'strategy': 'rebase',
                                'message': 'Rebase conflicts detected',
                                'conflicts': []
                            }
                    else:
                        # Other rebase error
                        logger.error(f"Rebase failed: {e}")
                        raise

        except Exception as e:
            logger.error(f"Failed to sync worktree: {e}")
            return {
                'status': 'error',
                'strategy': strategy,
                'message': f'Sync failed: {str(e)}'
            }

    async def cleanup_worktree(self, epic_id: int) -> None:
        """
        Remove worktree and clean up resources.

        Args:
            epic_id: Epic ID

        Raises:
            GitCommandError: If cleanup fails (non-fatal errors are logged)
        """
        logger.info(f"Cleaning up worktree for epic {epic_id}")

        # Get worktree info
        if epic_id not in self._worktrees:
            logger.warning(f"No worktree found for epic {epic_id}, nothing to clean up")
            return

        worktree_info = self._worktrees[epic_id]
        worktree_path = Path(worktree_info.path)
        branch_name = worktree_info.branch

        # Remove worktree using git worktree remove
        try:
            if worktree_path.exists():
                logger.info(f"Removing worktree: {worktree_path}")
                try:
                    # Try normal remove first
                    await self._run_git(
                        ['worktree', 'remove', str(worktree_path)],
                        timeout=30
                    )
                    logger.info(f"Worktree removed successfully")
                except GitCommandError as e:
                    # If normal remove fails, try force remove
                    if 'contains modified or untracked files' in str(e) or 'uncommitted changes' in str(e):
                        logger.warning(f"Worktree has uncommitted changes, forcing removal")
                        await self._run_git(
                            ['worktree', 'remove', '--force', str(worktree_path)],
                            timeout=30
                        )
                        logger.info(f"Worktree force-removed successfully")
                    else:
                        raise
            else:
                logger.warning(f"Worktree directory already removed: {worktree_path}")

        except GitCommandError as e:
            # If git worktree remove fails, try manual directory cleanup
            logger.warning(f"Git worktree remove failed: {e}")
            if worktree_path.exists():
                logger.info(f"Attempting manual directory cleanup")
                try:
                    import shutil
                    shutil.rmtree(worktree_path, ignore_errors=True)
                    logger.info(f"Worktree directory removed manually")
                except Exception as cleanup_error:
                    logger.error(f"Failed to remove worktree directory: {cleanup_error}")

        # Delete branch if fully merged
        try:
            # Check if branch exists
            try:
                await self._run_git(['rev-parse', '--verify', branch_name], timeout=10)
                branch_exists = True
            except GitCommandError:
                branch_exists = False
                logger.info(f"Branch {branch_name} already deleted")

            if branch_exists:
                # Check if branch is fully merged into current branch
                try:
                    # Try to delete with -d (safe delete - only if merged)
                    # This will fail if branch has unmerged changes
                    await self._run_git(['branch', '-d', branch_name], timeout=30)
                    logger.info(f"Branch deleted successfully (was fully merged)")
                except GitCommandError as e:
                    # Branch has unmerged changes
                    if 'not fully merged' in str(e):
                        logger.warning(f"Branch {branch_name} has unmerged changes")
                        logger.info(f"Use 'git branch -D {branch_name}' to force delete if needed")
                        # Don't force delete - let user decide
                    else:
                        # Other error
                        logger.warning(f"Could not delete branch: {e}")


        except Exception as e:
            logger.error(f"Error during branch cleanup: {e}")

        # Update database to mark as cleaned up
        if self.db:
            try:
                from uuid import UUID
                await self.db.update_worktree(
                    worktree_id=epic_id,  # Note: This assumes worktree_id = epic_id
                    status='cleanup'
                )
                logger.info(f"Database updated with cleanup status")
            except Exception as e:
                logger.warning(f"Failed to update database: {e}")

        # Remove from memory
        del self._worktrees[epic_id]
        logger.info(f"Worktree cleanup complete for epic {epic_id}")

    async def _run_git(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        timeout: int = 60
    ) -> str:
        """
        Run a git command asynchronously.

        Args:
            args: Git command arguments (e.g., ['status', '--short'])
            cwd: Working directory for command (defaults to project_path)
            timeout: Command timeout in seconds (default 60)

        Returns:
            Command stdout output

        Raises:
            GitCommandError: If command fails or times out
        """
        if cwd is None:
            cwd = self.project_path

        cmd = ['git'] + args
        logger.debug(f"Running git command: {' '.join(cmd)} in {cwd}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise GitCommandError(
                    f"Git command timed out after {timeout}s: {' '.join(cmd)}"
                )

            if process.returncode != 0:
                stderr_str = stderr.decode('utf-8', errors='replace').strip()
                raise GitCommandError(
                    f"Git command failed (exit {process.returncode}): {' '.join(cmd)}\n{stderr_str}"
                )

            return stdout.decode('utf-8', errors='replace').strip()

        except FileNotFoundError:
            raise GitCommandError("Git command not found. Is git installed?")
        except Exception as e:
            if isinstance(e, GitCommandError):
                raise
            raise GitCommandError(f"Failed to run git command: {e}")

    async def _get_main_branch(self) -> str:
        """
        Detect the main branch name (main or master).

        Returns:
            Name of main branch ('main' or 'master')

        Raises:
            GitCommandError: If unable to determine main branch
        """
        try:
            # Try to get default branch from remote
            output = await self._run_git(
                ['symbolic-ref', 'refs/remotes/origin/HEAD'],
                timeout=10
            )
            # Output format: refs/remotes/origin/main
            branch = output.split('/')[-1]
            logger.debug(f"Detected main branch from remote: {branch}")
            return branch
        except GitCommandError:
            # Fallback: check if main or master exists locally
            try:
                await self._run_git(['rev-parse', '--verify', 'main'], timeout=10)
                logger.debug("Using 'main' as main branch")
                return 'main'
            except GitCommandError:
                try:
                    await self._run_git(['rev-parse', '--verify', 'master'], timeout=10)
                    logger.debug("Using 'master' as main branch")
                    return 'master'
                except GitCommandError:
                    raise GitCommandError(
                        "Could not determine main branch (neither 'main' nor 'master' found)"
                    )

    async def _get_current_branch(self, cwd: Optional[Path] = None) -> str:
        """
        Get the current branch name.

        Args:
            cwd: Working directory (defaults to project_path)

        Returns:
            Current branch name

        Raises:
            GitCommandError: If not on a branch or command fails
        """
        output = await self._run_git(
            ['rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=cwd,
            timeout=10
        )

        if output == 'HEAD':
            raise GitCommandError("Not currently on a branch (detached HEAD)")

        logger.debug(f"Current branch: {output}")
        return output

    async def _has_uncommitted_changes(self, cwd: Optional[Path] = None) -> bool:
        """
        Check if working directory has uncommitted changes.

        Args:
            cwd: Working directory (defaults to project_path)

        Returns:
            True if there are uncommitted changes, False otherwise
        """
        output = await self._run_git(
            ['status', '--short'],
            cwd=cwd,
            timeout=10
        )

        has_changes = len(output) > 0
        logger.debug(f"Uncommitted changes: {has_changes}")
        return has_changes

    async def _check_merge_conflicts(self, branch: str) -> bool:
        """
        Check if merging a branch would cause conflicts using git merge-tree dry run.

        Args:
            branch: Branch name to check for conflicts

        Returns:
            True if conflicts would occur, False otherwise

        Raises:
            GitCommandError: If conflict check fails
        """
        logger.info(f"Checking for merge conflicts with branch {branch}")

        try:
            # Get main branch
            main_branch = await self._get_main_branch()

            # Get merge base
            merge_base_output = await self._run_git(
                ['merge-base', main_branch, branch],
                timeout=10
            )
            merge_base = merge_base_output.strip()
            logger.debug(f"Merge base: {merge_base}")

            # Use merge-tree for dry-run conflict detection
            # Format: git merge-tree <base-commit> <branch1> <branch2>
            try:
                output = await self._run_git(
                    ['merge-tree', merge_base, main_branch, branch],
                    timeout=30
                )

                # Check if output contains conflict markers
                has_conflicts = '<<<<<<< ' in output or 'CONFLICT' in output

                if has_conflicts:
                    logger.warning(f"Merge conflicts detected for branch {branch}")
                    logger.debug(f"Conflict preview:\n{output[:500]}")  # Log first 500 chars
                else:
                    logger.info(f"No merge conflicts detected for branch {branch}")

                return has_conflicts

            except GitCommandError as e:
                # merge-tree might not be available in older git versions
                logger.warning(f"merge-tree command failed: {e}")
                logger.info(f"Cannot perform dry-run conflict check, assuming no conflicts")
                return False

        except GitCommandError as e:
            logger.error(f"Failed to check for merge conflicts: {e}")
            raise

    async def get_conflict_details(self, epic_id: int) -> List[Dict[str, Any]]:
        """
        Get detailed information about merge conflicts for a worktree.

        Args:
            epic_id: Epic ID

        Returns:
            List of dictionaries with conflict information:
            - file: File path with conflict
            - status: Conflict type (both_modified, deleted_by_us, etc.)
            - details: Additional conflict details

        Raises:
            GitCommandError: If worktree not found or conflict check fails
        """
        logger.info(f"Getting conflict details for epic {epic_id}")

        # Get worktree info
        if epic_id not in self._worktrees:
            raise GitCommandError(f"No worktree found for epic {epic_id}")

        worktree_info = self._worktrees[epic_id]
        branch_name = worktree_info.branch

        # Check if there are conflicts
        has_conflicts = await self._check_merge_conflicts(branch_name)

        if not has_conflicts:
            logger.info(f"No conflicts detected for epic {epic_id}")
            return []

        # Get main branch
        main_branch = await self._get_main_branch()

        # Get merge base
        merge_base_output = await self._run_git(
            ['merge-base', main_branch, branch_name],
            timeout=10
        )
        merge_base = merge_base_output.strip()

        # Use merge-tree to get detailed conflict information
        try:
            output = await self._run_git(
                ['merge-tree', merge_base, main_branch, branch_name],
                timeout=30
            )

            # Parse conflict information
            conflicts = []

            # Look for conflict markers and file information
            # merge-tree output format includes conflict markers and file paths
            import re

            # Find all files with conflict markers
            conflict_sections = output.split('<<<<<<< ')
            for section in conflict_sections[1:]:  # Skip first empty section
                lines = section.split('\n')
                # First line after <<<<<<< contains branch info
                # Look for file path in the section
                file_match = re.search(r'^\+\+\+ b/(.+)$', section, re.MULTILINE)
                if file_match:
                    file_path = file_match.group(1)
                else:
                    # Fallback: try to extract from context
                    file_path = "unknown"

                conflicts.append({
                    'file': file_path,
                    'status': 'both_modified',
                    'details': f'Conflicting changes in {file_path}'
                })

            # If we couldn't parse specific files, provide general conflict info
            if not conflicts:
                conflicts.append({
                    'file': 'multiple files',
                    'status': 'conflict_detected',
                    'details': 'Merge conflicts detected, run merge to see specific files'
                })

            logger.info(f"Found {len(conflicts)} conflicting files for epic {epic_id}")
            for conflict in conflicts:
                logger.debug(f"  Conflict: {conflict['file']} - {conflict['status']}")

            return conflicts

        except GitCommandError as e:
            logger.error(f"Failed to get conflict details: {e}")
            raise

    async def resolve_conflict(
        self,
        epic_id: int,
        strategy: str = 'manual'
    ) -> Dict[str, Any]:
        """
        Resolve merge conflicts using specified strategy.

        Args:
            epic_id: Epic ID
            strategy: Resolution strategy:
                - 'ours': Keep changes from main branch
                - 'theirs': Keep changes from worktree branch
                - 'manual': Leave conflict markers for human resolution

        Returns:
            Dictionary with resolution status:
            - status: 'resolved' or 'manual_required'
            - strategy: Strategy used
            - message: Description of action taken

        Raises:
            GitCommandError: If worktree not found or resolution fails
            ValueError: If invalid strategy specified
        """
        logger.info(f"Resolving conflicts for epic {epic_id} with strategy '{strategy}'")

        # Validate strategy
        valid_strategies = ['ours', 'theirs', 'manual']
        if strategy not in valid_strategies:
            raise ValueError(
                f"Invalid strategy '{strategy}'. Must be one of: {', '.join(valid_strategies)}"
            )

        # Get worktree info
        if epic_id not in self._worktrees:
            raise GitCommandError(f"No worktree found for epic {epic_id}")

        worktree_info = self._worktrees[epic_id]
        branch_name = worktree_info.branch

        # Get main branch
        main_branch = await self._get_main_branch()

        if strategy == 'manual':
            # For manual strategy, we don't auto-resolve
            # Just return conflict details for human resolution
            logger.info(f"Manual resolution requested - conflicts left for human intervention")

            conflicts = await self.get_conflict_details(epic_id)

            return {
                'status': 'manual_required',
                'strategy': 'manual',
                'message': f'Conflicts detected in {len(conflicts)} file(s). Manual resolution required.',
                'conflicts': conflicts
            }

        # For 'ours' or 'theirs' strategies, we need to attempt a merge
        # and then resolve conflicts automatically
        try:
            # Attempt the merge to create conflict state
            logger.info(f"Attempting merge to create conflict state")

            # Switch to main branch
            current_branch = await self._get_current_branch()
            if current_branch != main_branch:
                await self._run_git(['checkout', main_branch], timeout=30)

            try:
                # Try to merge - this will fail with conflicts
                await self._run_git(
                    ['merge', '--no-commit', '--no-ff', branch_name],
                    timeout=60
                )

                # If merge succeeded without conflicts, we're done
                logger.info(f"Merge succeeded without conflicts")

                # Complete the merge
                commit_msg = f"Merge epic {epic_id}: {branch_name}"
                await self._run_git(['commit', '-m', commit_msg], timeout=30)

                return {
                    'status': 'resolved',
                    'strategy': strategy,
                    'message': 'No conflicts - merge completed successfully'
                }

            except GitCommandError as e:
                # Check if it's a conflict error
                if 'CONFLICT' not in str(e) and 'conflict' not in str(e).lower():
                    # Not a conflict, some other error
                    raise

                logger.info(f"Conflicts detected during merge, applying {strategy} strategy")

                # Get list of conflicted files
                status_output = await self._run_git(['status', '--short'], timeout=10)
                conflicted_files = []
                for line in status_output.split('\n'):
                    if line.startswith('UU ') or line.startswith('AA ') or line.startswith('DD '):
                        # Extract file path (after status markers)
                        file_path = line[3:].strip()
                        conflicted_files.append(file_path)

                logger.info(f"Found {len(conflicted_files)} conflicted files")

                if not conflicted_files:
                    # No conflicted files found, abort merge
                    await self._run_git(['merge', '--abort'], timeout=30)
                    return {
                        'status': 'resolved',
                        'strategy': strategy,
                        'message': 'No conflicted files detected'
                    }

                # Resolve each conflicted file using the specified strategy
                for file_path in conflicted_files:
                    logger.info(f"Resolving {file_path} with strategy '{strategy}'")

                    if strategy == 'ours':
                        # Keep version from main branch (current HEAD)
                        await self._run_git(
                            ['checkout', '--ours', file_path],
                            timeout=30
                        )
                    elif strategy == 'theirs':
                        # Keep version from worktree branch
                        await self._run_git(
                            ['checkout', '--theirs', file_path],
                            timeout=30
                        )

                    # Stage the resolved file
                    await self._run_git(['add', file_path], timeout=30)

                # Complete the merge
                commit_msg = f"Merge epic {epic_id}: {branch_name} (resolved with {strategy})"
                await self._run_git(['commit', '-m', commit_msg], timeout=30)

                logger.info(f"Conflicts resolved using {strategy} strategy")

                return {
                    'status': 'resolved',
                    'strategy': strategy,
                    'message': f'Resolved {len(conflicted_files)} conflicted file(s) using {strategy} strategy',
                    'files_resolved': conflicted_files
                }

        except Exception as e:
            # If something went wrong, try to abort the merge
            try:
                await self._run_git(['merge', '--abort'], timeout=30)
                logger.info(f"Merge aborted after error")
            except GitCommandError:
                pass

            logger.error(f"Failed to resolve conflicts: {e}")
            raise GitCommandError(f"Conflict resolution failed: {e}")

    def _sanitize_branch_name(self, name: str) -> str:
        """
        Sanitize epic name to create valid git branch name.
        Windows-safe: handles reserved names and special characters.

        Windows-specific handling:
        - Reserved names: CON, PRN, AUX, NUL, COM1-9, LPT1-9
        - Invalid characters: : * ? " < > | \\ /
        - Trailing dots and spaces
        - Path length limits (200 chars for branch name)

        Args:
            name: Epic name to sanitize

        Returns:
            Sanitized branch name (lowercase, no spaces, valid characters)
        """
        import re

        # Convert to lowercase
        branch = name.lower()

        # Replace spaces and underscores with hyphens
        branch = branch.replace(' ', '-').replace('_', '-')

        # Remove Windows invalid characters: : * ? " < > | \ /
        # Also remove any other special characters except alphanumeric, hyphens, dots
        # Keep only: a-z, 0-9, hyphens, dots
        branch = re.sub(r'[^a-z0-9\-.]', '', branch)

        # Replace multiple consecutive hyphens with single hyphen
        branch = re.sub(r'-+', '-', branch)

        # Remove leading/trailing hyphens, dots, and spaces
        branch = branch.strip('-. ')

        # Handle Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
        # Check the base name (before any extension-like suffix)
        base_name = branch.split('.')[0] if '.' in branch else branch
        reserved_names = ['con', 'prn', 'aux', 'nul']
        reserved_names += [f'com{i}' for i in range(1, 10)]
        reserved_names += [f'lpt{i}' for i in range(1, 10)]

        if base_name in reserved_names or branch in reserved_names:
            branch = f'epic-{branch}'

        # Enforce max path length (200 chars for branch name to stay well under Windows MAX_PATH)
        # This leaves room for the full worktree path
        max_length = 200
        if len(branch) > max_length:
            branch = branch[:max_length].rstrip('-. ')

        # Ensure non-empty
        if not branch:
            branch = 'epic'

        logger.debug(f"Sanitized '{name}' -> '{branch}'")
        return branch
