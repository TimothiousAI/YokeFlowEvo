"""
Test concurrent execution respects max_concurrency limit.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.parallel_executor import ParallelExecutor, ExecutionResult


class ConcurrencyTracker:
    """Track concurrent execution count."""

    def __init__(self):
        self.max_concurrent = 0
        self.current_concurrent = 0
        self.lock = asyncio.Lock()

    async def task_started(self):
        async with self.lock:
            self.current_concurrent += 1
            if self.current_concurrent > self.max_concurrent:
                self.max_concurrent = self.current_concurrent

    async def task_finished(self):
        async with self.lock:
            self.current_concurrent -= 1


class MockDatabase:
    """Mock database for testing."""

    def __init__(self):
        self.batches = []

    async def get_task_with_tests(self, task_id, project_id):
        """Return mock task."""
        return {
            'id': task_id,
            'epic_id': 1,
            'epic_name': 'Test Epic',
            'description': f'Task {task_id}',
            'done': False,
            'tests': []
        }

    async def list_parallel_batches(self, project_id):
        """Return batches."""
        return self.batches

    async def update_batch_status(self, batch_id, status, started_at=None, completed_at=None):
        """Update batch status."""
        for batch in self.batches:
            if batch['id'] == batch_id:
                batch['status'] = status
                if started_at:
                    batch['started_at'] = started_at
                if completed_at:
                    batch['completed_at'] = completed_at


async def test_concurrent_execution_respects_limit():
    """Test that concurrent execution never exceeds max_concurrency."""

    # Create tracker
    tracker = ConcurrencyTracker()

    # Create mock database
    mock_db = MockDatabase()
    project_id = uuid4()

    # Create executor with max_concurrency=2
    executor = ParallelExecutor(
        project_path="/tmp/test-project",
        project_id=project_id,
        max_concurrency=2,
        db_connection=mock_db
    )

    # Mock worktree manager create_worktree
    mock_worktree_info = Mock()
    mock_worktree_info.path = "/tmp/test-worktree"
    executor.worktree_manager.create_worktree = AsyncMock(return_value=mock_worktree_info)

    # Create batch record
    mock_db.batches.append({
        'id': 1,
        'batch_number': 1,
        'task_ids': [1, 2, 3, 4, 5],
        'status': 'pending'
    })

    # Mock run_task_agent to simulate work and track concurrency
    async def mock_run_task_agent(task, worktree_path):
        """Mock agent that tracks concurrency and simulates work."""
        await tracker.task_started()
        try:
            # Simulate some work
            await asyncio.sleep(0.1)
            return ExecutionResult(
                task_id=task['id'],
                success=True,
                duration=0.1,
                cost=0.01
            )
        finally:
            await tracker.task_finished()

    executor.run_task_agent = mock_run_task_agent

    # Execute batch with 5 tasks
    task_ids = [1, 2, 3, 4, 5]
    results = await executor.execute_batch(1, task_ids)

    # Verify results
    assert len(results) == 5, f"Expected 5 results, got {len(results)}"
    assert all(r.success for r in results), "All tasks should succeed"

    # Verify max_concurrency was respected
    assert tracker.max_concurrent <= 2, \
        f"Max concurrent tasks should be <= 2, but was {tracker.max_concurrent}"

    # Verify we actually ran tasks concurrently (should have been 2 at some point)
    assert tracker.max_concurrent >= 2, \
        f"Expected concurrent execution (max=2), but max was {tracker.max_concurrent}"

    # Verify all tasks completed
    assert tracker.current_concurrent == 0, \
        f"All tasks should be complete, but {tracker.current_concurrent} still running"

    print(f"Test passed! Max concurrent: {tracker.max_concurrent} (limit: 2)")


if __name__ == "__main__":
    asyncio.run(test_concurrent_execution_respects_limit())
