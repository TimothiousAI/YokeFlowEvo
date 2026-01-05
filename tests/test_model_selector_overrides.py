"""
Unit tests for ModelSelector configuration overrides.

Tests task metadata, priority, and task type overrides.
"""

import sys
sys.path.insert(0, '.')

from core.learning.model_selector import ModelSelector, ModelTier
from unittest.mock import Mock, AsyncMock
from uuid import uuid4


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self):
        self.cost = Mock()
        self.cost.budget_limit_usd = None
        self.cost.model_overrides = {}
        self.cost.priority_overrides = {}


def test_task_metadata_override():
    """Test that task metadata overrides take precedence."""
    # Setup
    project_id = uuid4()
    config = MockConfig()
    db = Mock()

    selector = ModelSelector(project_id, config, db)

    # Task with low complexity but metadata override to OPUS
    task = {
        'id': 1,
        'description': 'Simple task',
        'action': 'Do something simple',
        'priority': 5,
        'metadata': {'force_model': 'opus'}
    }

    # Test
    recommendation = selector.recommend_model(task)

    # Verify
    assert recommendation.model == ModelTier.OPUS, f"Expected OPUS, got {recommendation.model}"
    assert "metadata" in recommendation.reasoning.lower(), "Reasoning should mention metadata"
    print("[OK] Task metadata override test passed")


def test_priority_override():
    """Test that priority overrides work."""
    # Setup
    project_id = uuid4()
    config = MockConfig()
    config.cost.priority_overrides = {
        1: 'opus',  # P1 tasks use OPUS
        2: 'sonnet',  # P2 tasks use SONNET
    }
    db = Mock()

    selector = ModelSelector(project_id, config, db)

    # Task with P1 priority (should use OPUS)
    task = {
        'id': 2,
        'description': 'Simple task',
        'action': 'Do something simple',
        'priority': 1,
        'metadata': {}
    }

    # Test
    recommendation = selector.recommend_model(task)

    # Verify
    assert recommendation.model == ModelTier.OPUS, f"Expected OPUS for P1, got {recommendation.model}"
    assert "priority" in recommendation.reasoning.lower(), "Reasoning should mention priority"
    print("[OK] Priority override test passed")


def test_task_type_override():
    """Test that task type overrides work."""
    # Setup
    project_id = uuid4()
    config = MockConfig()
    config.cost.model_overrides = {
        'testing': 'haiku',  # Testing tasks use HAIKU
        'database': 'opus',  # Database tasks use OPUS
    }
    db = Mock()

    selector = ModelSelector(project_id, config, db)

    # Task with 'testing' in description (should use HAIKU)
    task = {
        'id': 3,
        'description': 'Create testing framework',
        'action': 'Implement comprehensive testing suite',
        'priority': 5,
        'metadata': {}
    }

    # Test
    recommendation = selector.recommend_model(task)

    # Verify
    assert recommendation.model == ModelTier.HAIKU, f"Expected HAIKU for testing, got {recommendation.model}"
    assert "task type" in recommendation.reasoning.lower(), "Reasoning should mention task type"
    print("[OK] Task type override test passed")


def test_override_priority_order():
    """Test that override priority order is correct (metadata > priority > task type)."""
    # Setup
    project_id = uuid4()
    config = MockConfig()
    config.cost.priority_overrides = {1: 'sonnet'}
    config.cost.model_overrides = {'testing': 'haiku'}
    db = Mock()

    selector = ModelSelector(project_id, config, db)

    # Task with all three override types (metadata should win)
    task = {
        'id': 4,
        'description': 'Create testing framework',
        'action': 'Testing implementation',
        'priority': 1,
        'metadata': {'force_model': 'opus'}
    }

    # Test
    recommendation = selector.recommend_model(task)

    # Verify metadata override wins
    assert recommendation.model == ModelTier.OPUS, f"Expected OPUS (metadata override), got {recommendation.model}"
    assert "metadata" in recommendation.reasoning.lower(), "Reasoning should mention metadata"
    print("[OK] Override priority order test passed (metadata wins)")


def test_no_override():
    """Test that complexity-based selection works when no overrides present."""
    # Setup
    project_id = uuid4()
    config = MockConfig()
    db = Mock()

    selector = ModelSelector(project_id, config, db)

    # High complexity task with no overrides
    task = {
        'id': 5,
        'description': 'Design complex distributed system architecture',
        'action': 'Implement sophisticated multi-step algorithm with advanced optimization',
        'priority': 5,
        'metadata': {}
    }

    # Test
    recommendation = selector.recommend_model(task)

    # Verify complexity-based selection (should be OPUS or SONNET based on complexity)
    assert recommendation.model in [ModelTier.SONNET, ModelTier.OPUS], \
        f"Expected SONNET or OPUS for complex task, got {recommendation.model}"
    assert recommendation.complexity is not None, "Complexity should be calculated"
    print(f"[OK] No override test passed - selected {recommendation.model.value} based on complexity")


def test_json_string_metadata():
    """Test that metadata can be provided as JSON string."""
    # Setup
    project_id = uuid4()
    config = MockConfig()
    db = Mock()

    selector = ModelSelector(project_id, config, db)

    # Task with metadata as JSON string (common from database)
    task = {
        'id': 6,
        'description': 'Simple task',
        'action': 'Do something',
        'priority': 5,
        'metadata': '{"force_model": "haiku"}'  # JSON string
    }

    # Test
    recommendation = selector.recommend_model(task)

    # Verify
    assert recommendation.model == ModelTier.HAIKU, f"Expected HAIKU from JSON metadata, got {recommendation.model}"
    print("[OK] JSON string metadata test passed")


if __name__ == '__main__':
    print("Testing ModelSelector configuration overrides...\n")

    try:
        test_task_metadata_override()
        test_priority_override()
        test_task_type_override()
        test_override_priority_order()
        test_no_override()
        test_json_string_metadata()

        print("\n" + "="*60)
        print("All tests PASSED!")
        print("="*60)

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
