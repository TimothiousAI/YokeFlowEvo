"""
Test script for WorktreeManager conflict detection and resolution.

This script tests:
- Conflict detection using _check_merge_conflicts()
- Getting conflict details with get_conflict_details()
- Conflict resolution strategies (ours, theirs, manual)
"""

import asyncio
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.worktree_manager import WorktreeManager, GitCommandError, WorktreeConflictError


async def setup_test_repo():
    """Create a temporary test repository with a conflict scenario."""
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix='worktree_test_')
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


async def test_conflict_detection():
    """Test conflict detection with _check_merge_conflicts()."""
    print("\n" + "="*60)
    print("TEST: Conflict Detection")
    print("="*60)

    repo_path, temp_dir = await setup_test_repo()

    try:
        # Initialize WorktreeManager
        manager = WorktreeManager(
            project_path=repo_path,
            project_id='test-project-123',
            worktree_dir='.worktrees'
        )
        await manager.initialize()

        # Create first worktree and modify file
        print("\n1. Creating first worktree (epic 100)...")
        wt1 = await manager.create_worktree(100, "Test Epic 1")
        print(f"   Created: {wt1.path}")

        # Modify file in first worktree
        test_file1 = Path(wt1.path) / 'test.txt'
        test_file1.write_text('Line 1 - Modified in Epic 100\nLine 2\nLine 3\n')

        # Commit changes in first worktree
        os.system(f'cd "{wt1.path}" && git add test.txt')
        os.system(f'cd "{wt1.path}" && git commit -m "Epic 100 changes"')
        print("   [OK] Modified and committed changes")

        # Merge first worktree
        print("\n2. Merging first worktree...")
        merge_commit = await manager.merge_worktree(100)
        print(f"   [OK] Merged: {merge_commit[:8]}")

        # Create second worktree and modify SAME file differently
        print("\n3. Creating second worktree (epic 101)...")
        wt2 = await manager.create_worktree(101, "Test Epic 2")
        print(f"   Created: {wt2.path}")

        # Modify same line in second worktree
        test_file2 = Path(wt2.path) / 'test.txt'
        test_file2.write_text('Line 1 - DIFFERENT change in Epic 101\nLine 2\nLine 3\n')

        # Commit changes in second worktree
        os.system(f'cd "{wt2.path}" && git add test.txt')
        os.system(f'cd "{wt2.path}" && git commit -m "Epic 101 changes"')
        print("   [OK] Modified and committed conflicting changes")

        # Test conflict detection
        print("\n4. Testing conflict detection...")
        has_conflicts = await manager._check_merge_conflicts(wt2.branch)
        print(f"   Conflicts detected: {has_conflicts}")

        if has_conflicts:
            print("   [PASS] TEST PASSED: Conflicts detected correctly")
        else:
            print("   [FAIL] TEST FAILED: Conflicts should have been detected")

        # Test get_conflict_details
        print("\n5. Getting conflict details...")
        conflicts = await manager.get_conflict_details(101)
        print(f"   Found {len(conflicts)} conflicting file(s):")
        for conflict in conflicts:
            print(f"     - {conflict['file']}: {conflict['status']}")
            print(f"       {conflict['details']}")

        if len(conflicts) > 0:
            print("   [PASS] TEST PASSED: Conflict details retrieved")
        else:
            print("   [FAIL] TEST FAILED: Should have found conflicts")

        # Cleanup
        await manager.cleanup_worktree(100)
        await manager.cleanup_worktree(101)

        return has_conflicts and len(conflicts) > 0

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\nCleaned up test repo: {temp_dir}")


async def test_conflict_resolution_manual():
    """Test manual conflict resolution strategy."""
    print("\n" + "="*60)
    print("TEST: Manual Conflict Resolution")
    print("="*60)

    repo_path, temp_dir = await setup_test_repo()

    try:
        manager = WorktreeManager(
            project_path=repo_path,
            project_id='test-project-456',
            worktree_dir='.worktrees'
        )
        await manager.initialize()

        # Setup conflict scenario (same as above)
        print("\n1. Setting up conflict scenario...")
        wt1 = await manager.create_worktree(200, "Epic A")
        test_file1 = Path(wt1.path) / 'test.txt'
        test_file1.write_text('Line 1 - Epic A\nLine 2\nLine 3\n')
        os.system(f'cd "{wt1.path}" && git add test.txt && git commit -m "Epic A"')
        await manager.merge_worktree(200)

        wt2 = await manager.create_worktree(201, "Epic B")
        test_file2 = Path(wt2.path) / 'test.txt'
        test_file2.write_text('Line 1 - Epic B\nLine 2\nLine 3\n')
        os.system(f'cd "{wt2.path}" && git add test.txt && git commit -m "Epic B"')
        print("   [OK] Conflict scenario ready")

        # Test manual resolution
        print("\n2. Testing manual conflict resolution...")
        result = await manager.resolve_conflict(201, strategy='manual')

        print(f"   Status: {result['status']}")
        print(f"   Strategy: {result['strategy']}")
        print(f"   Message: {result['message']}")

        if result['status'] == 'manual_required':
            print("   [PASS] TEST PASSED: Manual resolution correctly indicates human intervention needed")
            success = True
        else:
            print("   [FAIL] TEST FAILED: Should require manual resolution")
            success = False

        # Cleanup
        await manager.cleanup_worktree(200)
        await manager.cleanup_worktree(201)

        return success

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\nCleaned up test repo: {temp_dir}")


async def test_conflict_resolution_theirs():
    """Test 'theirs' conflict resolution strategy."""
    print("\n" + "="*60)
    print("TEST: 'Theirs' Conflict Resolution")
    print("="*60)

    repo_path, temp_dir = await setup_test_repo()

    try:
        manager = WorktreeManager(
            project_path=repo_path,
            project_id='test-project-789',
            worktree_dir='.worktrees'
        )
        await manager.initialize()

        # Setup conflict scenario
        print("\n1. Setting up conflict scenario...")
        wt1 = await manager.create_worktree(300, "Epic X")
        test_file1 = Path(wt1.path) / 'test.txt'
        test_file1.write_text('Line 1 - Epic X (will be overwritten)\nLine 2\nLine 3\n')
        os.system(f'cd "{wt1.path}" && git add test.txt && git commit -m "Epic X"')
        await manager.merge_worktree(300)

        wt2 = await manager.create_worktree(301, "Epic Y")
        test_file2 = Path(wt2.path) / 'test.txt'
        test_file2.write_text('Line 1 - Epic Y (should win)\nLine 2\nLine 3\n')
        os.system(f'cd "{wt2.path}" && git add test.txt && git commit -m "Epic Y"')
        print("   [OK] Conflict scenario ready")

        # Test 'theirs' resolution
        print("\n2. Testing 'theirs' conflict resolution...")
        result = await manager.resolve_conflict(301, strategy='theirs')

        print(f"   Status: {result['status']}")
        print(f"   Strategy: {result['strategy']}")
        print(f"   Message: {result['message']}")

        if 'files_resolved' in result:
            print(f"   Files resolved: {result['files_resolved']}")

        # Verify the result - check that Epic Y's changes won
        final_file = Path(repo_path) / 'test.txt'
        content = final_file.read_text()

        if 'Epic Y (should win)' in content:
            print("   [PASS] TEST PASSED: 'theirs' strategy correctly kept worktree changes")
            success = True
        else:
            print("   [FAIL] TEST FAILED: Wrong content in resolved file")
            print(f"   Content: {content}")
            success = False

        # Cleanup
        await manager.cleanup_worktree(300)
        await manager.cleanup_worktree(301)

        return success

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\nCleaned up test repo: {temp_dir}")


async def main():
    """Run all conflict resolution tests."""
    print("\n" + "="*60)
    print("WORKTREE CONFLICT DETECTION & RESOLUTION TESTS")
    print("="*60)

    results = []

    # Test 1: Conflict detection
    try:
        result1 = await test_conflict_detection()
        results.append(('Conflict Detection', result1))
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED with exception: {e}")
        results.append(('Conflict Detection', False))

    # Test 2: Manual resolution
    try:
        result2 = await test_conflict_resolution_manual()
        results.append(('Manual Resolution', result2))
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED with exception: {e}")
        results.append(('Manual Resolution', False))

    # Test 3: Theirs resolution
    try:
        result3 = await test_conflict_resolution_theirs()
        results.append(('Theirs Resolution', result3))
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED with exception: {e}")
        results.append(('Theirs Resolution', False))

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
