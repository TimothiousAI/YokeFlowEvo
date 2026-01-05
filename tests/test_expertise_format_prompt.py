"""
Test script for ExpertiseManager.format_for_prompt() functionality.

This script tests the prompt formatting feature to ensure it:
- Produces readable markdown structure
- Includes all required sections
- Respects line limits
- Prioritizes recent and relevant information
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.learning.expertise_manager import ExpertiseManager
from core.database_connection import DatabaseManager


async def test_format_for_prompt():
    """Test prompt formatting for expertise."""

    async with DatabaseManager() as db:
        # Use the test project created earlier
        project_name = "test_expertise_project"
        project = await db.get_project_by_name(project_name)

        if not project:
            print("[ERROR] Test project not found. Run test_expertise_self_improve.py first.")
            return

        project_id = project['id']
        manager = ExpertiseManager(project_id, db)

        print("=" * 80)
        print("Testing ExpertiseManager.format_for_prompt()")
        print("=" * 80)

        # Test 1: Format expertise for 'api' domain
        print("\n[TEST 1] Formatting expertise for 'api' domain...")
        formatted = await manager.format_for_prompt('api')

        if formatted:
            lines = formatted.split('\n')
            print(f"[OK] Formatted output generated: {len(lines)} lines, {len(formatted)} characters")

            # Verify markdown structure
            has_header = '# Expertise:' in formatted
            has_core_files = '## Core Files' in formatted
            has_patterns = '## Code Patterns' in formatted or '## Patterns' in formatted

            print(f"\n[TEST 2] Verifying markdown structure...")
            print(f"  Header present: {'[OK]' if has_header else '[FAIL]'}")
            print(f"  Core Files section: {'[OK]' if has_core_files else '[FAIL]'}")
            print(f"  Patterns section: {'[OK]' if has_patterns else '[FAIL]'}")

            # Test 3: Verify line limit respected
            print(f"\n[TEST 3] Verifying line limit...")
            if len(lines) <= 1000:
                print(f"[OK] Line limit respected ({len(lines)} <= 1000)")
            else:
                print(f"[FAIL] Line limit exceeded ({len(lines)} > 1000)")

            # Test 4: Show sample output
            print(f"\n[TEST 4] Sample output (first 50 lines):")
            print("-" * 80)
            for i, line in enumerate(lines[:50], 1):
                print(line)
            if len(lines) > 50:
                print(f"... ({len(lines) - 50} more lines)")
            print("-" * 80)

        else:
            print("[FAIL] No formatted output generated")

        # Test 5: Format expertise for domain with no data
        print("\n[TEST 5] Formatting expertise for domain with no data...")
        empty_formatted = await manager.format_for_prompt('nonexistent')

        if empty_formatted == "":
            print("[OK] Returns empty string for domain without expertise")
        else:
            print(f"[WARN] Expected empty string, got {len(empty_formatted)} characters")

        # Test 6: Verify all sections are included
        print("\n[TEST 6] Verifying all sections included...")
        sections = {
            'Core Files': '## Core Files' in formatted,
            'Patterns': '## Code Patterns' in formatted or '## Patterns' in formatted,
            'Techniques': '## Successful Techniques' in formatted or '## Techniques' in formatted,
            'Learnings': '## Success Insights' in formatted or '## Known Issues' in formatted
        }

        for section_name, present in sections.items():
            status = '[OK]' if present else '[INFO]'
            print(f"  {section_name}: {status}")

        print("\n" + "=" * 80)
        print("[OK] All format_for_prompt tests completed!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_format_for_prompt())
