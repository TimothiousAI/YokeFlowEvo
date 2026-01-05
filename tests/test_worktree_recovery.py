"""
Test script for WorktreeManager database integration and state recovery.
"""

import asyncio
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.worktree_manager import WorktreeManager


async def setup_test_repo():
    """Create a temporary test repository."""
    temp_dir = tempfile.mkdtemp(prefix='worktree_recovery_test_')
    repo_path = Path(temp_dir) / 'test_repo'
    repo_path.mkdir()

    print(f"Created test repo at: {repo_path}")

    # Initialize git repo
    os.system(f'cd "{repo_path}" && git init')
    os.system(f'cd "{repo_path}" && git config user.email "test@example.com"')
    os.system(f'cd "{repo_path}" && git config user.name "Test User"')

    # Create initial file and commit
    test_file = repo_path / 'test.txt'
    test_file.write_text('Line 1\nLine 2\nLine 3\n')
    os.system(f'cd "{repo_path}" && git add test.txt')
    os.system(f'cd "{repo_path}" && git commit -m "Initial commit"')

    return str(repo_path), temp_dir


async def test_state_recovery():
    """Test state recovery after manager restart."""
    print("\n" + "="*60)
    print("TEST: State Recovery")
    print("="*60)

    repo_path, temp_dir = await setup_test_repo()

    try:
        # Create first manager instance
        print("\n1. Creating first manager instance...")
        manager1 = WorktreeManager(
            project_path=repo_path,
            project_id='test-recovery-123',
            worktree_dir='.worktrees',
            db=None  # No database for this simple test
        )
        await manager1.initialize()

        # Create worktrees
        print("\n2. Creating worktrees...")
        wt1 = await manager1.create_worktree(100, "Epic 1")
        wt2 = await manager1.create_worktree(101, "Epic 2")
        print(f"   Created worktree 1: {wt1.path}")
        print(f"   Created worktree 2: {wt2.path}")

        # Verify in-memory state
        status1 = manager1.get_worktree_status()
        print(f"   Manager 1 has {status1['total_worktrees']} worktrees")

        # Create second manager instance (simulating restart)
        print("\n3. Creating new manager instance (simulating restart)...")
        manager2 = WorktreeManager(
            project_path=repo_path,
            project_id='test-recovery-123',
            worktree_dir='.worktrees',
            db=None
        )
        await manager2.initialize()

        # Before recovery, manager2 should have no in-memory state
        status2_before = manager2.get_worktree_status()
        print(f"   Manager 2 before recovery: {status2_before['total_worktrees']} worktrees")

        # Recover state
        print("\n4. Recovering state from git...")
        recovery_result = await manager2.recover_state()
        print(f"   Recovered: {recovery_result['recovered_count']} worktrees")
        print(f"   Cleaned: {recovery_result['cleaned_count']} stale entries")
        if recovery_result['errors']:
            print(f"   Errors: {recovery_result['errors']}")

        # Verify recovery
        status2_after = manager2.get_worktree_status()
        print(f"   Manager 2 after recovery: {status2_after['total_worktrees']} worktrees")

        # Test passes if we recovered the worktrees
        if status2_after['total_worktrees'] == 2 and recovery_result['recovered_count'] >= 2:
            print("\n   [PASS] State recovery successful")
            success = True
        else:
            print("\n   [FAIL] State recovery incomplete")
            success = False

        # Cleanup
        await manager2.cleanup_worktree(100)
        await manager2.cleanup_worktree(101)

        return success

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\nCleaned up test repo: {temp_dir}")


async def test_recover_state_method():
    """Test that recover_state method exists and is callable."""
    print("\n" + "="*60)
    print("TEST: Recover State Method")
    print("="*60)

    repo_path, temp_dir = await setup_test_repo()

    try:
        manager = WorktreeManager(
            project_path=repo_path,
            project_id='test-method-456',
            worktree_dir='.worktrees'
        )
        await manager.initialize()

        # Test that method exists
        print("\n1. Checking recover_state method exists...")
        if hasattr(manager, 'recover_state') and callable(manager.recover_state):
            print("   [OK] recover_state method exists")
        else:
            print("   [FAIL] recover_state method not found")
            return False

        # Test calling it
        print("\n2. Calling recover_state...")
        result = await manager.recover_state()

        print(f"   Result: {result}")

        # Verify result structure
        if 'recovered_count' in result and 'cleaned_count' in result and 'errors' in result:
            print("   [PASS] recover_state returns correct structure")
            return True
        else:
            print("   [FAIL] recover_state result missing expected fields")
            return False

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\nCleaned up test repo: {temp_dir}")


async def main():
    """Run all recovery tests."""
    print("\n" + "="*60)
    print("WORKTREE DATABASE INTEGRATION & RECOVERY TESTS")
    print("="*60)

    results = []

    # Test 1: Method existence
    try:
        result1 = await test_recover_state_method()
        results.append(('Recover State Method', result1))
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(('Recover State Method', False))

    # Test 2: State recovery
    try:
        result2 = await test_state_recovery()
        results.append(('State Recovery', result2))
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(('State Recovery', False))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{test_name:30s} {status}")

    all_passed = all(result for _, result in results)
    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("="*60)

    return 0 if all_passed else 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
