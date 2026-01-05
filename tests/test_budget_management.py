"""
Test Budget Management
======================

Unit tests for ModelSelector budget management functionality.
"""

import asyncio
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from core.learning.model_selector import ModelSelector, ModelTier


class MockConfig:
    """Mock configuration for testing."""
    class CostConfig:
        def __init__(self, budget_limit_usd=None):
            self.budget_limit_usd = budget_limit_usd
            self.optimization_enabled = True
            self.default_model = "sonnet"
            self.model_overrides = {}

    def __init__(self, budget_limit_usd=None):
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


def test_check_budget_unlimited():
    """Test budget check with no limit set."""
    project_id = uuid4()
    config = MockConfig(budget_limit_usd=None)
    db = MockDB(total_spent=0.0)

    selector = ModelSelector(project_id, config, db)
    within_budget, remaining = selector.check_budget()

    assert within_budget is True
    assert remaining == 999999.0
    print("[OK] Unlimited budget test passed")


def test_check_budget_within_limit():
    """Test budget check when within limit."""
    project_id = uuid4()
    config = MockConfig(budget_limit_usd=100.0)
    db = MockDB(total_spent=50.0)

    selector = ModelSelector(project_id, config, db)
    within_budget, remaining = selector.check_budget()

    assert within_budget is True
    assert remaining == 50.0
    print("[OK] Within budget test passed")


def test_check_budget_exceeded():
    """Test budget check when exceeded."""
    project_id = uuid4()
    config = MockConfig(budget_limit_usd=100.0)
    db = MockDB(total_spent=105.0)

    selector = ModelSelector(project_id, config, db)
    within_budget, remaining = selector.check_budget()

    assert within_budget is False
    assert remaining == -5.0
    print("[OK] Budget exceeded test passed")


def test_downgrade_for_budget_exhausted():
    """Test model downgrade when budget exhausted."""
    project_id = uuid4()
    config = MockConfig(budget_limit_usd=100.0)
    db = MockDB(total_spent=0.0)

    selector = ModelSelector(project_id, config, db)

    # Test downgrade from OPUS to HAIKU when budget exhausted
    downgraded, reason = selector._downgrade_for_budget(
        ModelTier.OPUS, remaining_budget=0.5, within_budget=False
    )
    assert downgraded == ModelTier.HAIKU
    assert "exhausted" in reason
    print("[OK] Budget exhausted downgrade test passed")


def test_downgrade_for_budget_low():
    """Test model downgrade when budget is low."""
    project_id = uuid4()
    config = MockConfig(budget_limit_usd=100.0)
    db = MockDB(total_spent=0.0)

    selector = ModelSelector(project_id, config, db)

    # Test downgrade from OPUS to SONNET when budget low
    downgraded, reason = selector._downgrade_for_budget(
        ModelTier.OPUS, remaining_budget=5.0, within_budget=True
    )
    assert downgraded == ModelTier.SONNET
    assert "low budget" in reason
    print("[OK] Low budget downgrade test passed")


def test_no_downgrade_sufficient_budget():
    """Test no downgrade when budget is sufficient."""
    project_id = uuid4()
    config = MockConfig(budget_limit_usd=100.0)
    db = MockDB(total_spent=0.0)

    selector = ModelSelector(project_id, config, db)

    # Test no downgrade when budget is sufficient
    downgraded, reason = selector._downgrade_for_budget(
        ModelTier.OPUS, remaining_budget=50.0, within_budget=True
    )
    assert downgraded == ModelTier.OPUS
    assert reason == ""
    print("[OK] No downgrade test passed")


if __name__ == "__main__":
    print("Running budget management tests...\n")

    test_check_budget_unlimited()
    test_check_budget_within_limit()
    test_check_budget_exceeded()
    test_downgrade_for_budget_exhausted()
    test_downgrade_for_budget_low()
    test_no_downgrade_sufficient_budget()

    print("\n[OK] All budget management tests passed!")
