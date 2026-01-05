#!/usr/bin/env python3
"""
Test CLI parallel execution flags.

Tests that the CLI properly handles:
- --parallel flag
- --max-concurrency option
- --merge-strategy option
- Validation of concurrency range
- Help text documentation
"""

import subprocess
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_help_text():
    """Test that help text documents parallel flags."""
    result = subprocess.run(
        ['python', 'scripts/run_self_enhancement.py', '--help'],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    help_text = result.stdout

    # Check all flags are documented
    assert '--parallel' in help_text, "Missing --parallel flag in help"
    assert '--max-concurrency' in help_text, "Missing --max-concurrency flag in help"
    assert '--merge-strategy' in help_text, "Missing --merge-strategy flag in help"

    # Check examples are present
    assert 'Examples:' in help_text, "Missing examples section"
    assert 'parallel' in help_text.lower(), "Examples don't mention parallel execution"

    print("PASS: Help text documents all parallel flags")


def test_concurrency_validation():
    """Test that max-concurrency is validated (1-10 range)."""
    # Test invalid value (too high)
    result = subprocess.run(
        ['python', 'scripts/run_self_enhancement.py', '--coding', '--parallel', '--max-concurrency', '15'],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    assert result.returncode != 0, "Should fail with concurrency > 10"
    assert 'must be between 1 and 10' in result.stdout or 'must be between 1 and 10' in result.stderr, \
        "Should show validation error message"

    print("PASS: Concurrency validation works (rejects value > 10)")

    # Test invalid value (too low)
    result = subprocess.run(
        ['python', 'scripts/run_self_enhancement.py', '--coding', '--parallel', '--max-concurrency', '0'],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    assert result.returncode != 0, "Should fail with concurrency < 1"
    assert 'must be between 1 and 10' in result.stdout or 'must be between 1 and 10' in result.stderr, \
        "Should show validation error message"

    print("PASS: Concurrency validation works (rejects value < 1)")


def test_merge_strategy_choices():
    """Test that merge-strategy only accepts valid choices."""
    result = subprocess.run(
        ['python', 'scripts/run_self_enhancement.py', '--coding', '--parallel', '--merge-strategy', 'invalid'],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    assert result.returncode != 0, "Should fail with invalid merge strategy"
    # argparse will show error about invalid choice
    error_output = result.stderr.lower()
    assert 'invalid choice' in error_output or 'choose from' in error_output, \
        "Should show invalid choice error"

    print("PASS: Merge strategy validation works (rejects invalid choices)")


def test_script_imports():
    """Test that the script imports successfully without errors."""
    # This verifies syntax and basic import structure
    result = subprocess.run(
        ['python', '-c', 'import sys; sys.path.insert(0, "scripts"); import run_self_enhancement'],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    if result.returncode != 0:
        print(f"Import failed: {result.stderr}")
        assert False, "Script should import successfully"

    print("PASS: Script imports successfully")


def test_default_values():
    """Test that default values are correct."""
    # Since we can't easily run the full script without a database,
    # we'll just verify the help text shows correct defaults
    result = subprocess.run(
        ['python', 'scripts/run_self_enhancement.py', '--help'],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    help_text = result.stdout

    # Check defaults are documented
    assert 'default: 3' in help_text, "Max concurrency default should be 3"
    assert 'default: regular' in help_text, "Merge strategy default should be regular"
    assert 'default: sequential' in help_text or 'default:\n                        sequential' in help_text, \
        "Parallel mode should default to sequential"

    print("PASS: Default values are correctly documented")


if __name__ == '__main__':
    print("Testing CLI parallel execution flags...")
    print("=" * 60)

    try:
        test_help_text()
        test_concurrency_validation()
        test_merge_strategy_choices()
        test_script_imports()
        test_default_values()

        print("=" * 60)
        print("All tests PASSED")
        sys.exit(0)

    except AssertionError as e:
        print(f"\nTest FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
