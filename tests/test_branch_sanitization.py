"""
Test script for branch name sanitization with Windows compatibility.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.worktree_manager import WorktreeManager


def test_sanitize_branch_name():
    """Test branch name sanitization."""
    print("\n" + "="*60)
    print("TEST: Branch Name Sanitization")
    print("="*60)

    # Create manager instance (no need for real repo)
    manager = WorktreeManager(
        project_path=".",
        project_id="test-123",
        worktree_dir=".worktrees"
    )

    test_cases = [
        # (input, description, expected_behavior)
        ("CON", "Windows reserved name CON", lambda x: x != "con" and "epic" in x),
        ("PRN", "Windows reserved name PRN", lambda x: x != "prn" and "epic" in x),
        ("AUX", "Windows reserved name AUX", lambda x: x != "aux" and "epic" in x),
        ("NUL", "Windows reserved name NUL", lambda x: x != "nul" and "epic" in x),
        ("COM1", "Windows reserved name COM1", lambda x: x != "com1" and "epic" in x),
        ("LPT9", "Windows reserved name LPT9", lambda x: x != "lpt9" and "epic" in x),

        ("file:name", "Colon removed", lambda x: ':' not in x),
        ("file*name", "Asterisk removed", lambda x: '*' not in x),
        ("file?name", "Question mark removed", lambda x: '?' not in x),
        ('file"name', "Quote removed", lambda x: '"' not in x),
        ("file<name", "Less-than removed", lambda x: '<' not in x),
        ("file>name", "Greater-than removed", lambda x: '>' not in x),
        ("file|name", "Pipe removed", lambda x: '|' not in x),
        ("file\\name", "Backslash removed", lambda x: '\\' not in x),
        ("file/name", "Forward slash removed", lambda x: '/' not in x),

        ("My Epic Feature", "Spaces to hyphens", lambda x: ' ' not in x and '-' in x),
        ("my_epic_feature", "Underscores to hyphens", lambda x: '_' not in x and '-' in x),

        ("UPPERCASE", "Lowercase conversion", lambda x: x.islower()),
        ("MixedCase", "Lowercase conversion", lambda x: x.islower()),

        ("a" * 250, "Long name truncated", lambda x: len(x) <= 200),

        ("---name---", "Trim leading/trailing hyphens", lambda x: not x.startswith('-') and not x.endswith('-')),
        ("...name...", "Trim leading/trailing dots", lambda x: not x.startswith('.') and not x.endswith('.')),

        ("multiple---hyphens", "Consecutive hyphens collapsed", lambda x: '---' not in x),
    ]

    passed = 0
    failed = 0

    print("\nRunning sanitization tests...")
    print()

    for input_name, description, check_func in test_cases:
        result = manager._sanitize_branch_name(input_name)

        # Apply check function
        if check_func(result):
            print(f"[PASS] {description:40s} '{input_name}' -> '{result}'")
            passed += 1
        else:
            print(f"[FAIL] {description:40s} '{input_name}' -> '{result}'")
            failed += 1

    print()
    print("="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)

    return failed == 0


if __name__ == '__main__':
    success = test_sanitize_branch_name()
    sys.exit(0 if success else 1)
