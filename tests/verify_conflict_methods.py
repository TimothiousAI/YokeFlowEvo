"""
Simple verification that conflict detection methods exist and are callable.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.worktree_manager import WorktreeManager


async def verify_methods():
    """Verify that all required methods are implemented."""
    print("Verifying WorktreeManager conflict methods...")

    # Create a manager instance
    manager = WorktreeManager(
        project_path=".",
        project_id="test-123",
        worktree_dir=".worktrees"
    )

    # Check that methods exist and are callable
    methods_to_check = [
        '_check_merge_conflicts',
        'get_conflict_details',
        'resolve_conflict'
    ]

    all_exist = True
    for method_name in methods_to_check:
        if hasattr(manager, method_name):
            method = getattr(manager, method_name)
            if callable(method):
                print(f"  [OK] {method_name} exists and is callable")
            else:
                print(f"  [FAIL] {method_name} exists but is not callable")
                all_exist = False
        else:
            print(f"  [FAIL] {method_name} does not exist")
            all_exist = False

    # Verify method signatures
    import inspect

    # Check _check_merge_conflicts(branch: str) -> bool
    sig = inspect.signature(manager._check_merge_conflicts)
    params = list(sig.parameters.keys())
    if params == ['branch']:
        print(f"  [OK] _check_merge_conflicts has correct signature")
    else:
        print(f"  [FAIL] _check_merge_conflicts signature incorrect: {params}")
        all_exist = False

    # Check get_conflict_details(epic_id: int) -> List[Dict[str, Any]]
    sig = inspect.signature(manager.get_conflict_details)
    params = list(sig.parameters.keys())
    if params == ['epic_id']:
        print(f"  [OK] get_conflict_details has correct signature")
    else:
        print(f"  [FAIL] get_conflict_details signature incorrect: {params}")
        all_exist = False

    # Check resolve_conflict(epic_id: int, strategy: str = 'manual')
    sig = inspect.signature(manager.resolve_conflict)
    params = list(sig.parameters.keys())
    if params == ['epic_id', 'strategy']:
        print(f"  [OK] resolve_conflict has correct signature")
    else:
        print(f"  [FAIL] resolve_conflict signature incorrect: {params}")
        all_exist = False

    if all_exist:
        print("\n[PASS] All conflict detection and resolution methods implemented correctly")
        return 0
    else:
        print("\n[FAIL] Some methods are missing or incorrect")
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(verify_methods())
    sys.exit(exit_code)
