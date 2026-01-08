# Implementation Plan: Phase 2 - Automatic Parallel Orchestration

## Task Description

Make parallel execution the default execution path after Session 0 completes. When an execution plan has parallel batches, automatically use the ParallelExecutor instead of sequential session execution.

## Objectives

- [ ] Add mode selection logic after Session 0 (parallel vs sequential)
- [ ] Integrate BatchExecutor with existing ParallelExecutor
- [ ] Implement merge validation pipeline after each batch
- [ ] Enhance progress tracking with batch_id and worktree_id
- [ ] Add API endpoints for parallel execution control
- [ ] Automatic fallback to sequential if parallel fails

## Relevant Files

| File | Purpose | Action |
|------|---------|--------|
| `core/parallel/batch_executor.py` | New BatchExecutor class | Create |
| `core/parallel/merge_validator.py` | Merge validation pipeline | Create |
| `core/orchestrator.py` | Mode selection integration | Modify |
| `core/database.py` | Add batch/worktree tracking methods | Modify |
| `api/main.py` | Parallel execution API endpoints | Modify |
| `core/parallel/parallel_executor.py` | Already exists | Reference |
| `core/parallel/worktree_manager.py` | Already exists | Reference |

## Implementation Phases

### Batch 1 (No Dependencies - Can Run in Parallel)
- Create `core/parallel/batch_executor.py` with BatchExecutor class
- Create `core/parallel/merge_validator.py` for merge pipeline
- Add database methods for batch tracking

### Batch 2 (Depends on Batch 1)
- Integrate mode selection into orchestrator
- Create API endpoints for parallel execution control
- Add progress tracking enhancements

## File Specifications

---

### File: core/parallel/batch_executor.py

**Purpose**: Manages the execution of batches from the execution plan, coordinating with ParallelExecutor and handling batch lifecycle.

**Requirements**:
- `BatchExecutor` class that consumes execution plans
- Coordinates with `ParallelExecutor` for task execution
- Manages batch transitions (pending -> running -> completed)
- Triggers merge validation after each batch
- Handles failures and automatic retries

**Related Files**:
- `core/parallel/parallel_executor.py` - Delegates task execution
- `core/parallel/worktree_manager.py` - Worktree management
- `core/execution_plan.py` - Consumes ExecutionPlan
- `core/parallel/merge_validator.py` - Post-batch validation

**Code Style & Patterns**:
```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Callable, Awaitable
from uuid import UUID
from datetime import datetime
import asyncio
import logging

from core.execution_plan import ExecutionPlan, ExecutionBatch
from core.parallel.parallel_executor import ParallelExecutor, ExecutionResult
from core.parallel.merge_validator import MergeValidator

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Result of executing a batch."""
    batch_id: int
    success: bool
    task_results: List[ExecutionResult]
    duration: float
    merge_status: str  # "success", "conflicts", "skipped"
    errors: List[str]


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
        progress_callback: Optional[Callable[[Dict], Awaitable[None]]] = None
    ):
        self.project_id = project_id
        self.project_path = project_path
        self.db = db
        self.max_concurrency = max_concurrency
        self.progress_callback = progress_callback

        self.parallel_executor = ParallelExecutor(
            project_path=project_path,
            project_id=str(project_id),
            max_concurrency=max_concurrency,
            progress_callback=progress_callback,
            db_connection=db
        )
        self.merge_validator = MergeValidator(project_path, db)

    async def execute_plan(self, plan: ExecutionPlan) -> List[BatchResult]:
        """Execute all batches in the execution plan."""

    async def execute_batch(self, batch: ExecutionBatch) -> BatchResult:
        """Execute a single batch."""

    async def _notify_progress(self, event: str, data: Dict) -> None:
        """Send progress update to callback."""
```

**Key Methods**:
```python
async def execute_plan(self, plan: ExecutionPlan) -> List[BatchResult]:
    """
    Execute all batches in the execution plan sequentially.

    Each batch is executed (possibly in parallel), then merged
    and validated before proceeding to the next batch.
    """
    results = []

    for batch in plan.batches:
        # Update batch status
        await self.db.update_batch_status(batch.batch_id, "running")
        await self._notify_progress("batch_started", {
            "batch_id": batch.batch_id,
            "task_count": len(batch.task_ids),
            "can_parallel": batch.can_parallel
        })

        # Execute batch
        result = await self.execute_batch(batch)
        results.append(result)

        # Update batch status
        status = "completed" if result.success else "failed"
        await self.db.update_batch_status(batch.batch_id, status)

        await self._notify_progress("batch_completed", {
            "batch_id": batch.batch_id,
            "success": result.success,
            "duration": result.duration,
            "merge_status": result.merge_status
        })

        # Stop if batch failed
        if not result.success:
            logger.error(f"Batch {batch.batch_id} failed, stopping execution")
            break

    return results

async def execute_batch(self, batch: ExecutionBatch) -> BatchResult:
    """Execute a single batch with parallel or sequential execution."""
    start_time = datetime.utcnow()
    task_results = []
    errors = []

    if batch.can_parallel and len(batch.task_ids) > 1:
        # Parallel execution
        task_results = await self.parallel_executor.execute_batch(
            batch.batch_id, batch.task_ids
        )
    else:
        # Sequential execution
        for task_id in batch.task_ids:
            result = await self.parallel_executor.execute_task(task_id)
            task_results.append(result)
            if not result.success:
                errors.append(f"Task {task_id}: {result.error}")

    # Merge validation (only if tasks were in worktrees)
    merge_status = "skipped"
    if batch.can_parallel:
        merge_result = await self.merge_validator.validate_batch(batch.batch_id)
        merge_status = merge_result.status
        if merge_result.conflicts:
            errors.extend(merge_result.conflicts)

    duration = (datetime.utcnow() - start_time).total_seconds()
    success = all(r.success for r in task_results) and merge_status != "conflicts"

    return BatchResult(
        batch_id=batch.batch_id,
        success=success,
        task_results=task_results,
        duration=duration,
        merge_status=merge_status,
        errors=errors
    )
```

---

### File: core/parallel/merge_validator.py

**Purpose**: Validates and performs merge operations after parallel batch completion.

**Requirements**:
- Merge worktrees back to main branch
- Detect and report conflicts
- Run test suite on merged result
- Cleanup worktrees after successful merge

**Code Style & Patterns**:
```python
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    """Result of merge validation."""
    status: str  # "success", "conflicts", "test_failed"
    conflicts: List[str]
    test_output: Optional[str]
    merged_worktrees: List[str]


class MergeValidator:
    """
    Validates and merges worktrees after batch completion.
    """

    def __init__(self, project_path: str, db: Any):
        self.project_path = Path(project_path)
        self.db = db

    async def validate_batch(self, batch_id: int) -> MergeResult:
        """Validate and merge all worktrees for a batch."""

    async def merge_worktree(self, worktree_path: str, branch: str) -> bool:
        """Merge a single worktree branch."""

    async def run_tests(self) -> Tuple[bool, str]:
        """Run test suite after merge."""

    async def cleanup_worktrees(self, worktrees: List[str]) -> None:
        """Remove merged worktrees."""
```

**Key Methods**:
```python
async def validate_batch(self, batch_id: int) -> MergeResult:
    """
    Validate and merge all worktrees from a batch.

    Steps:
    1. Get all worktrees for the batch
    2. Attempt merge for each worktree
    3. If any conflicts, abort and report
    4. Run tests on merged result
    5. Cleanup worktrees on success
    """
    # Get worktrees for this batch
    worktrees = await self.db.get_batch_worktrees(batch_id)
    if not worktrees:
        return MergeResult(
            status="success",
            conflicts=[],
            test_output=None,
            merged_worktrees=[]
        )

    conflicts = []
    merged = []

    for wt in worktrees:
        try:
            success = await self.merge_worktree(wt['path'], wt['branch'])
            if success:
                merged.append(wt['path'])
            else:
                conflicts.append(f"Merge conflict in {wt['branch']}")
        except Exception as e:
            conflicts.append(f"Merge error for {wt['branch']}: {e}")

    if conflicts:
        # Abort merge and report
        await self._abort_merge()
        return MergeResult(
            status="conflicts",
            conflicts=conflicts,
            test_output=None,
            merged_worktrees=[]
        )

    # Run tests
    test_pass, test_output = await self.run_tests()
    if not test_pass:
        await self._abort_merge()
        return MergeResult(
            status="test_failed",
            conflicts=[],
            test_output=test_output,
            merged_worktrees=merged
        )

    # Cleanup worktrees
    await self.cleanup_worktrees(merged)

    return MergeResult(
        status="success",
        conflicts=[],
        test_output=test_output,
        merged_worktrees=merged
    )

async def merge_worktree(self, worktree_path: str, branch: str) -> bool:
    """Merge a worktree branch using --no-commit first."""
    # First try merge with --no-commit to detect conflicts
    proc = await asyncio.create_subprocess_exec(
        "git", "merge", "--no-commit", branch,
        cwd=str(self.project_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        # Abort and return failure
        await asyncio.create_subprocess_exec(
            "git", "merge", "--abort",
            cwd=str(self.project_path)
        )
        return False

    # Commit the merge
    proc = await asyncio.create_subprocess_exec(
        "git", "commit", "-m", f"Merge {branch} (batch execution)",
        cwd=str(self.project_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()

    return proc.returncode == 0
```

---

### File: core/orchestrator.py

**Purpose**: Add mode selection logic after Session 0 to choose parallel or sequential execution.

**Requirements**:
- After Session 0 completes, check execution plan
- If `can_parallel` batches exist, use BatchExecutor
- Fall back to sequential if parallel fails
- Track execution mode in session metadata

**Integration Point** (after `_build_execution_plan` call, ~line 1114):
```python
# Build execution plan after successful initialization
await self._build_execution_plan(project_id, db, session_logger)

# Determine execution mode based on plan
plan = await db.get_execution_plan(project_id)
if plan and self._should_use_parallel(plan):
    # Store parallel mode flag
    await db.update_project_metadata(project_id, {
        'execution_mode': 'parallel',
        'parallel_started_at': datetime.utcnow().isoformat()
    })
    logger.info(f"Project {project_id} will use parallel execution")
else:
    await db.update_project_metadata(project_id, {
        'execution_mode': 'sequential'
    })
    logger.info(f"Project {project_id} will use sequential execution")
```

**New Methods**:
```python
def _should_use_parallel(self, plan: Dict[str, Any]) -> bool:
    """
    Determine if parallel execution should be used.

    Conditions:
    - At least one batch has can_parallel=True
    - At least one batch has > 1 task
    - No critical conflicts detected
    """
    if not plan or 'batches' not in plan:
        return False

    batches = plan.get('batches', [])
    parallel_batches = [b for b in batches if b.get('can_parallel') and len(b.get('task_ids', [])) > 1]

    return len(parallel_batches) > 0

async def start_parallel_execution(
    self,
    project_id: UUID,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Start parallel execution for a project using its execution plan.

    Called after Session 0 when parallel mode is selected.
    """
    from core.parallel.batch_executor import BatchExecutor
    from core.execution_plan import ExecutionPlan

    async with DatabaseManager() as db:
        # Get execution plan
        plan_dict = await db.get_execution_plan(project_id)
        if not plan_dict:
            raise ValueError("No execution plan found")

        plan = ExecutionPlan.from_dict(plan_dict)
        project = await db.get_project(project_id)

        # Create batch executor
        executor = BatchExecutor(
            project_id=project_id,
            project_path=project['local_path'],
            db=db,
            max_concurrency=self.config.parallel.max_concurrency,
            progress_callback=progress_callback
        )

        # Execute plan
        results = await executor.execute_plan(plan)

        return {
            'status': 'completed' if all(r.success for r in results) else 'failed',
            'batches_completed': sum(1 for r in results if r.success),
            'batches_total': len(results),
            'total_duration': sum(r.duration for r in results)
        }
```

---

### File: core/database.py

**Purpose**: Add methods for batch and worktree tracking.

**New Methods**:
```python
async def update_batch_status(
    self,
    batch_id: int,
    status: str,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None
) -> None:
    """Update batch execution status."""
    async with self.acquire() as conn:
        await conn.execute(
            """
            UPDATE parallel_batches
            SET status = $1,
                started_at = COALESCE($2, started_at),
                completed_at = COALESCE($3, completed_at)
            WHERE id = $4
            """,
            status, started_at, completed_at, batch_id
        )

async def get_batch_worktrees(self, batch_id: int) -> List[Dict[str, Any]]:
    """Get all worktrees associated with a batch."""
    async with self.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT w.* FROM worktrees w
            JOIN batch_worktrees bw ON w.id = bw.worktree_id
            WHERE bw.batch_id = $1
            """,
            batch_id
        )
        return [dict(r) for r in rows]

async def update_project_metadata(
    self,
    project_id: UUID,
    metadata_updates: Dict[str, Any]
) -> None:
    """Update specific fields in project metadata."""
    async with self.acquire() as conn:
        # Merge updates into existing metadata
        await conn.execute(
            """
            UPDATE projects
            SET metadata = COALESCE(metadata, '{}') || $1::jsonb
            WHERE id = $2
            """,
            json.dumps(metadata_updates), project_id
        )

async def get_project_execution_mode(self, project_id: UUID) -> Optional[str]:
    """Get the execution mode for a project."""
    async with self.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT metadata->>'execution_mode' as mode FROM projects WHERE id = $1",
            project_id
        )
        return row['mode'] if row else None
```

---

### File: api/main.py

**Purpose**: Add API endpoints for parallel execution control.

**New Endpoints**:
```python
@app.post("/api/projects/{project_id}/parallel/start")
async def start_parallel_execution(
    project_id: UUID,
    background_tasks: BackgroundTasks
):
    """
    Start parallel execution for a project.

    Uses the execution plan to execute batches in parallel.
    """
    async with get_db() as db:
        # Verify project has execution plan
        plan = await db.get_execution_plan(project_id)
        if not plan:
            raise HTTPException(
                status_code=400,
                detail="No execution plan found. Run initialization first."
            )

        # Check not already running
        mode = await db.get_project_execution_mode(project_id)
        if mode == 'parallel_running':
            raise HTTPException(
                status_code=409,
                detail="Parallel execution already in progress"
            )

        # Start in background
        background_tasks.add_task(
            run_parallel_execution_task,
            project_id
        )

        return {"status": "started", "message": "Parallel execution initiated"}


@app.get("/api/projects/{project_id}/parallel/status")
async def get_parallel_status(project_id: UUID):
    """Get current parallel execution status."""
    async with get_db() as db:
        project = await db.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        metadata = project.get('metadata', {})
        plan = await db.get_execution_plan(project_id)

        return {
            "execution_mode": metadata.get('execution_mode', 'sequential'),
            "parallel_started_at": metadata.get('parallel_started_at'),
            "batches_total": len(plan.get('batches', [])) if plan else 0,
            "current_batch": metadata.get('current_batch'),
            "completed_batches": metadata.get('completed_batches', 0)
        }


@app.post("/api/projects/{project_id}/parallel/stop")
async def stop_parallel_execution(project_id: UUID):
    """Stop parallel execution gracefully."""
    # Implementation: Set flag that batch executor checks
    async with get_db() as db:
        await db.update_project_metadata(project_id, {
            'parallel_stop_requested': True
        })

    return {"status": "stopping", "message": "Stop requested"}
```

---

## Testing Strategy

### Unit Tests (`tests/test_batch_executor.py`)

```python
@pytest.mark.asyncio
async def test_execute_plan_all_sequential():
    """All sequential batches execute correctly."""

@pytest.mark.asyncio
async def test_execute_plan_with_parallel():
    """Parallel batches execute concurrently."""

@pytest.mark.asyncio
async def test_batch_failure_stops_execution():
    """Failed batch stops further execution."""

@pytest.mark.asyncio
async def test_merge_validation_success():
    """Successful merges complete batch."""

@pytest.mark.asyncio
async def test_merge_conflict_handling():
    """Merge conflicts are detected and reported."""
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_mode_selection_parallel():
    """Parallel mode is selected when plan has parallel batches."""

@pytest.mark.asyncio
async def test_mode_selection_sequential():
    """Sequential mode when no parallel batches."""

@pytest.mark.asyncio
async def test_api_start_parallel():
    """API endpoint starts parallel execution."""
```

## Acceptance Criteria

- [ ] After Session 0, execution mode is determined from plan
- [ ] BatchExecutor correctly processes execution plan
- [ ] Parallel batches execute concurrently within max_concurrency
- [ ] Sequential batches execute one task at a time
- [ ] Merge validation runs after each parallel batch
- [ ] Conflicts are detected and reported
- [ ] Progress callbacks fire for batch events
- [ ] API endpoints work for start/status/stop
- [ ] Fallback to sequential works if parallel fails

## Validation Commands

```bash
# Run Phase 2 tests
pytest tests/test_batch_executor.py tests/test_merge_validator.py -v

# Type check new files
python -m mypy core/parallel/batch_executor.py core/parallel/merge_validator.py

# Verify API endpoints
curl -X POST http://localhost:8000/api/projects/{id}/parallel/start
curl -X GET http://localhost:8000/api/projects/{id}/parallel/status
```

## Dependencies

- Phase 1: `core/execution_plan.py` (ExecutionPlan data structure)
- Existing: `core/parallel/parallel_executor.py`
- Existing: `core/parallel/worktree_manager.py`
- Existing: `core/database.py`

## Notes

- Max concurrency defaults to 3 (from config)
- Merge validation uses `git merge --no-commit` to detect conflicts early
- Test suite execution is optional (skipped if no test command configured)
- Worktrees are cleaned up after successful merge only
