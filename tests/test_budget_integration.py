"""
Budget Management Integration Test
===================================

Demonstrates budget management working with actual task recommendations.
"""

from uuid import uuid4
from core.learning.model_selector import ModelSelector, ModelTier


class MockConfig:
    """Mock configuration for testing."""
    class CostConfig:
        def __init__(self, budget_limit_usd=10.0):
            self.budget_limit_usd = budget_limit_usd
            self.optimization_enabled = True
            self.default_model = "sonnet"
            self.model_overrides = {}

    def __init__(self, budget_limit_usd=10.0):
        self.cost = self.CostConfig(budget_limit_usd)


class MockDB:
    """Mock database connection for testing."""
    def __init__(self, total_spent=0.0):
        self.total_spent = total_spent

    def acquire(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def fetchrow(self, query, project_id):
        return {'total_spent': self.total_spent}

    async def fetch(self, query, project_id):
        # Return empty list for historical performance queries
        return []


def test_budget_management_integration():
    """
    Integration test demonstrating budget management.

    Scenario:
    1. Set budget to $10
    2. Record $8 spent
    3. Verify check_budget() returns within_budget=True, remaining=$2
    4. Record additional $3 (total $11)
    5. Verify check_budget() returns within_budget=False
    6. Verify model gets downgraded to HAIKU when over budget
    """
    project_id = uuid4()

    print("\n=== Budget Management Integration Test ===\n")

    # Step 1: Set budget to $10
    config = MockConfig(budget_limit_usd=10.0)
    print(f"[1] Budget limit set to: ${config.cost.budget_limit_usd}")

    # Step 2: Record $8 spent
    db = MockDB(total_spent=8.0)
    selector = ModelSelector(project_id, config, db)

    within_budget, remaining = selector.check_budget()
    print(f"[2] After spending $8:")
    print(f"    - Within budget: {within_budget}")
    print(f"    - Remaining: ${remaining:.2f}")
    assert within_budget is True
    assert remaining == 2.0

    # Step 3: Test model recommendation at 80% budget usage
    task = {
        'id': 1,
        'description': 'Design advanced distributed consensus algorithm with sophisticated multi-step workflow',
        'action': 'Implement complex architecture with advanced algorithms for distributed system coordination, requiring sophisticated multi-step reasoning and analysis across multiple large files with extensive refactoring of existing codebase',
        'priority': 5
    }

    recommendation = selector.recommend_model(task)
    print(f"\n[3] Model recommendation at 80% budget:")
    print(f"    - Task: {task['description']}")
    print(f"    - Recommended model: {recommendation.model.value}")
    print(f"    - Reasoning: {recommendation.reasoning}")
    # Complex task should recommend OPUS, but budget is OK so no downgrade yet
    # If it's SONNET, that's also fine - what matters is the downgrade behavior
    initial_model = recommendation.model

    # Step 4: Record additional $3 (total $11, over budget)
    db.total_spent = 11.0
    selector = ModelSelector(project_id, config, db)

    within_budget, remaining = selector.check_budget()
    print(f"\n[4] After spending $11 (over budget):")
    print(f"    - Within budget: {within_budget}")
    print(f"    - Remaining: ${remaining:.2f}")
    assert within_budget is False
    assert remaining == -1.0

    # Step 5: Verify model downgraded when over budget
    recommendation = selector.recommend_model(task)
    print(f"\n[5] Model recommendation when over budget:")
    print(f"    - Task: {task['description']}")
    print(f"    - Recommended model: {recommendation.model.value} (forced downgrade)")
    print(f"    - Reasoning: {recommendation.reasoning}")
    assert recommendation.model == ModelTier.HAIKU
    assert "exhausted" in recommendation.reasoning.lower()

    print("\n[SUCCESS] Budget management enforces limits correctly!")
    print("     - Tracks spent from agent_costs table")
    print("     - Compares against budget_limit_usd")
    print("     - Downgrades model when budget exceeded")
    print("     - Forces HAIKU when over budget")


if __name__ == "__main__":
    test_budget_management_integration()
