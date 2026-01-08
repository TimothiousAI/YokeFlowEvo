"""
Batch Executor
==============

Manages the execution of batches from an execution plan, coordinating
with ParallelExecutor and handling batch lifecycle.

Key Features:
- Consumes execution plans and processes batches
- Coordinates with ParallelExecutor for task execution
- Manages batch transitions (pending -> running -> completed)
- Triggers merge validation after each parallel batch
- Handles failures with automatic fallback
- Tracks costs and performance per batch
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Awaitable, Tuple
from uuid import UUID
from datetime import datetime
import asyncio
import logging

from core.execution_plan import ExecutionPlan, ExecutionBatch
from core.parallel.parallel_executor import ParallelExecutor, ExecutionResult
from core.parallel.worktree_manager import WorktreeManager

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """
    Result of executing a batch.

    Attributes:
        batch_id: The batch that was executed
        success: Whether all tasks completed successfully
        task_results: Results from each task
        duration: Total execution time in seconds
        merge_status: Merge validation result
        errors: List of error messages
        cost: Total cost in USD
    """
    batch_id: int
    success: bool
    task_results: List[ExecutionResult]
    duration: float
    merge_status: str = "skipped"  # "success", "conflicts", "test_failed", "skipped"
    errors: List[str] = field(default_factory=list)
    cost: float = 0.0


@dataclass
class PlanExecutionResult:
    """
    Result of executing an entire plan.

    Attributes:
        success: Whether all batches completed successfully
        batch_results: Results from each batch
        total_duration: Total execution time
        total_cost: Total cost across all batches
        batches_completed: Number of successfully completed batches
        batches_total: Total number of batches
        stopped_early: Whether execution was stopped before completion
    """
    success: bool
    batch_results: List[BatchResult]
    total_duration: float
    total_cost: float
    batches_completed: int
    batches_total: int
    stopped_early: bool = False


class BatchExecutor:
    """
    Executes batches from an execution plan.

    Coordinates parallel task execution within batches and
    handles merge validation between batches.
    """

    def __init__(
        self,
        project_id: UUID,
        project_path: str,
        db: Any,
        max_concurrency: int = 3,
        progress_callback: Optional[Callable[[Dict], Awaitable[None]]] = None,
        run_tests_after_merge: bool = True
    ):
        """
        Initialize batch executor.

        Args:
            project_id: Project UUID
            project_path: Path to project repository
            db: Database connection
            max_concurrency: Maximum concurrent agents
            progress_callback: Async callback for progress updates
            run_tests_after_merge: Whether to run tests after merge
        """
        self.project_id = project_id
        self.project_path = project_path
        self.db = db
        self.max_concurrency = max_concurrency
        self.progress_callback = progress_callback
        self.run_tests_after_merge = run_tests_after_merge

        self._stop_requested = False
        self._current_batch: Optional[int] = None

        # Initialize parallel executor
        self.parallel_executor = ParallelExecutor(
            project_path=project_path,
            project_id=str(project_id),
            max_concurrency=max_concurrency,
            progress_callback=self._wrap_progress_callback(),
            db_connection=db
        )

        # Initialize worktree manager
        self.worktree_manager = WorktreeManager(
            project_path=project_path,
            project_id=str(project_id),
            db=db
        )

        logger.info(
            f"BatchExecutor initialized for project {project_id}, "
            f"max_concurrency={max_concurrency}"
        )

    def _wrap_progress_callback(self) -> Optional[Callable]:
        """Wrap progress callback to add batch context."""
        if not self.progress_callback:
            return None

        async def wrapped_callback(event: Dict) -> None:
            # Add batch context
            event['batch_id'] = self._current_batch
            await self.progress_callback(event)

        return wrapped_callback

    async def execute_plan(self, plan: ExecutionPlan) -> PlanExecutionResult:
        """
        Execute all batches in the execution plan sequentially.

        Each batch is executed (possibly in parallel internally), then merged
        and validated before proceeding to the next batch.

        Args:
            plan: The execution plan to execute

        Returns:
            PlanExecutionResult with overall execution status
        """
        logger.info(
            f"Starting plan execution: {len(plan.batches)} batches, "
            f"{sum(len(b.task_ids) for b in plan.batches)} total tasks"
        )

        start_time = datetime.utcnow()
        batch_results: List[BatchResult] = []
        self._stop_requested = False

        # Initialize worktree manager
        await self.worktree_manager.initialize()

        for batch_idx, batch in enumerate(plan.batches):
            # Check for stop request
            if self._stop_requested:
                logger.info("Stop requested, halting plan execution")
                break

            # Check for stop request in database
            if await self._check_stop_requested():
                logger.info("Stop requested via database, halting plan execution")
                self._stop_requested = True
                break

            self._current_batch = batch.batch_id

            # Notify batch start
            await self._notify_progress("batch_started", {
                "batch_id": batch.batch_id,
                "batch_index": batch_idx,
                "task_count": len(batch.task_ids),
                "can_parallel": batch.can_parallel,
                "batches_remaining": len(plan.batches) - batch_idx
            })

            # Execute batch
            result = await self.execute_batch(batch, plan.worktree_assignments)
            batch_results.append(result)

            # Notify batch completion
            await self._notify_progress("batch_completed", {
                "batch_id": batch.batch_id,
                "success": result.success,
                "duration": result.duration,
                "merge_status": result.merge_status,
                "errors": result.errors
            })

            # Stop if batch failed
            if not result.success:
                logger.error(
                    f"Batch {batch.batch_id} failed with {len(result.errors)} errors, "
                    f"stopping execution"
                )
                break

        # Calculate totals
        total_duration = (datetime.utcnow() - start_time).total_seconds()
        total_cost = sum(r.cost for r in batch_results)
        batches_completed = sum(1 for r in batch_results if r.success)

        overall_success = (
            len(batch_results) == len(plan.batches) and
            all(r.success for r in batch_results)
        )

        # Update project metadata with results
        await self._update_execution_status(
            success=overall_success,
            batches_completed=batches_completed,
            total_batches=len(plan.batches)
        )

        return PlanExecutionResult(
            success=overall_success,
            batch_results=batch_results,
            total_duration=total_duration,
            total_cost=total_cost,
            batches_completed=batches_completed,
            batches_total=len(plan.batches),
            stopped_early=self._stop_requested or not overall_success
        )

    async def execute_batch(
        self,
        batch: ExecutionBatch,
        worktree_assignments: Dict[int, str]
    ) -> BatchResult:
        """
        Execute a single batch with parallel or sequential execution.

        Args:
            batch: The batch to execute
            worktree_assignments: Task ID to worktree mapping

        Returns:
            BatchResult with execution details
        """
        logger.info(
            f"Executing batch {batch.batch_id}: {len(batch.task_ids)} tasks, "
            f"parallel={batch.can_parallel}"
        )

        start_time = datetime.utcnow()
        task_results: List[ExecutionResult] = []
        errors: List[str] = []

        try:
            if batch.can_parallel and len(batch.task_ids) > 1:
                # Parallel execution
                task_results, errors = await self._execute_parallel(
                    batch, worktree_assignments
                )
            else:
                # Sequential execution
                task_results, errors = await self._execute_sequential(batch)

        except Exception as e:
            logger.error(f"Batch {batch.batch_id} execution error: {e}", exc_info=True)
            errors.append(f"Batch execution error: {e}")

        # Merge validation (only if tasks were in worktrees and had parallel execution)
        merge_status = "skipped"
        if batch.can_parallel and len(batch.task_ids) > 1:
            merge_status, merge_errors = await self._validate_and_merge(batch.batch_id)
            errors.extend(merge_errors)

        duration = (datetime.utcnow() - start_time).total_seconds()
        total_cost = sum(r.cost for r in task_results)
        success = (
            all(r.success for r in task_results) and
            merge_status not in ("conflicts", "test_failed") and
            len(errors) == 0
        )

        logger.info(
            f"Batch {batch.batch_id} completed: success={success}, "
            f"duration={duration:.1f}s, cost=${total_cost:.4f}"
        )

        return BatchResult(
            batch_id=batch.batch_id,
            success=success,
            task_results=task_results,
            duration=duration,
            merge_status=merge_status,
            errors=errors,
            cost=total_cost
        )

    async def _execute_parallel(
        self,
        batch: ExecutionBatch,
        worktree_assignments: Dict[int, str]
    ) -> Tuple[List[ExecutionResult], List[str]]:
        """
        Execute batch tasks in parallel using worktrees.

        Returns:
            Tuple of (task_results, errors)
        """
        errors: List[str] = []

        # Create worktrees for tasks that need them
        worktrees_created = await self._setup_batch_worktrees(
            batch, worktree_assignments
        )

        # Execute tasks in parallel with concurrency limit
        task_results = await self.parallel_executor.execute_batch(
            batch.batch_id, batch.task_ids
        )

        # Collect errors from failed tasks
        for result in task_results:
            if not result.success and result.error:
                errors.append(f"Task {result.task_id}: {result.error}")

        return task_results, errors

    async def _execute_sequential(
        self,
        batch: ExecutionBatch
    ) -> Tuple[List[ExecutionResult], List[str]]:
        """
        Execute batch tasks sequentially.

        Returns:
            Tuple of (task_results, errors)
        """
        task_results: List[ExecutionResult] = []
        errors: List[str] = []

        for task_id in batch.task_ids:
            # Check for stop request
            if self._stop_requested or await self._check_stop_requested():
                errors.append("Execution stopped by user request")
                break

            try:
                # Use parallel executor for single task (reuses infrastructure)
                results = await self.parallel_executor.execute_batch(
                    batch.batch_id, [task_id]
                )
                if results:
                    result = results[0]
                    task_results.append(result)
                    if not result.success and result.error:
                        errors.append(f"Task {task_id}: {result.error}")
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                errors.append(f"Task {task_id}: {e}")
                task_results.append(ExecutionResult(
                    task_id=task_id,
                    success=False,
                    duration=0,
                    error=str(e)
                ))

        return task_results, errors

    async def _setup_batch_worktrees(
        self,
        batch: ExecutionBatch,
        worktree_assignments: Dict[int, str]
    ) -> List[str]:
        """
        Set up worktrees for parallel batch execution.

        Returns:
            List of created worktree paths
        """
        created = []

        # Group tasks by worktree
        worktree_tasks: Dict[str, List[int]] = {}
        for task_id in batch.task_ids:
            wt_name = worktree_assignments.get(task_id)
            if wt_name:
                if wt_name not in worktree_tasks:
                    worktree_tasks[wt_name] = []
                worktree_tasks[wt_name].append(task_id)

        # Create worktrees
        for wt_name, task_ids in worktree_tasks.items():
            try:
                # Get epic_id from first task
                epic_id = await self._get_task_epic_id(task_ids[0])
                if epic_id:
                    wt_info = await self.worktree_manager.create_worktree(epic_id)
                    created.append(wt_info.path)
                    logger.info(f"Created worktree {wt_name} for tasks {task_ids}")
            except Exception as e:
                logger.warning(f"Failed to create worktree {wt_name}: {e}")

        return created

    async def _validate_and_merge(
        self,
        batch_id: int
    ) -> Tuple[str, List[str]]:
        """
        Validate and merge worktrees after parallel batch execution.

        Returns:
            Tuple of (status, errors)
        """
        try:
            # Import here to avoid circular dependency
            from core.parallel.merge_validator import MergeValidator

            validator = MergeValidator(self.project_path, self.db)
            result = await validator.validate_batch(batch_id)

            return result.status, result.conflicts

        except ImportError:
            # MergeValidator not yet implemented, skip
            logger.warning("MergeValidator not available, skipping merge validation")
            return "skipped", []
        except Exception as e:
            logger.error(f"Merge validation failed: {e}")
            return "error", [str(e)]

    async def _check_stop_requested(self) -> bool:
        """Check if stop was requested via database."""
        try:
            project = await self.db.get_project(self.project_id)
            if project:
                metadata = project.get('metadata', {})
                if isinstance(metadata, str):
                    import json
                    metadata = json.loads(metadata)
                return metadata.get('parallel_stop_requested', False)
        except Exception:
            pass
        return False

    async def _get_task_epic_id(self, task_id: int) -> Optional[int]:
        """Get epic_id for a task."""
        try:
            task = await self.db.get_task(task_id, self.project_id)
            return task.get('epic_id') if task else None
        except Exception:
            return None

    async def _update_execution_status(
        self,
        success: bool,
        batches_completed: int,
        total_batches: int
    ) -> None:
        """Update project metadata with execution status."""
        try:
            import json
            status = "completed" if success else "failed"
            await self.db.update_project_metadata(self.project_id, {
                'parallel_status': status,
                'parallel_completed_at': datetime.utcnow().isoformat(),
                'batches_completed': batches_completed,
                'batches_total': total_batches
            })
        except Exception as e:
            logger.warning(f"Failed to update execution status: {e}")

    async def _notify_progress(self, event: str, data: Dict) -> None:
        """Send progress update to callback."""
        if self.progress_callback:
            try:
                await self.progress_callback({
                    'type': event,
                    'project_id': str(self.project_id),
                    'timestamp': datetime.utcnow().isoformat(),
                    **data
                })
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    def request_stop(self) -> None:
        """Request graceful stop of execution."""
        logger.info("Stop requested for batch executor")
        self._stop_requested = True
