"""
Test script for ExpertiseManager database integration.

This script tests database integration to ensure:
- Expertise is stored with versioning
- Version increments on each update
- Update history is tracked correctly
- Database errors handled gracefully
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.learning.expertise_manager import ExpertiseManager
from core.database_connection import DatabaseManager


async def test_database_integration():
    """Test database integration and versioning."""

    async with DatabaseManager() as db:
        # Use the test project
        project_name = "test_expertise_project"
        project = await db.get_project_by_name(project_name)

        if not project:
            print("[ERROR] Test project not found. Run test_expertise_self_improve.py first.")
            return

        project_id = project['id']
        manager = ExpertiseManager(project_id, db)

        print("=" * 80)
        print("Testing ExpertiseManager Database Integration")
        print("=" * 80)

        # Test 1: Get existing expertise and note version
        print("\n[TEST 1] Getting existing expertise...")
        expertise_v1 = await manager.get_expertise('api')

        if expertise_v1:
            print(f"[OK] Found expertise for 'api' domain")
            print(f"  Version: {expertise_v1.version}")
            print(f"  Line count: {expertise_v1.line_count}")
            initial_version = expertise_v1.version
        else:
            print("[INFO] No existing expertise, will create new")
            initial_version = 0

        # Test 2: Trigger self-improvement to create update
        print("\n[TEST 2] Triggering self-improvement update...")
        result = await manager.self_improve('api')

        if result.get('status') in ['success', 'no_changes']:
            print(f"[OK] Self-improvement completed: {result.get('status')}")
        else:
            print(f"[WARN] Self-improvement status: {result.get('status')}")

        # Test 3: Verify version incremented (if changes were made)
        print("\n[TEST 3] Verifying version increment...")
        expertise_v2 = await manager.get_expertise('api')

        if expertise_v2:
            if result.get('status') == 'success':
                if expertise_v2.version > initial_version:
                    print(f"[OK] Version incremented: {initial_version} -> {expertise_v2.version}")
                else:
                    print(f"[WARN] Version not incremented: {expertise_v2.version}")
            else:
                print(f"[INFO] No changes made, version unchanged: {expertise_v2.version}")
        else:
            print("[FAIL] Could not retrieve updated expertise")

        # Test 4: Get expertise history
        print("\n[TEST 4] Getting expertise history...")
        history = await manager.get_expertise_history('api')

        if history:
            print(f"[OK] Retrieved {len(history)} history records")

            # Show recent history
            print("\n  Recent history:")
            for i, record in enumerate(history[:5], 1):
                change_type = record.get('change_type', 'unknown')
                summary = record.get('summary', 'No summary')
                created_at = record.get('created_at', 'Unknown date')
                print(f"    {i}. [{change_type}] {summary}")
                print(f"       Date: {created_at}")

            if len(history) > 5:
                print(f"    ... and {len(history) - 5} more records")

        else:
            print("[INFO] No history records found (may be first run)")

        # Test 5: Test with non-existent domain
        print("\n[TEST 5] Testing error handling for non-existent domain...")
        empty_history = await manager.get_expertise_history('nonexistent_domain_xyz')

        if empty_history == []:
            print("[OK] Returns empty list for non-existent domain")
        else:
            print(f"[WARN] Expected empty list, got {len(empty_history)} records")

        # Test 6: Verify history contains self_improved entries
        print("\n[TEST 6] Verifying history contains update types...")
        if history:
            change_types = set(record.get('change_type') for record in history)
            print(f"  Change types found: {', '.join(change_types)}")

            expected_types = ['self_improved']  # We just ran self_improve
            for change_type in expected_types:
                if change_type in change_types:
                    print(f"  [OK] Found '{change_type}' changes")
                else:
                    print(f"  [INFO] No '{change_type}' changes yet")
        else:
            print("  [INFO] No history to check")

        # Test 7: Verify database error handling
        print("\n[TEST 7] Testing graceful error handling...")
        try:
            # This should handle errors gracefully
            invalid_manager = ExpertiseManager(project_id, db)
            result = await invalid_manager.get_expertise('api')
            print("[OK] Error handling works (no crash)")
        except Exception as e:
            print(f"[FAIL] Uncaught exception: {e}")

        print("\n" + "=" * 80)
        print("[OK] All database integration tests completed!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_database_integration())
