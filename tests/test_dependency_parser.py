"""
Test dependency parser module
"""

import sys
sys.path.insert(0, '.')

from core.parallel.dependency_parser import (
    parse_explicit_dependencies,
    infer_dependencies,
    validate_dependencies,
    parse_and_validate,
    enrich_tasks_with_dependencies
)


def test_parse_explicit_dependencies():
    """Test parsing explicit depends_on field"""
    print("\n=== Test 1: Parse Explicit Dependencies ===")

    # Test with valid dependencies
    task1 = {
        'id': 5,
        'depends_on': [1, 2, 3]
    }
    deps = parse_explicit_dependencies(task1)
    print(f"Task with depends_on=[1,2,3]: {deps}")
    assert deps == [1, 2, 3], f"Expected [1,2,3], got {deps}"

    # Test with empty dependencies
    task2 = {
        'id': 6,
        'depends_on': []
    }
    deps = parse_explicit_dependencies(task2)
    print(f"Task with depends_on=[]: {deps}")
    assert deps == [], f"Expected [], got {deps}"

    # Test with missing depends_on field
    task3 = {
        'id': 7
    }
    deps = parse_explicit_dependencies(task3)
    print(f"Task without depends_on: {deps}")
    assert deps == [], f"Expected [], got {deps}"

    # Test with None
    task4 = {
        'id': 8,
        'depends_on': None
    }
    deps = parse_explicit_dependencies(task4)
    print(f"Task with depends_on=None: {deps}")
    assert deps == [], f"Expected [], got {deps}"

    print("[PASS]")


def test_infer_dependencies():
    """Test inferring dependencies from text"""
    print("\n=== Test 2: Infer Dependencies from Text ===")

    all_tasks = [
        {'id': 1, 'description': 'Create database schema'},
        {'id': 2, 'description': 'Setup API server'},
        {'id': 3, 'description': 'Build frontend UI'},
    ]

    # Test "requires task N" pattern
    desc = "Create user authentication"
    action = "Requires task 1 to be completed. Uses database from task 1."
    inferred = infer_dependencies(desc, action, all_tasks)
    print(f"Text with 'Requires task 1': {inferred}")
    assert 1 in inferred, f"Should infer dependency on task 1, got {inferred}"

    # Test "depends on task N" pattern
    desc = "Add user management"
    action = "Depends on task 2 for API endpoints."
    inferred = infer_dependencies(desc, action, all_tasks)
    print(f"Text with 'Depends on task 2': {inferred}")
    assert 2 in inferred, f"Should infer dependency on task 2, got {inferred}"

    # Test "after task N" pattern
    desc = "Deploy application"
    action = "After task 3 is done, deploy to production."
    inferred = infer_dependencies(desc, action, all_tasks)
    print(f"Text with 'After task 3': {inferred}")
    assert 3 in inferred, f"Should infer dependency on task 3, got {inferred}"

    # Test no dependencies
    desc = "Write documentation"
    action = "Create README with setup instructions."
    inferred = infer_dependencies(desc, action, all_tasks)
    print(f"Text with no dependency keywords: {inferred}")
    assert len(inferred) == 0, f"Should have no inferred deps, got {inferred}"

    print("[PASS]")


def test_validate_dependencies():
    """Test dependency validation"""
    print("\n=== Test 3: Validate Dependencies ===")

    all_task_ids = {1, 2, 3, 4, 5}

    # Test all valid dependencies
    valid, invalid = validate_dependencies([1, 2, 3], all_task_ids)
    print(f"Valid deps [1,2,3]: valid={valid}, invalid={invalid}")
    assert valid == [1, 2, 3], f"Expected all valid, got {valid}"
    assert invalid == [], f"Expected no invalid, got {invalid}"

    # Test mixed valid/invalid
    valid, invalid = validate_dependencies([2, 99, 3, 100], all_task_ids)
    print(f"Mixed deps [2,99,3,100]: valid={valid}, invalid={invalid}")
    assert set(valid) == {2, 3}, f"Expected {{2,3}} valid, got {valid}"
    assert set(invalid) == {99, 100}, f"Expected {{99,100}} invalid, got {invalid}"

    # Test all invalid
    valid, invalid = validate_dependencies([999, 1000], all_task_ids)
    print(f"Invalid deps [999,1000]: valid={valid}, invalid={invalid}")
    assert valid == [], f"Expected no valid, got {valid}"
    assert set(invalid) == {999, 1000}, f"Expected all invalid, got {invalid}"

    print("[PASS]")


def test_parse_and_validate():
    """Test combined parsing and validation"""
    print("\n=== Test 4: Parse and Validate Combined ===")

    all_tasks = [
        {'id': 1, 'description': 'Task 1', 'action': ''},
        {'id': 2, 'description': 'Task 2', 'action': '', 'depends_on': [1]},
        {'id': 3, 'description': 'Task 3', 'action': 'Requires task 2', 'depends_on': [99]},  # Invalid + inferred
    ]

    # Task with valid explicit deps
    result = parse_and_validate(all_tasks[1], all_tasks, enable_inference=False)
    print(f"Task 2 (depends_on=[1]): {result}")
    assert result['explicit'] == [1], "Should have explicit dep on 1"
    assert result['valid'] == [1], "Should have valid dep on 1"
    assert result['invalid'] == [], "Should have no invalid deps"

    # Task with invalid explicit and inferred deps
    result = parse_and_validate(all_tasks[2], all_tasks, enable_inference=True)
    print(f"Task 3 (depends_on=[99], infers 2): {result}")
    assert 99 in result['explicit'], "Should have explicit dep on 99"
    assert 2 in result['inferred'], "Should infer dep on 2"
    assert 2 in result['valid'], "Should have valid dep on 2"
    assert 99 in result['invalid'], "Should have invalid dep on 99"

    print("[PASS]")


def test_enrich_tasks():
    """Test bulk task enrichment"""
    print("\n=== Test 5: Enrich Tasks with Dependencies ===")

    tasks = [
        {'id': 1, 'description': 'Database setup', 'action': 'Create schema', 'depends_on': []},
        {'id': 2, 'description': 'API server', 'action': 'Requires task 1', 'depends_on': None},
        {'id': 3, 'description': 'Frontend', 'action': 'Depends on task 2', 'depends_on': []},
    ]

    # Enrich with inference enabled
    enriched = enrich_tasks_with_dependencies(tasks, enable_inference=True)

    print(f"Task 1 deps: {enriched[0].get('depends_on')}")
    print(f"Task 2 deps: {enriched[1].get('depends_on')} (inferred: {enriched[1].get('_inferred_dependencies')})")
    print(f"Task 3 deps: {enriched[2].get('depends_on')} (inferred: {enriched[2].get('_inferred_dependencies')})")

    # Task 1 should have no deps
    assert enriched[0]['depends_on'] == [], "Task 1 should have no deps"

    # Task 2 should infer dependency on task 1
    assert 1 in enriched[1]['depends_on'], "Task 2 should depend on task 1"

    # Task 3 should infer dependency on task 2
    assert 2 in enriched[2]['depends_on'], "Task 3 should depend on task 2"

    print("[PASS]")


def test_self_reference_exclusion():
    """Test that tasks don't infer dependencies on themselves"""
    print("\n=== Test 6: Self-Reference Exclusion ===")

    all_tasks = [
        {'id': 1, 'description': 'Task 1', 'action': 'Do task 1 things'},
        {'id': 2, 'description': 'Task 2', 'action': 'Complete task 2'},
    ]

    # Task 1 mentions "task 1" but shouldn't depend on itself
    desc = "Complete task 1"
    action = "After task 1 is done, verify task 1 results."
    inferred = infer_dependencies(desc, action, all_tasks, exclude_task_id=1)
    print(f"Task 1 mentioning itself (with exclude_task_id=1): {inferred}")
    assert 1 not in inferred, f"Task should not depend on itself, got {inferred}"

    print("[PASS]")


def run_all_tests():
    """Run all parser tests"""
    print("\n" + "="*70)
    print("Running Dependency Parser Tests")
    print("="*70)

    try:
        test_parse_explicit_dependencies()
        test_infer_dependencies()
        test_validate_dependencies()
        test_parse_and_validate()
        test_enrich_tasks()
        test_self_reference_exclusion()

        print("\n" + "="*70)
        print("[SUCCESS] ALL PARSER TESTS PASSED")
        print("="*70)
        return True

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
