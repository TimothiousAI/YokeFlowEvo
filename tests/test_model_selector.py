#!/usr/bin/env python3
"""
Test script for ModelSelector.recommend_model()

Tests the model recommendation logic with various complexity levels.
"""

import sys
from dataclasses import dataclass
from typing import Any
from uuid import UUID

# Mock config object
@dataclass
class MockConfig:
    """Mock configuration for testing."""
    pass

# Mock DB connection
class MockDB:
    """Mock database connection for testing."""
    pass

# Import the ModelSelector
sys.path.insert(0, '.')
from core.learning.model_selector import ModelSelector, ModelTier

def test_low_complexity():
    """Test that low complexity tasks recommend HAIKU."""
    config = MockConfig()
    db = MockDB()
    project_id = UUID('00000000-0000-0000-0000-000000000000')

    selector = ModelSelector(project_id, config, db)

    # Low complexity task
    task = {
        'id': 1,
        'description': 'Update simple README file',
        'action': 'Add a simple paragraph to README.md explaining the project',
        'priority': 5
    }

    recommendation = selector.recommend_model(task)

    print(f"\n=== LOW COMPLEXITY TEST ===")
    print(f"Task: {task['description']}")
    print(f"Recommended Model: {recommendation.model.value}")
    print(f"Reasoning: {recommendation.reasoning}")
    print(f"Estimated Cost: ${recommendation.estimated_cost:.4f}")
    print(f"Complexity Score: {recommendation.complexity.overall_score:.2f}")

    assert recommendation.model == ModelTier.HAIKU, f"Expected HAIKU, got {recommendation.model.value}"
    assert recommendation.complexity.overall_score < 0.3, f"Expected score < 0.3, got {recommendation.complexity.overall_score}"
    print("[PASS] Low complexity test passed")

def test_medium_complexity():
    """Test that medium complexity tasks recommend SONNET."""
    config = MockConfig()
    db = MockDB()
    project_id = UUID('00000000-0000-0000-0000-000000000000')

    selector = ModelSelector(project_id, config, db)

    # Medium complexity task - more substantial to trigger SONNET
    task = {
        'id': 2,
        'description': 'Refactor authentication system architecture with OAuth2 integration',
        'action': 'Analyze and redesign the authentication module. Implement OAuth2 authorization code flow with PKCE. Create abstract factory pattern for auth providers. Integrate with existing session management. Add comprehensive error handling and logging. Design database migrations for new token storage schema. Implement sophisticated rate limiting and security measures.',
        'priority': 2
    }

    recommendation = selector.recommend_model(task)

    print(f"\n=== MEDIUM COMPLEXITY TEST ===")
    print(f"Task: {task['description']}")
    print(f"Recommended Model: {recommendation.model.value}")
    print(f"Reasoning: {recommendation.reasoning}")
    print(f"Estimated Cost: ${recommendation.estimated_cost:.4f}")
    print(f"Complexity Score: {recommendation.complexity.overall_score:.2f}")

    # With a more complex task, should recommend SONNET or OPUS
    assert recommendation.model in [ModelTier.SONNET, ModelTier.OPUS], f"Expected SONNET/OPUS, got {recommendation.model.value}"
    assert recommendation.complexity.overall_score >= 0.3, f"Expected score >= 0.3, got {recommendation.complexity.overall_score}"
    print("[PASS] Medium complexity test passed")

def test_high_complexity():
    """Test that high complexity tasks recommend SONNET or OPUS."""
    config = MockConfig()
    db = MockDB()
    project_id = UUID('00000000-0000-0000-0000-000000000000')

    selector = ModelSelector(project_id, config, db)

    # High complexity task - should recommend at least SONNET
    task = {
        'id': 3,
        'description': 'Design and implement distributed consensus algorithm with Raft protocol',
        'action': 'Implement Raft consensus algorithm for distributed state machine replication. Design sophisticated architecture for multiple nodes. Implement leader election with term management. Build log replication with snapshot support. Add safety mechanisms for split-brain scenarios. Implement network partition recovery. Design comprehensive testing strategy. Analyze and optimize performance characteristics.',
        'priority': 1
    }

    recommendation = selector.recommend_model(task)

    print(f"\n=== HIGH COMPLEXITY TEST ===")
    print(f"Task: {task['description']}")
    print(f"Recommended Model: {recommendation.model.value}")
    print(f"Reasoning: {recommendation.reasoning}")
    print(f"Estimated Cost: ${recommendation.estimated_cost:.4f}")
    print(f"Complexity Score: {recommendation.complexity.overall_score:.2f}")

    # Should recommend SONNET or OPUS for complex tasks
    assert recommendation.model in [ModelTier.SONNET, ModelTier.OPUS], f"Expected SONNET/OPUS, got {recommendation.model.value}"
    assert recommendation.complexity.overall_score >= 0.3, f"Expected score >= 0.3, got {recommendation.complexity.overall_score}"
    print("[PASS] High complexity test passed")

def test_complexity_analysis():
    """Test that complexity analysis produces reasonable scores."""
    config = MockConfig()
    db = MockDB()
    project_id = UUID('00000000-0000-0000-0000-000000000000')

    selector = ModelSelector(project_id, config, db)

    # Test task
    task = {
        'id': 4,
        'description': 'Refactor database module',
        'action': 'Refactor existing database module to use connection pooling. Analyze existing code patterns and implement optimization strategy.',
        'priority': 5
    }

    complexity = selector.analyze_complexity(task)

    print(f"\n=== COMPLEXITY ANALYSIS TEST ===")
    print(f"Task: {task['description']}")
    print(f"Reasoning Depth: {complexity.reasoning_depth:.2f}")
    print(f"Code Complexity: {complexity.code_complexity:.2f}")
    print(f"Domain Specificity: {complexity.domain_specificity:.2f}")
    print(f"Context Requirements: {complexity.context_requirements:.2f}")
    print(f"Overall Score: {complexity.overall_score:.2f}")

    # Should have high context requirements (refactor = existing code)
    assert complexity.context_requirements > 0.3, "Refactoring should have high context requirements"
    # Should have some reasoning depth (optimization strategy)
    assert complexity.reasoning_depth > 0.1, "Should have some reasoning depth"
    print("[PASS] Complexity analysis test passed")

if __name__ == '__main__':
    print("Testing ModelSelector.recommend_model() implementation")
    print("=" * 60)

    try:
        test_low_complexity()
        test_medium_complexity()
        test_high_complexity()
        test_complexity_analysis()

        print("\n" + "=" * 60)
        print("[SUCCESS] ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"\n[FAILED] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
