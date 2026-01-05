"""
Test script for WorktreeManager sync_worktree_from_main functionality.
"""

import asyncio
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.worktree_manager import WorktreeManager, GitCommandError


async def setup_test_repo():
    """Create a temporary test repository."""
    temp_dir = tempfile.mkdtemp(prefix='worktree_sync_test_')
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


async def test_sync_from_main():
    """Test syncing worktree from main branch."""
    print("\n" + "="*60)
    print("TEST: Sync Worktree from Main")
    print("="*60)

    repo_path, temp_dir = await setup_test_repo()

    try:
        # Initialize WorktreeManager
        manager = WorktreeManager(
            project_path=repo_path,
            project_id='test-sync-123',
            worktree_dir='.worktrees'
        )
        await manager.initialize()

        # Create worktree
        print("\n1. Creating worktree (epic 100)...")
        wt = await manager.create_worktree(100, "Test Sync Epic")
        print(f"   Created: {wt.path}")

        # Make changes in worktree
        worktree_file = Path(wt.path) / 'worktree_feature.txt'
        worktree_file.write_text('Feature implemented in worktree\n')
        os.system(f'cd "{wt.path}" && git add worktree_feature.txt')
        os.system(f'cd "{wt.path}" && git commit -m "Add worktree feature"')
        print("   [OK] Added feature in worktree")

        # Make changes in main branch (simulating other development)
        print("\n2. Making changes in main branch...")
        main_file = Path(repo_path) / 'main_feature.txt'
        main_file.write_text('Feature added to main\n')
        os.system(f'cd "{repo_path}" && git add main_feature.txt')
        os.system(f'cd "{repo_path}" && git commit -m "Add main feature"')
        print("   [OK] Added feature in main")

        # Sync worktree from main
        print("\n3. Syncing worktree from main...")
        result = await manager.sync_worktree_from_main(100, strategy='merge')

        print(f"   Status: {result['status']}")
        print(f"   Strategy: {result['strategy']}")
        print(f"   Message: {result['message']}")

        # Verify sync worked
        if result['status'] == 'success':
            # Check that main's changes are now in worktree
            synced_file = Path(wt.path) / 'main_feature.txt'
            worktree_feature = Path(wt.path) / 'worktree_feature.txt'

            main_exists = synced_file.exists()
            worktree_exists = worktree_feature.exists()

            print(f"\n4. Verifying sync results...")
            print(f"   Main's feature file in worktree: {main_exists}")
            print(f"   Worktree's own feature preserved: {worktree_exists}")

            if main_exists and worktree_exists:
                print("   [PASS] Sync successful - both features present")
                success = True
            else:
                print("   [FAIL] Sync incomplete - missing files")
                success = False
        else:
            print("   [FAIL] Sync failed")
            success = False

        # Cleanup
        await manager.cleanup_worktree(100)

        return success

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\nCleaned up test repo: {temp_dir}")


async def test_sync_with_rebase():
    """Test syncing worktree using rebase strategy."""
    print("\n" + "="*60)
    print("TEST: Sync with Rebase Strategy")
    print("="*60)

    repo_path, temp_dir = await setup_test_repo()

    try:
        manager = WorktreeManager(
            project_path=repo_path,
            project_id='test-rebase-456',
            worktree_dir='.worktrees'
        )
        await manager.initialize()

        # Create worktree
        print("\n1. Creating worktree (epic 200)...")
        wt = await manager.create_worktree(200, "Rebase Test Epic")
        print(f"   Created: {wt.path}")

        # Make changes in worktree
        worktree_file = Path(wt.path) / 'feature.txt'
        worktree_file.write_text('Worktree change\n')
        os.system(f'cd "{wt.path}" && git add feature.txt')
        os.system(f'cd "{wt.path}" && git commit -m "Worktree commit"')
        print("   [OK] Made changes in worktree")

        # Make changes in main
        print("\n2. Making changes in main...")
        main_file = Path(repo_path) / 'main.txt'
        main_file.write_text('Main change\n')
        os.system(f'cd "{repo_path}" && git add main.txt')
        os.system(f'cd "{repo_path}" && git commit -m "Main commit"')
        print("   [OK] Made changes in main")

        # Sync with rebase
        print("\n3. Syncing with rebase strategy...")
        result = await manager.sync_worktree_from_main(200, strategy='rebase')

        print(f"   Status: {result['status']}")
        print(f"   Strategy: {result['strategy']}")
        print(f"   Message: {result['message']}")

        if result['status'] == 'success':
            print("   [PASS] Rebase sync successful")
            success = True
        else:
            print("   [FAIL] Rebase sync failed")
            success = False

        # Cleanup
        await manager.cleanup_worktree(200)

        return success

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\nCleaned up test repo: {temp_dir}")


async def main():
    """Run all sync tests."""
    print("\n" + "="*60)
    print("WORKTREE SYNC FROM MAIN TESTS")
    print("="*60)

    results = []

    # Test 1: Basic sync
    try:
        result1 = await test_sync_from_main()
        results.append(('Sync from Main', result1))
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(('Sync from Main', False))

    # Test 2: Rebase strategy
    try:
        result2 = await test_sync_with_rebase()
        results.append(('Rebase Strategy', result2))
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(('Rebase Strategy', False))

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
