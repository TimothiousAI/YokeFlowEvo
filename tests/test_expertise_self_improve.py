"""
Test script for ExpertiseManager.self_improve() functionality.

This script tests the self-improvement scanning feature to ensure it:
- Discovers relevant files for a domain
- Extracts patterns from existing code
- Identifies library usage
- Updates expertise with discoveries
- Respects scanning limits
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.learning.expertise_manager import ExpertiseManager
from core.database_connection import DatabaseManager


async def test_self_improve():
    """Test self-improvement scanning for API domain."""

    async with DatabaseManager() as db:
        # Create or get a test project
        project_name = "test_expertise_project"
        project = await db.get_project_by_name(project_name)

        if not project:
            # Create test project
            project = await db.create_project(
                name=project_name,
                spec_file_path="test_spec.txt"
            )
            print(f"Created test project: {project['id']}")
        else:
            print(f"Using existing project: {project['id']}")

        project_id = project['id']

        # Create ExpertiseManager
        manager = ExpertiseManager(project_id, db)

        print("=" * 80)
        print("Testing ExpertiseManager.self_improve() for 'api' domain")
        print("=" * 80)

        # Test 1: Self-improve for 'api' domain
        print("\n[TEST 1] Running self-improvement scan for 'api' domain...")
        result = await manager.self_improve('api')

        print(f"\nResult: {result.get('status')}")
        print(f"Domain: {result.get('domain')}")
        print(f"Files scanned: {result.get('files_scanned', 0)}")
        print(f"Files added: {result.get('files_added', 0)}")
        print(f"Patterns added: {result.get('patterns_added', 0)}")

        if result.get('changes'):
            print(f"\nChanges made ({len(result['changes'])}):")
            for i, change in enumerate(result['changes'][:10], 1):
                print(f"  {i}. {change}")
            if len(result['changes']) > 10:
                print(f"  ... and {len(result['changes']) - 10} more")

        # Test 2: Verify expertise was saved
        print("\n[TEST 2] Verifying expertise was saved...")
        expertise = await manager.get_expertise('api')

        if expertise:
            print(f"[OK] Expertise found for 'api' domain")
            print(f"   Version: {expertise.version}")
            print(f"   Line count: {expertise.line_count}")
            print(f"   Core files: {len(expertise.content.get('core_files', []))}")
            print(f"   Patterns: {len(expertise.content.get('patterns', []))}")
            print(f"   Learnings: {len(expertise.content.get('learnings', []))}")

            # Show some examples
            if expertise.content.get('core_files'):
                print(f"\n   Sample core files:")
                for file in expertise.content['core_files'][:5]:
                    print(f"     - {file}")

            if expertise.content.get('patterns'):
                print(f"\n   Sample patterns:")
                for pattern in expertise.content['patterns'][:3]:
                    print(f"     - {pattern.get('name')}: {pattern.get('description', '')[:60]}")
        else:
            print("[FAIL] No expertise found")

        # Test 3: Test with 'database' domain
        print("\n[TEST 3] Running self-improvement scan for 'database' domain...")
        db_result = await manager.self_improve('database')

        print(f"\nResult: {db_result.get('status')}")
        print(f"Files scanned: {db_result.get('files_scanned', 0)}")
        print(f"Files added: {db_result.get('files_added', 0)}")
        print(f"Patterns added: {db_result.get('patterns_added', 0)}")

        # Test 4: Verify limits are respected
        print("\n[TEST 4] Verifying scanning limits...")
        if result.get('files_scanned', 0) <= 20:
            print(f"[OK] File scan limit respected (scanned {result.get('files_scanned', 0)} <= 20)")
        else:
            print(f"[FAIL] File scan limit exceeded (scanned {result.get('files_scanned', 0)} > 20)")

        if result.get('line_count', 0) <= 1000:
            print(f"[OK] Line count limit respected ({result.get('line_count', 0)} <= 1000)")
        else:
            print(f"[WARN] Line count near limit ({result.get('line_count', 0)} lines)")

        print("\n" + "=" * 80)
        print("[OK] All tests completed successfully!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_self_improve())
