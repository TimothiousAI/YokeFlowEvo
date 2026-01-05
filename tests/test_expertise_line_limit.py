"""
Test script for ExpertiseManager._enforce_line_limit() functionality.

This script tests line limit enforcement to ensure it:
- Keeps expertise under MAX_EXPERTISE_LINES (1000)
- Removes oldest failure learnings first
- Preserves most relevant content
- Applies intelligent pruning strategy
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.learning.expertise_manager import ExpertiseManager, MAX_EXPERTISE_LINES
from core.database_connection import DatabaseManager


async def test_enforce_line_limit():
    """Test line limit enforcement."""

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
        print("Testing ExpertiseManager._enforce_line_limit()")
        print("=" * 80)

        # Test 1: Create large expertise content
        print("\n[TEST 1] Creating oversized expertise content...")

        large_content = {
            'core_files': [f'file_{i}.py' for i in range(200)],  # 200 files
            'patterns': [
                {
                    'name': f'Pattern {i}',
                    'description': f'This is a test pattern number {i} with some description that is quite long to increase line count',
                    'when_to_use': 'For testing purposes in various scenarios',
                    'language': 'python'
                }
                for i in range(100)  # 100 patterns
            ],
            'techniques': [
                {
                    'name': f'Technique {i}',
                    'steps': [f'Step {j} with detailed instructions' for j in range(10)]
                }
                for i in range(50)  # 50 techniques
            ],
            'learnings': []
        }

        # Add recent failures
        for i in range(10):
            large_content['learnings'].append({
                'type': 'failure',
                'lesson': f'Recent failure {i}',
                'date': datetime.now().isoformat()
            })

        # Add old failures (should be removed)
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        for i in range(20):
            large_content['learnings'].append({
                'type': 'failure',
                'lesson': f'Old failure {i}',
                'date': old_date
            })

        # Add successes (should be kept)
        for i in range(10):
            large_content['learnings'].append({
                'type': 'success',
                'lesson': f'Success {i}',
                'date': datetime.now().isoformat()
            })

        # Calculate initial line count
        initial_lines = len(json.dumps(large_content, indent=2).split('\n'))
        print(f"Created content with {initial_lines} lines")
        print(f"  - {len(large_content['core_files'])} core files")
        print(f"  - {len(large_content['patterns'])} patterns")
        print(f"  - {len(large_content['techniques'])} techniques")
        print(f"  - {len(large_content['learnings'])} learnings")

        # Test 2: Enforce line limit
        print(f"\n[TEST 2] Enforcing line limit (MAX={MAX_EXPERTISE_LINES})...")
        pruned_content = manager._enforce_line_limit(large_content)

        pruned_lines = len(json.dumps(pruned_content, indent=2).split('\n'))
        print(f"After pruning: {pruned_lines} lines")
        print(f"  - {len(pruned_content.get('core_files', []))} core files")
        print(f"  - {len(pruned_content.get('patterns', []))} patterns")
        print(f"  - {len(pruned_content.get('techniques', []))} techniques")
        print(f"  - {len(pruned_content.get('learnings', []))} learnings")

        # Test 3: Verify under limit
        print(f"\n[TEST 3] Verifying line limit...")
        if pruned_lines <= MAX_EXPERTISE_LINES:
            print(f"[OK] Content under limit ({pruned_lines} <= {MAX_EXPERTISE_LINES})")
        else:
            print(f"[FAIL] Content exceeds limit ({pruned_lines} > {MAX_EXPERTISE_LINES})")

        # Test 4: Verify old failures removed
        print(f"\n[TEST 4] Verifying old failures removed...")
        old_failures = [
            l for l in pruned_content.get('learnings', [])
            if l.get('type') == 'failure' and 'Old failure' in l.get('lesson', '')
        ]

        if len(old_failures) == 0:
            print(f"[OK] All old failures (>30 days) removed")
        else:
            print(f"[FAIL] {len(old_failures)} old failures still present")

        # Test 5: Verify successes preserved
        print(f"\n[TEST 5] Verifying successes preserved...")
        successes = [
            l for l in pruned_content.get('learnings', [])
            if l.get('type') == 'success'
        ]

        if len(successes) > 0:
            print(f"[OK] {len(successes)} successes preserved")
        else:
            print(f"[WARN] No successes preserved")

        # Test 6: Verify recent failures preserved
        print(f"\n[TEST 6] Verifying recent failures preserved...")
        recent_failures = [
            l for l in pruned_content.get('learnings', [])
            if l.get('type') == 'failure' and 'Recent failure' in l.get('lesson', '')
        ]

        if len(recent_failures) > 0:
            print(f"[OK] {len(recent_failures)} recent failures preserved")
        else:
            print(f"[WARN] No recent failures preserved")

        # Test 7: Test with already small content
        print(f"\n[TEST 7] Testing with content already under limit...")
        small_content = {
            'core_files': ['file1.py', 'file2.py'],
            'patterns': [{'name': 'Test pattern'}],
            'learnings': [{'lesson': 'Test learning'}]
        }

        small_pruned = manager._enforce_line_limit(small_content)
        if small_pruned == small_content:
            print(f"[OK] Small content unchanged")
        else:
            print(f"[WARN] Small content was modified")

        print("\n" + "=" * 80)
        print("[OK] All line limit enforcement tests completed!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_enforce_line_limit())
