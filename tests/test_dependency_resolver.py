"""
Test DependencyResolver implementation
"""

import sys
sys.path.insert(0, '.')

from core.parallel.dependency_resolver import DependencyResolver, DependencyGraph


def test_simple_batching():
    """Test basic parallel batching without dependencies"""
    print("\n=== Test 1: Simple Batching (no dependencies) ===")

    tasks = [
        {'id': 1, 'priority': 1},
        {'id': 2, 'priority': 2},
        {'id': 3, 'priority': 3},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)

    print(f"Batches: {graph.batches}")
    print(f"Task order: {graph.task_order}")
    print(f"Circular deps: {graph.circular_deps}")
    print(f"Missing deps: {graph.missing_deps}")

    # All tasks should be in first batch (no dependencies)
    assert len(graph.batches) == 1, f"Expected 1 batch, got {len(graph.batches)}"
    assert len(graph.batches[0]) == 3, f"Expected 3 tasks in batch, got {len(graph.batches[0])}"
    # Should be sorted by priority
    assert graph.batches[0] == [1, 2, 3], f"Expected [1,2,3], got {graph.batches[0]}"
    assert graph.circular_deps == [], "Should have no circular deps"
    assert graph.missing_deps == [], "Should have no missing deps"

    print("[PASS]")


def test_linear_dependencies():
    """Test linear dependency chain: 1 -> 2 -> 3"""
    print("\n=== Test 2: Linear Dependencies (1 -> 2 -> 3) ===")

    tasks = [
        {'id': 1, 'priority': 1, 'depends_on': []},
        {'id': 2, 'priority': 2, 'depends_on': [1], 'dependency_type': 'hard'},
        {'id': 3, 'priority': 3, 'depends_on': [2], 'dependency_type': 'hard'},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)

    print(f"Batches: {graph.batches}")
    print(f"Task order: {graph.task_order}")

    # Should have 3 batches (sequential execution)
    assert len(graph.batches) == 3, f"Expected 3 batches, got {len(graph.batches)}"
    assert graph.batches[0] == [1], f"Expected batch 0 = [1], got {graph.batches[0]}"
    assert graph.batches[1] == [2], f"Expected batch 1 = [2], got {graph.batches[1]}"
    assert graph.batches[2] == [3], f"Expected batch 2 = [3], got {graph.batches[2]}"
    assert graph.task_order == [1, 2, 3], f"Expected order [1,2,3], got {graph.task_order}"

    print("[PASS]")


def test_parallel_batching():
    """Test parallel batching with diamond dependency"""
    print("\n=== Test 3: Parallel Batching (Diamond: 1 -> {2,3} -> 4) ===")

    tasks = [
        {'id': 1, 'priority': 1, 'depends_on': []},
        {'id': 2, 'priority': 2, 'depends_on': [1], 'dependency_type': 'hard'},
        {'id': 3, 'priority': 3, 'depends_on': [1], 'dependency_type': 'hard'},
        {'id': 4, 'priority': 4, 'depends_on': [2, 3], 'dependency_type': 'hard'},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)

    print(f"Batches: {graph.batches}")
    print(f"Task order: {graph.task_order}")

    # Should have 3 batches: [1], [2,3], [4]
    assert len(graph.batches) == 3, f"Expected 3 batches, got {len(graph.batches)}"
    assert graph.batches[0] == [1], f"Expected batch 0 = [1], got {graph.batches[0]}"
    assert set(graph.batches[1]) == {2, 3}, f"Expected batch 1 = {{2,3}}, got {graph.batches[1]}"
    assert graph.batches[2] == [4], f"Expected batch 2 = [4], got {graph.batches[2]}"

    print("[PASS]")


def test_circular_dependency():
    """Test circular dependency detection: 1 -> 2 -> 3 -> 1"""
    print("\n=== Test 4: Circular Dependency Detection (1->2->3->1) ===")

    tasks = [
        {'id': 1, 'priority': 1, 'depends_on': [3], 'dependency_type': 'hard'},
        {'id': 2, 'priority': 2, 'depends_on': [1], 'dependency_type': 'hard'},
        {'id': 3, 'priority': 3, 'depends_on': [2], 'dependency_type': 'hard'},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)

    print(f"Batches: {graph.batches}")
    print(f"Task order: {graph.task_order}")
    print(f"Circular deps: {graph.circular_deps}")

    # Should detect circular dependency
    assert len(graph.circular_deps) > 0, "Should detect circular dependency"
    # All tasks should remain unprocessed
    assert len(graph.batches) == 0, f"Expected 0 batches (circular), got {len(graph.batches)}"

    print("[PASS] - Circular dependency detected")


def test_missing_dependency():
    """Test missing dependency detection"""
    print("\n=== Test 5: Missing Dependency Detection ===")

    tasks = [
        {'id': 1, 'priority': 1, 'depends_on': []},
        {'id': 2, 'priority': 2, 'depends_on': [999], 'dependency_type': 'hard'},  # Invalid
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)

    print(f"Batches: {graph.batches}")
    print(f"Missing deps: {graph.missing_deps}")

    # Should detect missing dependency
    assert 2 in graph.missing_deps, f"Expected task 2 in missing_deps, got {graph.missing_deps}"
    # Task 1 should still be processed
    assert 1 in graph.task_order, "Task 1 should be in task_order"

    print("[PASS] - Missing dependency detected")


def test_soft_dependencies():
    """Test soft dependencies don't block execution"""
    print("\n=== Test 6: Soft Dependencies (non-blocking) ===")

    tasks = [
        {'id': 1, 'priority': 1, 'depends_on': []},
        {'id': 2, 'priority': 2, 'depends_on': [1], 'dependency_type': 'soft'},  # Soft
        {'id': 3, 'priority': 3, 'depends_on': [1], 'dependency_type': 'hard'},  # Hard
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)

    print(f"Batches: {graph.batches}")
    print(f"Task order: {graph.task_order}")

    # Task 2 (soft dependency) can run in parallel with task 1
    # Task 3 (hard dependency) must wait for task 1
    assert len(graph.batches) == 2, f"Expected 2 batches, got {len(graph.batches)}"
    # Batch 0 should have tasks with no hard dependencies
    assert 1 in graph.batches[0], "Task 1 should be in batch 0"
    assert 2 in graph.batches[0], "Task 2 (soft dep) should be in batch 0"
    # Batch 1 should have task 3 (hard dependency on 1)
    assert 3 in graph.batches[1], "Task 3 should be in batch 1"

    print("[PASS]")


def test_priority_ordering():
    """Test priority ordering within batches"""
    print("\n=== Test 7: Priority Ordering Within Batches ===")

    tasks = [
        {'id': 1, 'priority': 5, 'depends_on': []},
        {'id': 2, 'priority': 1, 'depends_on': []},  # Highest priority
        {'id': 3, 'priority': 3, 'depends_on': []},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)

    print(f"Batches: {graph.batches}")
    print(f"Task order: {graph.task_order}")

    # Should be sorted by priority (lower = higher priority)
    assert graph.batches[0] == [2, 3, 1], f"Expected [2,3,1], got {graph.batches[0]}"

    print("[PASS]")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("Running DependencyResolver Tests")
    print("="*60)

    try:
        test_simple_batching()
        test_linear_dependencies()
        test_parallel_batching()
        test_circular_dependency()
        test_missing_dependency()
        test_soft_dependencies()
        test_priority_ordering()

        print("\n" + "="*60)
        print("[SUCCESS] ALL TESTS PASSED")
        print("="*60)
        return True

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
