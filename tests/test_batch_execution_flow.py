"""
Test batch execution flow.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.parallel_executor import ParallelExecutor, ExecutionResult


class MockDatabase:
    """Mock database for testing."""

    def __init__(self):
        self.batches = []
        self.batch_statuses = {}

    async def get_tasks_with_dependencies(self, project_id):
        """Return mock tasks with dependencies forming 3 batches."""
        return [
            # Batch 1: No dependencies
            {'id': 1, 'epic_id': 1, 'description': 'Task 1', 'depends_on': [], 'dependency_type': 'hard', 'priority': 1, 'done': False, 'epic_name': 'Epic 1'},
            {'id': 2, 'epic_id': 1, 'description': 'Task 2', 'depends_on': [], 'dependency_type': 'hard', 'priority': 2, 'done': False, 'epic_name': 'Epic 1'},

            # Batch 2: Depends on batch 1
            {'id': 3, 'epic_id': 2, 'description': 'Task 3', 'depends_on': [1], 'dependency_type': 'hard', 'priority': 1, 'done': False, 'epic_name': 'Epic 2'},

            # Batch 3: Depends on batch 2
            {'id': 4, 'epic_id': 2, 'description': 'Task 4', 'depends_on': [3], 'dependency_type': 'hard', 'priority': 2, 'done': False, 'epic_name': 'Epic 2'},
        ]

    async def create_parallel_batch(self, project_id, batch_number, task_ids):
        """Record batch creation."""
        batch = {
            'id': len(self.batches) + 1,
            'project_id': project_id,
            'batch_number': batch_number,
            'task_ids': task_ids,
            'status': 'pending'
        }
        self.batches.append(batch)
        return batch


async def test_batch_execution_flow():
    """Test that batch execution processes batches sequentially."""

    # Create mock database
    mock_db = MockDatabase()
    project_id = uuid4()

    # Create executor
    executor = ParallelExecutor(
        project_path="/tmp/test-project",
        project_id=project_id,
        max_concurrency=3,
        db_connection=mock_db
    )

    # Mock the execute_batch method to return success results
    async def mock_execute_batch(batch_number, task_ids):
        """Mock batch execution that returns success for all tasks."""
        return [
            ExecutionResult(
                task_id=task_id,
                success=True,
                duration=1.0,
                cost=0.01
            )
            for task_id in task_ids
        ]

    executor.execute_batch = mock_execute_batch

    # Mock worktree manager initialization
    executor.worktree_manager.initialize = AsyncMock()

    # Execute
    results = await executor.execute()

    # Verify results
    assert len(results) == 4, f"Expected 4 results, got {len(results)}"
    assert all(r.success for r in results), "All tasks should succeed"

    # Verify batch records created in database
    assert len(mock_db.batches) == 3, f"Expected 3 batches created, got {len(mock_db.batches)}"

    # Verify batch 1 contains tasks 1 and 2
    batch1 = mock_db.batches[0]
    assert batch1['batch_number'] == 1
    assert set(batch1['task_ids']) == {1, 2}, f"Batch 1 should contain tasks 1,2 but got {batch1['task_ids']}"

    # Verify batch 2 contains task 3
    batch2 = mock_db.batches[1]
    assert batch2['batch_number'] == 2
    assert set(batch2['task_ids']) == {3}, f"Batch 2 should contain task 3 but got {batch2['task_ids']}"

    # Verify batch 3 contains task 4
    batch3 = mock_db.batches[2]
    assert batch3['batch_number'] == 3
    assert set(batch3['task_ids']) == {4}, f"Batch 3 should contain task 4 but got {batch3['task_ids']}"

    # Verify worktree manager was initialized
    executor.worktree_manager.initialize.assert_called_once()

    print("All batch execution flow tests passed!")


if __name__ == "__main__":
    asyncio.run(test_batch_execution_flow())
