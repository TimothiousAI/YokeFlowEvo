#!/usr/bin/env python3
"""
Integration test for ModelSelector historical performance tracking.

Tests the complete flow with proper async/await patterns.
"""

import sys
import asyncio
from dataclasses import dataclass
from typing import Any, List, Dict
from uuid import UUID
from contextlib import asynccontextmanager

# Mock config object
@dataclass
class MockConfig:
    """Mock configuration for testing."""
    pass

# Mock DB connection with async support
class MockDBConnection:
    """Mock database connection for testing."""

    def __init__(self, test_data: List[Dict[str, Any]]):
        self.test_data = test_data

    async def fetch(self, query: str, *args):
        """Mock fetch that returns test data."""
        return self.test_data

class MockDB:
    """Mock database connection pool for testing."""

    def __init__(self, test_data: List[Dict[str, Any]] = None):
        self.test_data = test_data or []

    @asynccontextmanager
    async def acquire(self):
        """Mock acquire context manager."""
        yield MockDBConnection(self.test_data)

# Import the ModelSelector
sys.path.insert(0, '.')
from core.learning.model_selector import ModelSelector, ModelTier

async def test_async_historical_performance():
    """Test historical performance tracking with proper async context."""
    print(f"\n=== ASYNC HISTORICAL PERFORMANCE TEST ===")

    # Mock historical data: HAIKU performs poorly on API tasks, SONNET performs well
    test_data = [
        {
            'description': 'Create API endpoint for users',
            'model': 'haiku',
            'total_count': 5,
            'success_count': 2,  # 40% success rate
            'avg_duration_seconds': 120.0
        },
        {
            'description': 'Implement API route',
            'model': 'haiku',
            'total_count': 3,
            'success_count': 1,  # 33% success rate
            'avg_duration_seconds': 100.0
        },
        {
            'description': 'Build API handler',
            'model': 'sonnet',
            'total_count': 5,
            'success_count': 5,  # 100% success rate
            'avg_duration_seconds': 90.0
        }
    ]

    config = MockConfig()
    db = MockDB(test_data)
    project_id = UUID('00000000-0000-0000-0000-000000000000')

    selector = ModelSelector(project_id, config, db)

    # Manually refresh cache in async context
    await selector._refresh_performance_cache()

    print(f"Cache populated: {len(selector._performance_cache)} task types")
    print(f"Cache contents: {selector._performance_cache}")

    # Now test historical performance query
    haiku_perf = await selector._get_historical_performance('api', 'haiku')
    sonnet_perf = await selector._get_historical_performance('api', 'sonnet')

    print(f"\nHAIKU performance on API tasks:")
    if haiku_perf:
        print(f"  Success rate: {haiku_perf['success_rate']:.1%}")
        print(f"  Avg duration: {haiku_perf['avg_duration']:.1f}s")
        print(f"  Sample count: {haiku_perf['count']}")
    else:
        print(f"  No data")

    print(f"\nSONNET performance on API tasks:")
    if sonnet_perf:
        print(f"  Success rate: {sonnet_perf['success_rate']:.1%}")
        print(f"  Avg duration: {sonnet_perf['avg_duration']:.1f}s")
        print(f"  Sample count: {sonnet_perf['count']}")
    else:
        print(f"  No data")

    # Verify cache works correctly
    if haiku_perf and sonnet_perf:
        assert haiku_perf['success_rate'] < 0.7, "HAIKU should have poor success rate"
        assert sonnet_perf['success_rate'] > 0.9, "SONNET should have high success rate"
        assert haiku_perf['count'] >= 3, "Should aggregate multiple HAIKU records"
        print(f"\n[PASS] Historical performance tracking works correctly")
        return True
    else:
        print(f"\n[FAIL] Cache not populated correctly")
        return False

async def test_cache_ttl():
    """Test that cache respects TTL."""
    print(f"\n=== CACHE TTL TEST ===")

    test_data = [
        {
            'description': 'Test task',
            'model': 'haiku',
            'total_count': 3,
            'success_count': 3,
            'avg_duration_seconds': 60.0
        }
    ]

    config = MockConfig()
    db = MockDB(test_data)
    project_id = UUID('00000000-0000-0000-0000-000000000000')

    selector = ModelSelector(project_id, config, db)

    # First refresh
    await selector._refresh_performance_cache()
    first_timestamp = selector._cache_timestamp

    print(f"Cache timestamp after first refresh: {first_timestamp}")
    assert first_timestamp is not None, "Cache should have timestamp"

    # Wait a tiny bit
    await asyncio.sleep(0.1)

    # Second call should use cached data (no refresh if within TTL)
    perf = await selector._get_historical_performance('general', 'haiku')
    second_timestamp = selector._cache_timestamp

    print(f"Cache timestamp after second query: {second_timestamp}")
    assert second_timestamp == first_timestamp, "Cache timestamp should not change within TTL"

    print(f"[PASS] Cache TTL works correctly (same timestamp = cache hit)")
    return True

async def test_task_type_aggregation():
    """Test that multiple tasks of same type are aggregated correctly."""
    print(f"\n=== TASK TYPE AGGREGATION TEST ===")

    # Multiple database tasks with different success rates
    test_data = [
        {
            'description': 'Create database schema',
            'model': 'haiku',
            'total_count': 2,
            'success_count': 2,
            'avg_duration_seconds': 50.0
        },
        {
            'description': 'Implement database migration',
            'model': 'haiku',
            'total_count': 4,
            'success_count': 2,
            'avg_duration_seconds': 100.0
        },
        {
            'description': 'Add database query optimization',
            'model': 'haiku',
            'total_count': 3,
            'success_count': 3,
            'avg_duration_seconds': 75.0
        }
    ]

    config = MockConfig()
    db = MockDB(test_data)
    project_id = UUID('00000000-0000-0000-0000-000000000000')

    selector = ModelSelector(project_id, config, db)
    await selector._refresh_performance_cache()

    # All three tasks should be aggregated under 'database' task type
    db_perf = await selector._get_historical_performance('database', 'haiku')

    print(f"Aggregated database task performance:")
    if db_perf:
        print(f"  Success rate: {db_perf['success_rate']:.1%}")
        print(f"  Avg duration: {db_perf['avg_duration']:.1f}s")
        print(f"  Total count: {db_perf['count']}")

        # Expected: (2+2+3)/(2+4+3) = 7/9 = 77.8%
        expected_success_rate = 7.0 / 9.0
        assert abs(db_perf['success_rate'] - expected_success_rate) < 0.01, f"Expected {expected_success_rate:.1%}, got {db_perf['success_rate']:.1%}"
        assert db_perf['count'] == 9, f"Expected 9 total samples, got {db_perf['count']}"

        print(f"\n[PASS] Task type aggregation works correctly")
        return True
    else:
        print(f"\n[FAIL] No aggregated data found")
        return False

async def main():
    """Run all integration tests."""
    print("Integration Testing ModelSelector Historical Performance Tracking")
    print("=" * 70)

    try:
        passed = []
        passed.append(await test_async_historical_performance())
        passed.append(await test_cache_ttl())
        passed.append(await test_task_type_aggregation())

        print("\n" + "=" * 70)
        if all(passed):
            print("[SUCCESS] ALL INTEGRATION TESTS PASSED")
        else:
            print(f"[PARTIAL] {sum(passed)}/{len(passed)} tests passed")
        print("=" * 70)
    except Exception as e:
        print(f"\n[FAILED] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
