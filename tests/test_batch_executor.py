"""
Tests for BatchExecutor and parallel execution functionality.

Tests cover:
- Plan execution with all sequential batches
- Plan execution with parallel batches
- Batch failure stops execution
- Progress callbacks
- Stop request handling
"""

import sys
import asyncio
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.batch_executor import BatchExecutor, BatchResult, PlanExecutionResult
from core.parallel.parallel_executor import ExecutionResult
from core.execution_plan import ExecutionPlan, ExecutionBatch


class MockDatabase:
    """Mock database for testing batch execution."""

    def __init__(self):
        self.project_metadata = {}
        self.execution_plan = None
        self.project = {
            'id': uuid4(),
            'name': 'Test Project',
            'local_path': '/tmp/test-project',
            'metadata': {}
        }

    async def get_project(self, project_id):
        return self.project

    async def get_execution_plan(self, project_id):
        return self.execution_plan

    async def update_project_metadata(self, project_id, updates):
        self.project_metadata.update(updates)

    async def update_batch_status(self, batch_id, status, **kwargs):
        pass

    async def get_batch_worktrees(self, batch_id):
        return []

    async def get_task(self, task_id, project_id):
        return {'id': task_id, 'epic_id': 1}


class MockParallelExecutor:
    """Mock parallel executor for testing."""

    def __init__(self, success=True, delay=0.01):
        self.success = success
        self.delay = delay
        self.executed_batches = []
        self.executed_tasks = []

    async def execute_batch(self, batch_id, task_ids):
        self.executed_batches.append(batch_id)
        self.executed_tasks.extend(task_ids)
        await asyncio.sleep(self.delay)
        return [
            ExecutionResult(
                task_id=tid,
                success=self.success,
                duration=0.1,
                error=None if self.success else "Mock error",
                cost=0.01
            )
            for tid in task_ids
        ]


class MockWorktreeManager:
    """Mock worktree manager for testing."""

    async def initialize(self):
        pass

    async def create_worktree(self, epic_id):
        return Mock(path=f"/tmp/worktree-{epic_id}")


def create_test_plan(batches_config):
    """
    Create a test execution plan.

    Args:
        batches_config: List of (task_ids, can_parallel) tuples
    """
    batches = [
        ExecutionBatch(
            batch_id=i,
            task_ids=task_ids,
            can_parallel=can_parallel,
            depends_on=[i-1] if i > 0 else []
        )
        for i, (task_ids, can_parallel) in enumerate(batches_config)
    ]

    return ExecutionPlan(
        project_id=uuid4(),
        created_at=datetime.utcnow(),
        batches=batches,
        worktree_assignments={},
        predicted_conflicts=[],
        metadata={}
    )


async def test_execute_plan_all_sequential():
    """All sequential batches execute correctly."""
    print("\n=== Test: All Sequential Batches ===")

    mock_db = MockDatabase()
    project_id = uuid4()

    # Create plan with 3 sequential batches
    plan = create_test_plan([
        ([1], False),
        ([2], False),
        ([3], False),
    ])

    # Create executor with mocked parallel executor
    executor = BatchExecutor(
        project_id=project_id,
        project_path="/tmp/test",
        db=mock_db,
        max_concurrency=3
    )

    # Replace with mock
    mock_parallel = MockParallelExecutor(success=True)
    executor.parallel_executor = mock_parallel
    executor.worktree_manager = MockWorktreeManager()

    # Execute plan
    result = await executor.execute_plan(plan)

    assert result.success, "Plan should succeed"
    assert result.batches_completed == 3, f"Expected 3 batches, got {result.batches_completed}"
    assert len(mock_parallel.executed_tasks) == 3, "Should execute 3 tasks"

    print(f"[PASS] Executed {result.batches_completed} sequential batches")


async def test_execute_plan_with_parallel():
    """Parallel batches execute concurrently."""
    print("\n=== Test: Parallel Batch Execution ===")

    mock_db = MockDatabase()
    project_id = uuid4()

    # Create plan with 1 sequential, 1 parallel, 1 sequential
    plan = create_test_plan([
        ([1], False),        # Sequential
        ([2, 3, 4], True),   # Parallel
        ([5], False),        # Sequential
    ])

    executor = BatchExecutor(
        project_id=project_id,
        project_path="/tmp/test",
        db=mock_db,
        max_concurrency=3
    )

    mock_parallel = MockParallelExecutor(success=True)
    executor.parallel_executor = mock_parallel
    executor.worktree_manager = MockWorktreeManager()

    result = await executor.execute_plan(plan)

    assert result.success, "Plan should succeed"
    assert result.batches_completed == 3, f"Expected 3 batches, got {result.batches_completed}"
    assert 2 in mock_parallel.executed_tasks, "Task 2 should be executed"
    assert 3 in mock_parallel.executed_tasks, "Task 3 should be executed"
    assert 4 in mock_parallel.executed_tasks, "Task 4 should be executed"

    print(f"[PASS] Executed plan with parallel batch")


async def test_batch_failure_stops_execution():
    """Failed batch stops further execution."""
    print("\n=== Test: Batch Failure Stops Execution ===")

    mock_db = MockDatabase()
    project_id = uuid4()

    plan = create_test_plan([
        ([1], False),
        ([2], False),  # Will fail
        ([3], False),  # Should not execute
    ])

    executor = BatchExecutor(
        project_id=project_id,
        project_path="/tmp/test",
        db=mock_db,
        max_concurrency=3
    )

    # First batch succeeds, second fails
    call_count = 0
    async def mock_execute_batch(batch_id, task_ids):
        nonlocal call_count
        call_count += 1
        if batch_id == 1:
            return [ExecutionResult(
                task_id=task_ids[0],
                success=False,
                duration=0.1,
                error="Task failed"
            )]
        return [ExecutionResult(
            task_id=task_ids[0],
            success=True,
            duration=0.1
        )]

    mock_parallel = Mock()
    mock_parallel.execute_batch = mock_execute_batch
    executor.parallel_executor = mock_parallel
    executor.worktree_manager = MockWorktreeManager()

    result = await executor.execute_plan(plan)

    assert not result.success, "Plan should fail"
    assert result.batches_completed == 1, "Only first batch should succeed"
    assert result.stopped_early, "Should be marked as stopped early"

    print(f"[PASS] Execution stopped after batch failure")


async def test_progress_callbacks():
    """Progress callbacks fire for batch events."""
    print("\n=== Test: Progress Callbacks ===")

    mock_db = MockDatabase()
    project_id = uuid4()

    plan = create_test_plan([
        ([1, 2], True),
    ])

    progress_events = []

    async def progress_callback(event):
        progress_events.append(event)

    executor = BatchExecutor(
        project_id=project_id,
        project_path="/tmp/test",
        db=mock_db,
        max_concurrency=3,
        progress_callback=progress_callback
    )

    mock_parallel = MockParallelExecutor(success=True)
    executor.parallel_executor = mock_parallel
    executor.worktree_manager = MockWorktreeManager()

    await executor.execute_plan(plan)

    # Should have batch_started and batch_completed events
    event_types = [e['type'] for e in progress_events]
    assert 'batch_started' in event_types, "Should have batch_started event"
    assert 'batch_completed' in event_types, "Should have batch_completed event"

    print(f"[PASS] Received {len(progress_events)} progress events")


async def test_stop_request():
    """Stop request halts execution."""
    print("\n=== Test: Stop Request ===")

    mock_db = MockDatabase()
    mock_db.project_metadata['parallel_stop_requested'] = True

    project_id = uuid4()

    plan = create_test_plan([
        ([1], False),
        ([2], False),
        ([3], False),
    ])

    executor = BatchExecutor(
        project_id=project_id,
        project_path="/tmp/test",
        db=mock_db,
        max_concurrency=3
    )

    mock_parallel = MockParallelExecutor(success=True)
    executor.parallel_executor = mock_parallel
    executor.worktree_manager = MockWorktreeManager()

    # Mock the stop check to return True after first batch
    batch_count = 0
    original_check = executor._check_stop_requested

    async def mock_check_stop():
        nonlocal batch_count
        batch_count += 1
        if batch_count > 1:
            return True
        return False

    executor._check_stop_requested = mock_check_stop

    result = await executor.execute_plan(plan)

    assert result.stopped_early, "Should be marked as stopped early"
    assert result.batches_completed < 3, "Should not complete all batches"

    print(f"[PASS] Execution stopped on request after {result.batches_completed} batches")


async def test_batch_result_dataclass():
    """BatchResult dataclass works correctly."""
    print("\n=== Test: BatchResult Dataclass ===")

    result = BatchResult(
        batch_id=1,
        success=True,
        task_results=[
            ExecutionResult(task_id=1, success=True, duration=1.0, cost=0.01),
            ExecutionResult(task_id=2, success=True, duration=2.0, cost=0.02),
        ],
        duration=3.0,
        merge_status="success",
        errors=[],
        cost=0.03
    )

    assert result.batch_id == 1
    assert result.success
    assert len(result.task_results) == 2
    assert result.merge_status == "success"

    print("[PASS] BatchResult dataclass works correctly")


async def test_mode_selection_parallel():
    """_should_use_parallel returns True for parallelizable plans."""
    print("\n=== Test: Mode Selection (Parallel) ===")

    # Import orchestrator's method
    from core.orchestrator import AgentOrchestrator

    orch = AgentOrchestrator.__new__(AgentOrchestrator)

    # Plan with parallel batch
    plan = {
        'batches': [
            {'task_ids': [1], 'can_parallel': False},
            {'task_ids': [2, 3, 4], 'can_parallel': True},  # Parallel with 3 tasks
            {'task_ids': [5], 'can_parallel': False},
        ]
    }

    result = orch._should_use_parallel(plan)
    assert result, "Should select parallel mode"

    print("[PASS] Parallel mode selected for parallelizable plan")


async def test_mode_selection_sequential():
    """_should_use_parallel returns False for non-parallelizable plans."""
    print("\n=== Test: Mode Selection (Sequential) ===")

    from core.orchestrator import AgentOrchestrator

    orch = AgentOrchestrator.__new__(AgentOrchestrator)

    # Plan with no parallel batches
    plan = {
        'batches': [
            {'task_ids': [1], 'can_parallel': False},
            {'task_ids': [2], 'can_parallel': False},
        ]
    }

    result = orch._should_use_parallel(plan)
    assert not result, "Should select sequential mode"

    # Plan with parallel batch but only 1 task
    plan2 = {
        'batches': [
            {'task_ids': [1], 'can_parallel': True},  # Only 1 task, not worth parallel
        ]
    }

    result2 = orch._should_use_parallel(plan2)
    assert not result2, "Should select sequential for single-task parallel batch"

    print("[PASS] Sequential mode selected for non-parallelizable plans")


async def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("BATCH EXECUTOR TESTS")
    print("=" * 60)

    await test_execute_plan_all_sequential()
    await test_execute_plan_with_parallel()
    await test_batch_failure_stops_execution()
    await test_progress_callbacks()
    await test_stop_request()
    await test_batch_result_dataclass()
    await test_mode_selection_parallel()
    await test_mode_selection_sequential()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
