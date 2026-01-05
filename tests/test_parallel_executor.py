"""
Unit tests for ParallelExecutor

Tests parallel execution orchestration with mocked dependencies.
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.parallel_executor import (
    ParallelExecutor,
    ExecutionResult,
    RunningAgent
)


def create_mock_db(tasks):
    """Create a fully mocked database with all required methods."""
    db = Mock()
    db.get_tasks_with_dependencies = AsyncMock(return_value=tasks)
    db.create_parallel_batch = AsyncMock(return_value={'id': 1})
    db.update_batch_status = AsyncMock()
    db.list_parallel_batches = AsyncMock(return_value=[
        {'id': 1, 'batch_number': 1, 'status': 'pending'}
    ])
    db.get_task_with_tests = AsyncMock(side_effect=lambda task_id, project_id: next(
        (t for t in tasks if t['id'] == task_id), None
    ))
    db.update_task_status = AsyncMock()
    db.record_agent_cost = AsyncMock()
    return db


class TestSingleBatchExecution:
    """Test execution of a single batch of tasks."""

    async def test_single_batch_success(self):
        """Test successful execution of single batch."""
        print("\n=== Test: Single Batch Execution Success ===")

        temp_dir = tempfile.mkdtemp(prefix='parallel_test_')
        try:
            project_uuid = "12345678-1234-5678-1234-567812345678"

            executor = ParallelExecutor(
                project_path=temp_dir,
                project_id=project_uuid,
                max_concurrency=3
            )

            tasks = [
                {'id': 1, 'epic_id': 1, 'epic_name': 'Epic 1', 'description': 'Task 1', 'action': 'Do task 1'},
                {'id': 2, 'epic_id': 1, 'epic_name': 'Epic 1', 'description': 'Task 2', 'action': 'Do task 2'},
                {'id': 3, 'epic_id': 1, 'epic_name': 'Epic 1', 'description': 'Task 3', 'action': 'Do task 3'},
            ]

            # Mock dependencies
            with patch.object(executor.dependency_resolver, 'resolve') as mock_resolve:
                with patch.object(executor.worktree_manager, 'initialize', new_callable=AsyncMock):
                    with patch.object(executor.worktree_manager, 'create_worktree', new_callable=AsyncMock) as mock_create:
                        with patch.object(executor, 'run_task_agent', new_callable=AsyncMock) as mock_run:
                            with patch.object(executor.worktree_manager, 'merge_worktree', new_callable=AsyncMock) as mock_merge:
                                # Setup mocks
                                mock_resolve.return_value = Mock(
                                    batches=[[1, 2, 3]],
                                    task_order=[1, 2, 3],
                                    circular_deps=[],
                                    missing_deps=[]
                                )

                                mock_create.return_value = Mock(
                                    path=f"{temp_dir}/.worktrees/epic-1",
                                    branch="epic-1-test",
                                    epic_id=1,
                                    status="active"
                                )

                                mock_run.return_value = ExecutionResult(
                                    task_id=1,
                                    success=True,
                                    duration=1.0,
                                    cost=0.01
                                )

                                mock_merge.return_value = "abc123"

                                # Mock database
                                executor.db = create_mock_db(tasks)

                                # Execute
                                results = await executor.execute()

                                assert len(results) == 3
                                assert all(r.success for r in results)
                                assert mock_create.call_count >= 1

                                print(f"✓ Executed {len(results)} tasks successfully")
                                print(f"✓ Created worktrees")

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestMultiBatchExecution:
    """Test sequential execution of multiple batches."""

    async def test_multi_batch_sequential(self):
        """Test that batches execute sequentially."""
        print("\n=== Test: Multi-Batch Sequential Execution ===")

        temp_dir = tempfile.mkdtemp(prefix='parallel_test_')
        try:
            project_uuid = "12345678-1234-5678-1234-567812345678"

            executor = ParallelExecutor(
                project_path=temp_dir,
                project_id=project_uuid,
                max_concurrency=3
            )

            batch_execution_order = []

            async def mock_execute_batch(batch_num, task_ids):
                batch_execution_order.append(batch_num)
                await asyncio.sleep(0.01)  # Simulate work
                return [
                    ExecutionResult(task_id=tid, success=True, duration=0.01, cost=0.001)
                    for tid in task_ids
                ]

            with patch.object(executor.dependency_resolver, 'resolve') as mock_resolve:
                with patch.object(executor, 'execute_batch', side_effect=mock_execute_batch) as mock_exec_batch:
                    # Setup: 3 batches
                    mock_resolve.return_value = Mock(
                        batches=[[1, 2], [3, 4], [5]],
                        task_order=[1, 2, 3, 4, 5],
                        circular_deps=[],
                        missing_deps=[]
                    )

                    executor.db = Mock()
                    executor.db.get_tasks_with_dependencies = AsyncMock(return_value=[
                        {'id': i, 'epic_id': 1, 'description': f'Task {i}', 'action': f'Do task {i}'}
                        for i in range(1, 6)
                    ])
                    executor.db.create_parallel_batch = AsyncMock(return_value={'id': 1})
                    executor.db.update_batch_status = AsyncMock()

                    # Execute
                    results = await executor.execute()

                    # Verify batches executed in order
                    assert batch_execution_order == [0, 1, 2]
                    assert len(results) == 5
                    print(f"✓ Executed {len(results)} tasks across 3 batches")
                    print(f"✓ Batch execution order: {batch_execution_order}")

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestConcurrencyLimit:
    """Test concurrency limit enforcement."""

    async def test_concurrency_limit_enforced(self):
        """Test that max concurrent agents is respected."""
        print("\n=== Test: Concurrency Limit Enforcement ===")

        temp_dir = tempfile.mkdtemp(prefix='parallel_test_')
        try:
            project_uuid = "12345678-1234-5678-1234-567812345678"

            # Set low concurrency limit
            executor = ParallelExecutor(
                project_path=temp_dir,
                project_id=project_uuid,
                max_concurrency=2  # Only 2 concurrent tasks
            )

            concurrent_count = 0
            max_concurrent = 0

            async def mock_run_task(task, worktree_path):
                nonlocal concurrent_count, max_concurrent
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)

                await asyncio.sleep(0.05)  # Simulate work

                concurrent_count -= 1
                return ExecutionResult(
                    task_id=task['id'],
                    success=True,
                    duration=0.05,
                    cost=0.01
                )

            with patch.object(executor.dependency_resolver, 'resolve') as mock_resolve:
                with patch.object(executor.worktree_manager, 'create_worktree', new_callable=AsyncMock):
                    with patch.object(executor, 'run_task_agent', side_effect=mock_run_task):
                        with patch.object(executor.worktree_manager, 'merge_worktree', new_callable=AsyncMock):
                            mock_resolve.return_value = Mock(
                                batches=[[1, 2, 3, 4, 5]],  # All in one batch
                                task_order=[1, 2, 3, 4, 5],
                                circular_deps=[],
                                missing_deps=[]
                            )

                            executor.db = Mock()
                            executor.db.get_tasks_with_dependencies = AsyncMock(return_value=[
                                {'id': i, 'epic_id': 1, 'description': f'Task {i}', 'action': f'Do task {i}'}
                                for i in range(1, 6)
                            ])
                            executor.db.create_parallel_batch = AsyncMock(return_value={'id': 1})
                            executor.db.update_batch_status = AsyncMock()

                            await executor.execute()

                            # Max concurrent should not exceed limit
                            assert max_concurrent <= 2, f"Max concurrent was {max_concurrent}, limit is 2"
                            print(f"✓ Max concurrent agents: {max_concurrent} (limit: 2)")

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestFailureHandling:
    """Test handling of task failures."""

    async def test_partial_batch_failure(self):
        """Test that batch continues even with partial failures."""
        print("\n=== Test: Partial Batch Failure Handling ===")

        temp_dir = tempfile.mkdtemp(prefix='parallel_test_')
        try:
            project_uuid = "12345678-1234-5678-1234-567812345678"

            executor = ParallelExecutor(
                project_path=temp_dir,
                project_id=project_uuid,
                max_concurrency=3
            )

            async def mock_run_task(task, worktree_path):
                # Task 2 fails
                if task['id'] == 2:
                    return ExecutionResult(
                        task_id=2,
                        success=False,
                        duration=0.1,
                        error="Simulated failure",
                        cost=0.01
                    )
                return ExecutionResult(
                    task_id=task['id'],
                    success=True,
                    duration=0.1,
                    cost=0.01
                )

            with patch.object(executor.dependency_resolver, 'resolve') as mock_resolve:
                with patch.object(executor.worktree_manager, 'create_worktree', new_callable=AsyncMock):
                    with patch.object(executor, 'run_task_agent', side_effect=mock_run_task):
                        with patch.object(executor.worktree_manager, 'merge_worktree', new_callable=AsyncMock):
                            mock_resolve.return_value = Mock(
                                batches=[[1, 2, 3]],
                                task_order=[1, 2, 3],
                                circular_deps=[],
                                missing_deps=[]
                            )

                            executor.db = Mock()
                            executor.db.get_tasks_with_dependencies = AsyncMock(return_value=[
                                {'id': 1, 'epic_id': 1, 'description': 'Task 1', 'action': 'Do 1'},
                                {'id': 2, 'epic_id': 1, 'description': 'Task 2', 'action': 'Do 2'},
                                {'id': 3, 'epic_id': 1, 'description': 'Task 3', 'action': 'Do 3'},
                            ])
                            executor.db.create_parallel_batch = AsyncMock(return_value={'id': 1})
                            executor.db.update_batch_status = AsyncMock()

                            results = await executor.execute()

                            assert len(results) == 3
                            success_count = sum(1 for r in results if r.success)
                            failure_count = sum(1 for r in results if not r.success)

                            assert success_count == 2
                            assert failure_count == 1
                            print(f"✓ Batch completed: {success_count} succeeded, {failure_count} failed")

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestCancellation:
    """Test execution cancellation."""

    async def test_cancellation_mid_execution(self):
        """Test that execution can be cancelled mid-batch."""
        print("\n=== Test: Cancellation Mid-Execution ===")

        temp_dir = tempfile.mkdtemp(prefix='parallel_test_')
        try:
            project_uuid = "12345678-1234-5678-1234-567812345678"

            executor = ParallelExecutor(
                project_path=temp_dir,
                project_id=project_uuid,
                max_concurrency=2
            )

            tasks_started = []

            async def mock_run_task(task, worktree_path):
                tasks_started.append(task['id'])

                # Simulate long-running task
                try:
                    await asyncio.sleep(1.0)
                    return ExecutionResult(task_id=task['id'], success=True, duration=1.0, cost=0.01)
                except asyncio.CancelledError:
                    return ExecutionResult(
                        task_id=task['id'],
                        success=False,
                        duration=0.0,
                        error="Cancelled",
                        cost=0.0
                    )

            with patch.object(executor.dependency_resolver, 'resolve') as mock_resolve:
                with patch.object(executor.worktree_manager, 'create_worktree', new_callable=AsyncMock):
                    with patch.object(executor, 'run_task_agent', side_effect=mock_run_task):
                        mock_resolve.return_value = Mock(
                            batches=[[1, 2, 3, 4]],
                            task_order=[1, 2, 3, 4],
                            circular_deps=[],
                            missing_deps=[]
                        )

                        executor.db = Mock()
                        executor.db.get_tasks_with_dependencies = AsyncMock(return_value=[
                            {'id': i, 'epic_id': 1, 'description': f'Task {i}', 'action': f'Do {i}'}
                            for i in range(1, 5)
                        ])
                        executor.db.create_parallel_batch = AsyncMock(return_value={'id': 1})
                        executor.db.update_batch_status = AsyncMock()

                        # Start execution in background
                        exec_task = asyncio.create_task(executor.execute())

                        # Wait a bit for tasks to start
                        await asyncio.sleep(0.1)

                        # Cancel execution
                        await executor.cancel()

                        # Wait for execution to finish
                        try:
                            await exec_task
                        except asyncio.CancelledError:
                            pass

                        # Verify cancellation occurred
                        assert executor._cancel_event.is_set()
                        print(f"✓ Execution cancelled")
                        print(f"✓ Tasks started before cancel: {len(tasks_started)}")

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestProgressCallback:
    """Test progress callback invocation."""

    async def test_progress_callback_called(self):
        """Test that progress callback is invoked during execution."""
        print("\n=== Test: Progress Callback Invocation ===")

        temp_dir = tempfile.mkdtemp(prefix='parallel_test_')
        try:
            project_uuid = "12345678-1234-5678-1234-567812345678"

            callback_invocations = []

            def progress_callback(event_type, data):
                callback_invocations.append((event_type, data))

            executor = ParallelExecutor(
                project_path=temp_dir,
                project_id=project_uuid,
                max_concurrency=2,
                progress_callback=progress_callback
            )

            with patch.object(executor.dependency_resolver, 'resolve') as mock_resolve:
                with patch.object(executor.worktree_manager, 'create_worktree', new_callable=AsyncMock):
                    with patch.object(executor, 'run_task_agent', new_callable=AsyncMock) as mock_run:
                        with patch.object(executor.worktree_manager, 'merge_worktree', new_callable=AsyncMock):
                            mock_resolve.return_value = Mock(
                                batches=[[1, 2]],
                                task_order=[1, 2],
                                circular_deps=[],
                                missing_deps=[]
                            )

                            mock_run.return_value = ExecutionResult(
                                task_id=1,
                                success=True,
                                duration=0.1,
                                cost=0.01
                            )

                            executor.db = Mock()
                            executor.db.get_tasks_with_dependencies = AsyncMock(return_value=[
                                {'id': 1, 'epic_id': 1, 'description': 'Task 1', 'action': 'Do 1'},
                                {'id': 2, 'epic_id': 1, 'description': 'Task 2', 'action': 'Do 2'},
                            ])
                            executor.db.create_parallel_batch = AsyncMock(return_value={'id': 1})
                            executor.db.update_batch_status = AsyncMock()

                            await executor.execute()

                            # Verify callbacks were invoked
                            assert len(callback_invocations) > 0
                            event_types = [inv[0] for inv in callback_invocations]

                            print(f"✓ Progress callback invoked {len(callback_invocations)} times")
                            print(f"✓ Event types: {set(event_types)}")

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


class TestWorktreeAssignment:
    """Test worktree assignment by epic."""

    async def test_worktree_per_epic(self):
        """Test that tasks from same epic use same worktree."""
        print("\n=== Test: Worktree Assignment by Epic ===")

        temp_dir = tempfile.mkdtemp(prefix='parallel_test_')
        try:
            project_uuid = "12345678-1234-5678-1234-567812345678"

            executor = ParallelExecutor(
                project_path=temp_dir,
                project_id=project_uuid,
                max_concurrency=3
            )

            worktree_assignments = {}  # epic_id -> worktree_path

            async def mock_create_worktree(epic_id, epic_name):
                path = f"{temp_dir}/.worktrees/epic-{epic_id}"
                worktree_assignments[epic_id] = path
                return Mock(
                    path=path,
                    branch=f"epic-{epic_id}-{epic_name}",
                    epic_id=epic_id,
                    status="active"
                )

            with patch.object(executor.dependency_resolver, 'resolve') as mock_resolve:
                with patch.object(executor.worktree_manager, 'create_worktree', side_effect=mock_create_worktree):
                    with patch.object(executor, 'run_task_agent', new_callable=AsyncMock) as mock_run:
                        with patch.object(executor.worktree_manager, 'merge_worktree', new_callable=AsyncMock):
                            # Tasks from 2 different epics
                            mock_resolve.return_value = Mock(
                                batches=[[1, 2, 3, 4]],
                                task_order=[1, 2, 3, 4],
                                circular_deps=[],
                                missing_deps=[]
                            )

                            mock_run.return_value = ExecutionResult(
                                task_id=1,
                                success=True,
                                duration=0.1,
                                cost=0.01
                            )

                            executor.db = Mock()
                            executor.db.get_tasks_with_dependencies = AsyncMock(return_value=[
                                {'id': 1, 'epic_id': 1, 'description': 'Task 1', 'action': 'Do 1'},
                                {'id': 2, 'epic_id': 1, 'description': 'Task 2', 'action': 'Do 2'},
                                {'id': 3, 'epic_id': 2, 'description': 'Task 3', 'action': 'Do 3'},
                                {'id': 4, 'epic_id': 2, 'description': 'Task 4', 'action': 'Do 4'},
                            ])
                            executor.db.create_parallel_batch = AsyncMock(return_value={'id': 1})
                            executor.db.update_batch_status = AsyncMock()

                            await executor.execute()

                            # Verify 2 worktrees were created (one per epic)
                            assert len(worktree_assignments) == 2
                            assert 1 in worktree_assignments
                            assert 2 in worktree_assignments
                            print(f"✓ Created {len(worktree_assignments)} worktrees for {len(worktree_assignments)} epics")

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        print("[PASS]")


async def run_all_tests():
    """Run all test suites."""
    print("\n" + "="*60)
    print("Running ParallelExecutor Unit Tests")
    print("="*60)

    try:
        # Single batch tests
        single = TestSingleBatchExecution()
        await single.test_single_batch_success()

        # Multi-batch tests
        multi = TestMultiBatchExecution()
        await multi.test_multi_batch_sequential()

        # Concurrency tests
        concurrency = TestConcurrencyLimit()
        await concurrency.test_concurrency_limit_enforced()

        # Failure handling tests
        failure = TestFailureHandling()
        await failure.test_partial_batch_failure()

        # Cancellation tests
        cancel = TestCancellation()
        await cancel.test_cancellation_mid_execution()

        # Progress callback tests
        progress = TestProgressCallback()
        await progress.test_progress_callback_called()

        # Worktree assignment tests
        worktree = TestWorktreeAssignment()
        await worktree.test_worktree_per_epic()

        print("\n" + "="*60)
        print("[SUCCESS] ALL TESTS PASSED (7/7)")
        print("="*60)
        print("\nTest Coverage:")
        print("  ✓ Single batch execution")
        print("  ✓ Multi-batch sequential execution")
        print("  ✓ Concurrency limit enforcement")
        print("  ✓ Failure handling (partial batch failure)")
        print("  ✓ Cancellation mid-execution")
        print("  ✓ Progress callback invocation")
        print("  ✓ Worktree assignment by epic")

        return True

    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
