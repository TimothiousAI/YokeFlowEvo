"""
Unit tests for WorktreeManager

Tests all core functionality with mocked git commands for fast, reliable testing.
"""

import asyncio
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.worktree_manager import (
    WorktreeManager,
    WorktreeInfo,
    GitCommandError,
    WorktreeConflictError
)


class TestWorktreeCreation:
    """Test worktree creation with mocked git commands."""

    async def test_create_worktree_success(self):
        """Test successful worktree creation."""
        print("\n=== Test: Create Worktree Success ===")

        # Create temp directory for test
        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project",
                worktree_dir=".worktrees"
            )

            # Mock git commands
            with patch.object(manager, '_run_git', new_callable=AsyncMock) as mock_git:
                with patch.object(manager, '_get_main_branch', return_value='main'):
                    with patch.object(manager, '_has_uncommitted_changes', return_value=False):
                        mock_git.return_value = ""

                        # Create worktree
                        worktree = await manager.create_worktree(epic_id=1, epic_name="Test Epic")

                        assert worktree.epic_id == 1
                        assert worktree.branch == "epic-1-test-epic"
                        assert worktree.status == "active"
                        # Path should contain epic ID
                        assert "epic-1" in worktree.path or "epic_1" in worktree.path

                        print(f"[PASS] Created worktree: {worktree.branch}")
                        print(f"[PASS] Path: {worktree.path}")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")

    async def test_create_worktree_reuses_existing(self):
        """Test that creating worktree for same epic reuses existing worktree."""
        print("\n=== Test: Reuse Existing Worktree ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project"
            )

            with patch.object(manager, '_run_git', new_callable=AsyncMock) as mock_git:
                with patch.object(manager, '_get_main_branch', return_value='main'):
                    with patch.object(manager, '_has_uncommitted_changes', return_value=False):
                        mock_git.return_value = ""

                        # Create first time
                        worktree1 = await manager.create_worktree(epic_id=1, epic_name="Test Epic")

                        # Try to create again
                        worktree2 = await manager.create_worktree(epic_id=1, epic_name="Test Epic")

                        assert worktree1.path == worktree2.path
                        assert worktree1.branch == worktree2.branch

                        print(f"[PASS] Reused existing worktree for epic 1")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestWorktreeMerge:
    """Test worktree merge functionality."""

    async def test_merge_worktree_success(self):
        """Test successful worktree merge."""
        print("\n=== Test: Merge Worktree Success ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project"
            )

            # Create worktree directory
            worktree_path = Path(temp_dir) / ".worktrees" / "epic-1"
            worktree_path.mkdir(parents=True, exist_ok=True)

            # Create a worktree first
            worktree = WorktreeInfo(
                path=str(worktree_path),
                branch="epic-1-test",
                epic_id=1,
                status="active",
                created_at=datetime.now()
            )
            manager._worktrees[1] = worktree

            with patch.object(manager, '_run_git', new_callable=AsyncMock) as mock_git:
                with patch.object(manager, '_get_main_branch', return_value='main'):
                    with patch.object(manager, '_has_uncommitted_changes', return_value=False):
                        with patch.object(manager, '_check_merge_conflicts', return_value=False):
                            mock_git.return_value = "abc123def"

                            # Merge worktree
                            commit_hash = await manager.merge_worktree(epic_id=1, squash=False)

                            assert commit_hash == "abc123def"
                            assert manager._worktrees[1].status == "merged"

                            print(f"[PASS] Merged worktree successfully")
                            print(f"[PASS] Commit hash: {commit_hash}")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")

    async def test_merge_worktree_with_conflicts(self):
        """Test merge failure due to conflicts."""
        print("\n=== Test: Merge With Conflicts ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project"
            )

            # Create worktree directory
            worktree_path = Path(temp_dir) / ".worktrees" / "epic-1"
            worktree_path.mkdir(parents=True, exist_ok=True)

            worktree = WorktreeInfo(
                path=str(worktree_path),
                branch="epic-1-test",
                epic_id=1,
                status="active",
                created_at=datetime.now()
            )
            manager._worktrees[1] = worktree

            with patch.object(manager, '_run_git', new_callable=AsyncMock) as mock_git:
                with patch.object(manager, '_get_main_branch', return_value='main'):
                    with patch.object(manager, '_has_uncommitted_changes', return_value=False):
                        # Make git merge command fail with conflict
                        def mock_git_with_conflict(args, **kwargs):
                            if 'merge' in args and '--abort' not in args:
                                raise GitCommandError("CONFLICT (content): Merge conflict in file.txt")
                            return ""

                        mock_git.side_effect = mock_git_with_conflict

                        # Should raise WorktreeConflictError
                        try:
                            await manager.merge_worktree(epic_id=1)
                            assert False, "Should have raised WorktreeConflictError"
                        except WorktreeConflictError as e:
                            print(f"[PASS] Correctly raised conflict error: {e}")
                            assert "conflict" in str(e).lower()

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestWorktreeCleanup:
    """Test worktree cleanup functionality."""

    async def test_cleanup_worktree_success(self):
        """Test successful worktree cleanup."""
        print("\n=== Test: Cleanup Worktree Success ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project"
            )

            # Create worktree entry
            worktree_path = Path(temp_dir) / ".worktrees" / "epic-1"
            worktree_path.mkdir(parents=True, exist_ok=True)

            worktree = WorktreeInfo(
                path=str(worktree_path),
                branch="epic-1-test",
                epic_id=1,
                status="merged",
                created_at=datetime.now()
            )
            manager._worktrees[1] = worktree

            with patch.object(manager, '_run_git', new_callable=AsyncMock) as mock_git:
                mock_git.return_value = ""

                # Cleanup worktree
                await manager.cleanup_worktree(epic_id=1)

                assert 1 not in manager._worktrees
                print(f"[PASS] Cleaned up worktree for epic 1")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")

    async def test_cleanup_removes_directory_if_git_fails(self):
        """Test that cleanup removes directory even if git worktree remove fails."""
        print("\n=== Test: Cleanup Removes Directory on Git Failure ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project"
            )

            worktree_path = Path(temp_dir) / ".worktrees" / "epic-1"
            worktree_path.mkdir(parents=True, exist_ok=True)

            worktree = WorktreeInfo(
                path=str(worktree_path),
                branch="epic-1-test",
                epic_id=1,
                status="merged",
                created_at=datetime.now()
            )
            manager._worktrees[1] = worktree

            with patch.object(manager, '_run_git', new_callable=AsyncMock) as mock_git:
                # Simulate git worktree remove failure
                mock_git.side_effect = GitCommandError("worktree not found")

                # Should still cleanup
                await manager.cleanup_worktree(epic_id=1)

                assert 1 not in manager._worktrees
                assert not worktree_path.exists()
                print(f"[PASS] Removed directory despite git failure")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestBranchNameSanitization:
    """Test branch name sanitization for Windows compatibility."""

    def test_sanitize_basic(self):
        """Test basic sanitization."""
        print("\n=== Test: Branch Name Sanitization - Basic ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project"
            )

            # Test special characters
            result = manager._sanitize_branch_name("My Epic Task!")
            assert result == "my-epic-task"
            print(f"[PASS] 'My Epic Task!' -> '{result}'")

            # Test spaces
            result = manager._sanitize_branch_name("Add User Auth")
            assert result == "add-user-auth"
            print(f"[PASS] 'Add User Auth' -> '{result}'")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")

    def test_sanitize_windows_reserved_names(self):
        """Test Windows reserved name handling."""
        print("\n=== Test: Branch Name Sanitization - Windows Reserved ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project"
            )

            # Test reserved names
            reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT1']

            for name in reserved_names:
                result = manager._sanitize_branch_name(name)
                assert result != name.lower(), f"Should rename reserved name {name}"
                # Implementation prefixes with 'epic-'
                assert result == f'epic-{name.lower()}', f"Expected 'epic-{name.lower()}', got '{result}'"
                print(f"[PASS] Reserved '{name}' sanitized to '{result}'")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")

    def test_sanitize_invalid_characters(self):
        """Test removal of invalid git branch characters."""
        print("\n=== Test: Branch Name Sanitization - Invalid Chars ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project"
            )

            # Test various invalid characters
            test_cases = [
                ("epic:feature", "epic-feature"),
                ("task*with?chars", "task-with-chars"),
                ("path/to/epic", "path-to-epic"),
                ("epic<>with|pipes", "epic-with-pipes"),
            ]

            for input_name, expected in test_cases:
                result = manager._sanitize_branch_name(input_name)
                # Should not contain invalid characters
                invalid_chars = ':*?"<>|\\/'
                for char in invalid_chars:
                    assert char not in result, f"Invalid char '{char}' found in '{result}'"
                print(f"[PASS] '{input_name}' -> '{result}'")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")

    def test_sanitize_length_limit(self):
        """Test branch name length is limited."""
        print("\n=== Test: Branch Name Sanitization - Length Limit ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project"
            )

            # Very long name
            long_name = "a" * 300
            result = manager._sanitize_branch_name(long_name)

            assert len(result) <= 200, f"Branch name too long: {len(result)}"
            print(f"[PASS] Long name (300 chars) truncated to {len(result)} chars")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestDatabaseSync:
    """Test database synchronization."""

    async def test_database_sync_on_create(self):
        """Test database is updated when worktree is created."""
        print("\n=== Test: Database Sync on Create ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            # Mock database
            mock_db = Mock()
            mock_db.create_worktree = AsyncMock(return_value={"id": 1})

            # Use valid UUID format
            project_uuid = "12345678-1234-5678-1234-567812345678"

            manager = WorktreeManager(
                project_path=temp_dir,
                project_id=project_uuid,
                db=mock_db
            )

            with patch.object(manager, '_run_git', new_callable=AsyncMock) as mock_git:
                with patch.object(manager, '_get_main_branch', return_value='main'):
                    with patch.object(manager, '_has_uncommitted_changes', return_value=False):
                        mock_git.return_value = ""

                        # Create worktree
                        await manager.create_worktree(epic_id=1, epic_name="Test Epic")

                        # Verify database was called
                        assert mock_db.create_worktree.called
                        print(f"[PASS] Database create_worktree called")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")

    async def test_database_sync_on_merge(self):
        """Test database is updated when worktree is merged."""
        print("\n=== Test: Database Sync on Merge ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            mock_db = Mock()
            mock_db.update_worktree = AsyncMock()

            # Use valid UUID format
            project_uuid = "12345678-1234-5678-1234-567812345678"

            manager = WorktreeManager(
                project_path=temp_dir,
                project_id=project_uuid,
                db=mock_db
            )

            # Create worktree directory
            worktree_path = Path(temp_dir) / ".worktrees" / "epic-1"
            worktree_path.mkdir(parents=True, exist_ok=True)

            worktree = WorktreeInfo(
                path=str(worktree_path),
                branch="epic-1-test",
                epic_id=1,
                status="active",
                created_at=datetime.now()
            )
            manager._worktrees[1] = worktree

            with patch.object(manager, '_run_git', new_callable=AsyncMock) as mock_git:
                with patch.object(manager, '_get_main_branch', return_value='main'):
                    with patch.object(manager, '_has_uncommitted_changes', return_value=False):
                        with patch.object(manager, '_check_merge_conflicts', return_value=False):
                            mock_git.return_value = "abc123"

                            await manager.merge_worktree(epic_id=1)

                            # Verify database was called
                            assert mock_db.update_worktree.called
                            print(f"[PASS] Database update_worktree called")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestRecoveryFromInvalidState:
    """Test recovery from invalid states."""

    async def test_recover_state_rebuilds_from_database(self):
        """Test that recover_state() loads worktrees from database."""
        print("\n=== Test: Recover State from Database ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            # Use valid UUID format
            project_uuid = "12345678-1234-5678-1234-567812345678"

            # Create worktree directory so it's found during recovery
            worktree_path = Path(temp_dir) / ".worktrees" / "epic-1"
            worktree_path.mkdir(parents=True, exist_ok=True)

            mock_db = Mock()
            mock_db.list_worktrees = AsyncMock(return_value=[
                {
                    'id': 1,
                    'epic_id': 1,
                    'branch_name': 'epic-1-test',
                    'worktree_path': str(worktree_path),
                    'status': 'active',
                    'created_at': datetime.now()
                }
            ])
            mock_db.update_worktree = AsyncMock()

            manager = WorktreeManager(
                project_path=temp_dir,
                project_id=project_uuid,
                db=mock_db
            )

            with patch.object(manager, '_run_git', new_callable=AsyncMock) as mock_git:
                mock_git.return_value = ""

                # Recover state
                status = await manager.recover_state()

                assert status['recovered_count'] == 1
                assert 1 in manager._worktrees
                print(f"[PASS] Recovered 1 worktree from database")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestConcurrentOperations:
    """Test concurrent worktree operations."""

    async def test_concurrent_worktree_creation(self):
        """Test creating multiple worktrees concurrently."""
        print("\n=== Test: Concurrent Worktree Creation ===")

        temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
        try:
            manager = WorktreeManager(
                project_path=temp_dir,
                project_id="test-project"
            )

            with patch.object(manager, '_run_git', new_callable=AsyncMock) as mock_git:
                with patch.object(manager, '_get_main_branch', return_value='main'):
                    with patch.object(manager, '_has_uncommitted_changes', return_value=False):
                        mock_git.return_value = ""

                        # Create multiple worktrees concurrently
                        tasks = [
                            manager.create_worktree(epic_id=1, epic_name="Epic 1"),
                            manager.create_worktree(epic_id=2, epic_name="Epic 2"),
                            manager.create_worktree(epic_id=3, epic_name="Epic 3"),
                        ]

                        worktrees = await asyncio.gather(*tasks)

                        assert len(worktrees) == 3
                        assert len(manager._worktrees) == 3
                        print(f"[PASS] Created 3 worktrees concurrently")

                        # Verify each has unique branch
                        branches = [w.branch for w in worktrees]
                        assert len(set(branches)) == 3
                        print(f"[PASS] All worktrees have unique branches")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


async def run_all_tests():
    """Run all test suites."""
    print("\n" + "="*60)
    print("Running WorktreeManager Unit Tests")
    print("="*60)

    try:
        # Worktree creation tests
        creation = TestWorktreeCreation()
        await creation.test_create_worktree_success()
        await creation.test_create_worktree_reuses_existing()

        # Worktree merge tests
        merge = TestWorktreeMerge()
        await merge.test_merge_worktree_success()
        await merge.test_merge_worktree_with_conflicts()

        # Cleanup tests
        cleanup = TestWorktreeCleanup()
        await cleanup.test_cleanup_worktree_success()
        await cleanup.test_cleanup_removes_directory_if_git_fails()

        # Branch sanitization tests
        sanitize = TestBranchNameSanitization()
        sanitize.test_sanitize_basic()
        sanitize.test_sanitize_windows_reserved_names()
        sanitize.test_sanitize_invalid_characters()
        sanitize.test_sanitize_length_limit()

        # Database sync tests
        db_sync = TestDatabaseSync()
        await db_sync.test_database_sync_on_create()
        await db_sync.test_database_sync_on_merge()

        # Recovery tests
        recovery = TestRecoveryFromInvalidState()
        await recovery.test_recover_state_rebuilds_from_database()

        # Concurrent operations tests
        concurrent = TestConcurrentOperations()
        await concurrent.test_concurrent_worktree_creation()

        print("\n" + "="*60)
        print("[SUCCESS] ALL TESTS PASSED (14/14)")
        print("="*60)
        print("\nTest Coverage:")
        print("  [PASS] Worktree creation (with mocked git)")
        print("  [PASS] Worktree merge flow")
        print("  [PASS] Worktree cleanup")
        print("  [PASS] Conflict detection")
        print("  [PASS] Branch name sanitization (Windows reserved names, special chars)")
        print("  [PASS] Database sync on operations")
        print("  [PASS] Recovery from invalid state")
        print("  [PASS] Concurrent worktree operations")

        return True

    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
