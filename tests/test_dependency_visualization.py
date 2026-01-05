"""
Test DependencyResolver visualization methods
"""

import sys
sys.path.insert(0, '.')

from core.parallel.dependency_resolver import DependencyResolver


def test_mermaid_visualization():
    """Test Mermaid diagram generation"""
    print("\n=== Test 1: Mermaid Visualization ===")

    tasks = [
        {'id': 1, 'description': 'Setup database', 'priority': 1, 'depends_on': []},
        {'id': 2, 'description': 'Create API endpoints', 'priority': 2, 'depends_on': [1], 'dependency_type': 'hard'},
        {'id': 3, 'description': 'Build frontend UI', 'priority': 3, 'depends_on': [2], 'dependency_type': 'hard'},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)
    mermaid = resolver.to_mermaid()

    print(mermaid)
    print()

    # Validate Mermaid syntax
    assert mermaid.startswith('graph TD'), "Should start with 'graph TD'"
    assert 'T1' in mermaid, "Should include task 1"
    assert 'T2' in mermaid, "Should include task 2"
    assert 'T3' in mermaid, "Should include task 3"
    assert '-->' in mermaid, "Should have dependency arrows"
    assert 'Setup database' in mermaid, "Should include task description"

    print("[PASS]")


def test_ascii_visualization():
    """Test ASCII text representation"""
    print("\n=== Test 2: ASCII Visualization ===")

    tasks = [
        {'id': 1, 'description': 'Task A', 'priority': 1, 'depends_on': []},
        {'id': 2, 'description': 'Task B', 'priority': 2, 'depends_on': [1], 'dependency_type': 'hard'},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)
    ascii_diagram = resolver.to_ascii()

    print(ascii_diagram)
    print()

    # Validate ASCII output
    assert 'DEPENDENCY GRAPH' in ascii_diagram, "Should have header"
    assert 'BATCH 0' in ascii_diagram, "Should show batch 0"
    assert 'BATCH 1' in ascii_diagram, "Should show batch 1"
    assert 'Task A' in ascii_diagram, "Should include task A"
    assert 'Task B' in ascii_diagram, "Should include task B"
    assert 'Depends on' in ascii_diagram, "Should show dependencies"

    print("[PASS]")


def test_critical_path():
    """Test critical path calculation"""
    print("\n=== Test 3: Critical Path ===")

    # Create a graph with known critical path: 1 -> 2 -> 3 -> 5
    tasks = [
        {'id': 1, 'priority': 1, 'depends_on': []},
        {'id': 2, 'priority': 2, 'depends_on': [1], 'dependency_type': 'hard'},
        {'id': 3, 'priority': 3, 'depends_on': [2], 'dependency_type': 'hard'},
        {'id': 4, 'priority': 4, 'depends_on': [1], 'dependency_type': 'hard'},  # Shorter path
        {'id': 5, 'priority': 5, 'depends_on': [3], 'dependency_type': 'hard'},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)
    critical_path = resolver.get_critical_path()

    print(f"Critical path: {critical_path}")
    print()

    # Critical path should be the longest chain
    assert len(critical_path) > 0, "Should have a critical path"
    # Path should be 1 -> 2 -> 3 -> 5 (length 4)
    assert len(critical_path) == 4, f"Expected length 4, got {len(critical_path)}"
    assert critical_path == [1, 2, 3, 5], f"Expected [1,2,3,5], got {critical_path}"

    print("[PASS]")


def test_filtering():
    """Test epic and batch filtering"""
    print("\n=== Test 4: Filtering (Epic/Batch) ===")

    tasks = [
        {'id': 1, 'epic_id': 10, 'description': 'Epic 10 Task 1', 'priority': 1, 'depends_on': []},
        {'id': 2, 'epic_id': 10, 'description': 'Epic 10 Task 2', 'priority': 2, 'depends_on': [1], 'dependency_type': 'hard'},
        {'id': 3, 'epic_id': 20, 'description': 'Epic 20 Task 1', 'priority': 3, 'depends_on': []},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)

    # Test epic filtering
    mermaid_epic10 = resolver.to_mermaid(epic_filter=10)
    print("Mermaid (Epic 10 only):")
    print(mermaid_epic10)
    print()

    assert 'Epic 10' in mermaid_epic10, "Should include Epic 10 tasks"
    assert 'Epic 20' not in mermaid_epic10, "Should not include Epic 20 tasks"

    # Test batch filtering
    ascii_batch0 = resolver.to_ascii(batch_filter=0)
    print("ASCII (Batch 0 only):")
    print(ascii_batch0)
    print()

    # Batch 0 should have tasks 1 and 3 (no dependencies)
    assert '[1]' in ascii_batch0, "Should include task 1"
    assert '[3]' in ascii_batch0, "Should include task 3"

    print("[PASS]")


def test_circular_dependency_visualization():
    """Test visualization with circular dependencies"""
    print("\n=== Test 5: Circular Dependency Visualization ===")

    tasks = [
        {'id': 1, 'description': 'Task A', 'priority': 1, 'depends_on': [3], 'dependency_type': 'hard'},
        {'id': 2, 'description': 'Task B', 'priority': 2, 'depends_on': [1], 'dependency_type': 'hard'},
        {'id': 3, 'description': 'Task C', 'priority': 3, 'depends_on': [2], 'dependency_type': 'hard'},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)

    # Check Mermaid includes circular dependency comment
    mermaid = resolver.to_mermaid()
    print("Mermaid with circular deps:")
    print(mermaid)
    print()
    assert 'Circular dependencies detected' in mermaid or 'Cycle' in mermaid, "Should note circular deps"

    # Check ASCII includes circular dependency warning
    ascii_diagram = resolver.to_ascii()
    print("ASCII with circular deps:")
    print(ascii_diagram)
    print()
    assert 'CIRCULAR DEPENDENCIES' in ascii_diagram, "Should have circular dependency section"

    print("[PASS]")


def test_empty_graph():
    """Test visualization with empty graph"""
    print("\n=== Test 6: Empty Graph ===")

    resolver = DependencyResolver()

    # Before calling resolve
    mermaid = resolver.to_mermaid()
    ascii_diagram = resolver.to_ascii()

    print("Mermaid (empty):", mermaid)
    print("ASCII (empty):", ascii_diagram)
    print()

    assert 'No dependency graph' in mermaid or 'Empty' in mermaid, "Should handle empty state"
    assert 'No dependency graph' in ascii_diagram, "Should handle empty state"

    print("[PASS]")


def run_all_tests():
    """Run all visualization tests"""
    print("\n" + "="*70)
    print("Running DependencyResolver Visualization Tests")
    print("="*70)

    try:
        test_mermaid_visualization()
        test_ascii_visualization()
        test_critical_path()
        test_filtering()
        test_circular_dependency_visualization()
        test_empty_graph()

        print("\n" + "="*70)
        print("[SUCCESS] ALL VISUALIZATION TESTS PASSED")
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
