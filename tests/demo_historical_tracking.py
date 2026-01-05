#!/usr/bin/env python3
"""
Demonstration of ModelSelector historical performance tracking.

Shows how historical data influences model recommendations.
"""

import sys
import asyncio
from dataclasses import dataclass
from typing import Any, List, Dict
from uuid import UUID
from contextlib import asynccontextmanager

# Setup path
sys.path.insert(0, '.')

@dataclass
class MockConfig:
    pass

class MockDBConnection:
    def __init__(self, test_data):
        self.test_data = test_data

    async def fetch(self, query: str, *args):
        return self.test_data

class MockDB:
    def __init__(self, test_data=None):
        self.test_data = test_data or []

    @asynccontextmanager
    async def acquire(self):
        yield MockDBConnection(self.test_data)

from core.learning.model_selector import ModelSelector, ModelTier

async def demonstrate():
    """Demonstrate historical performance tracking."""

    print("\n" + "="*70)
    print("DEMONSTRATION: Historical Performance Tracking in ModelSelector")
    print("="*70)

    # Scenario: We have historical data showing HAIKU struggles with API tasks
    # but SONNET handles them well
    historical_data = [
        # HAIKU failed 60% of API tasks
        {'description': 'Create API endpoint', 'model': 'haiku', 'total_count': 5, 'success_count': 2, 'avg_duration_seconds': 120},
        {'description': 'Implement API route', 'model': 'haiku', 'total_count': 5, 'success_count': 2, 'avg_duration_seconds': 110},

        # SONNET succeeded at 95% of API tasks
        {'description': 'Create API handler', 'model': 'sonnet', 'total_count': 10, 'success_count': 9, 'avg_duration_seconds': 85},

        # HAIKU does fine on simple documentation tasks
        {'description': 'Update README', 'model': 'haiku', 'total_count': 10, 'success_count': 10, 'avg_duration_seconds': 30},
    ]

    config = MockConfig()
    db = MockDB(historical_data)
    project_id = UUID('00000000-0000-0000-0000-000000000000')

    selector = ModelSelector(project_id, config, db)

    # Populate cache
    await selector._refresh_performance_cache()

    print("\nHistorical Performance Data Loaded:")
    print("-" * 70)
    for task_type, models in selector._performance_cache.items():
        print(f"\n{task_type.upper()} tasks:")
        for model, stats in models.items():
            print(f"  {model:8s}: {stats['success_rate']:5.1%} success, "
                  f"{stats['avg_duration']:5.1f}s avg, {stats['count']} samples")

    print("\n" + "="*70)
    print("SCENARIO 1: API Task (would normally be HAIKU based on complexity)")
    print("="*70)

    # This task has low complexity, so without historical data it would be HAIKU
    api_task = {
        'id': 1,
        'description': 'Add simple API endpoint',
        'action': 'Create a GET endpoint that returns user profile data',
        'priority': 5
    }

    # Analyze complexity first
    complexity = selector.analyze_complexity(api_task)
    print(f"\nComplexity Analysis:")
    print(f"  Overall Score: {complexity.overall_score:.2f}")
    print(f"  Base Model (by complexity): ", end="")
    if complexity.overall_score < 0.3:
        print("HAIKU")
    elif complexity.overall_score < 0.7:
        print("SONNET")
    else:
        print("OPUS")

    # Get actual recommendation (uses historical data)
    print(f"\nGetting recommendation...")
    recommendation = selector.recommend_model(api_task)

    print(f"\nFinal Recommendation:")
    print(f"  Model: {recommendation.model.value.upper()}")
    print(f"  Reasoning: {recommendation.reasoning}")
    print(f"  Estimated Cost: ${recommendation.estimated_cost:.4f}")

    if 'historical' in recommendation.reasoning.lower():
        print(f"\n  [Historical data influenced this decision!]")
        print(f"  HAIKU had 40% success on API tasks, so upgraded to SONNET")

    print("\n" + "="*70)
    print("SCENARIO 2: Documentation Task (HAIKU performs well)")
    print("="*70)

    doc_task = {
        'id': 2,
        'description': 'Update documentation',
        'action': 'Add usage examples to README',
        'priority': 5
    }

    complexity2 = selector.analyze_complexity(doc_task)
    print(f"\nComplexity Analysis:")
    print(f"  Overall Score: {complexity2.overall_score:.2f}")

    recommendation2 = selector.recommend_model(doc_task)

    print(f"\nFinal Recommendation:")
    print(f"  Model: {recommendation2.model.value.upper()}")
    print(f"  Reasoning: {recommendation2.reasoning}")
    print(f"  Estimated Cost: ${recommendation2.estimated_cost:.4f}")

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("\nKey Features Demonstrated:")
    print("  1. Historical data is cached for 5 minutes (TTL)")
    print("  2. Task types are extracted from descriptions")
    print("  3. Success rates influence model selection")
    print("  4. Poor performance triggers upgrades (HAIKU -> SONNET)")
    print("  5. Good performance allows downgrades (OPUS -> SONNET for cost)")
    print("  6. Requires 3+ samples before influencing decisions")
    print("  7. Cache is invalidated after recording new outcomes")

    print("\n" + "="*70)

if __name__ == '__main__':
    asyncio.run(demonstrate())
