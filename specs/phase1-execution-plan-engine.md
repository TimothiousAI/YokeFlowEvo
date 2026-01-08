# Implementation Plan: Phase 1 - Execution Plan Engine

## Task Description

Build an execution plan during Session 0 that determines parallel batches, worktree assignments, and file conflict analysis. This plan becomes the foundation for automatic parallel execution in Phase 2.

## Objectives

- [ ] Store execution plans in `projects.metadata.execution_plan`
- [ ] Compute parallel batches using existing DependencyResolver
- [ ] Predict file conflicts between concurrent tasks
- [ ] Pre-assign tasks to worktrees based on epic boundaries
- [ ] Provide API endpoints for plan retrieval and manual adjustment
- [ ] Automatically trigger plan building after Session 0 completes

## Relevant Files

| File | Purpose | Action |
|------|---------|--------|
| `core/execution_plan.py` | ExecutionPlanBuilder class | Create |
| `core/database.py` | Methods for execution plan CRUD | Modify |
| `core/orchestrator.py` | Integration after Session 0 | Modify |
| `api/main.py` | API endpoints | Modify |
| `core/parallel/dependency_resolver.py` | Already exists, will be used | Reference |

## Implementation Phases

### Batch 1 (No Dependencies - Can Run in Parallel)
- Create `core/execution_plan.py` with ExecutionPlanBuilder class
- Add database methods for execution plan storage

### Batch 2 (Depends on Batch 1)
- Create API endpoints for execution plan
- Integrate into orchestrator (post-Session 0 hook)

## File Specifications

---

### File: core/execution_plan.py

**Purpose**: Build execution plans that determine parallel batches, predict file conflicts, and pre-assign worktrees.

**Requirements**:
- `ExecutionPlanBuilder` class with async methods
- Uses `DependencyResolver` for batch computation
- Analyzes task descriptions for file predictions
- Groups tasks by epic for worktree assignment
- Validates no file conflicts within same batch
- Returns serializable plan structure

**Related Files**:
- `core/parallel/dependency_resolver.py` - Uses for batch computation
- `core/database.py` - Uses for task/epic queries and plan storage

**Code Style & Patterns**:
```python
# From backend/expertise.yaml - async patterns
async def build_plan(self, project_id: UUID) -> ExecutionPlan:
    async with self.db.acquire() as conn:
        tasks = await conn.fetch(query, project_id)
    # ... processing
    return plan

# From database/expertise.yaml - parameterized queries
await conn.fetch(
    "SELECT * FROM tasks WHERE project_id = $1 AND done = false",
    project_id
)
```

**Data Structures**:
```python
@dataclass
class ExecutionPlan:
    project_id: UUID
    created_at: datetime
    batches: List[ExecutionBatch]
    worktree_assignments: Dict[int, str]  # task_id -> worktree_name
    predicted_conflicts: List[FileConflict]
    metadata: Dict[str, Any]

@dataclass
class ExecutionBatch:
    batch_id: int
    task_ids: List[int]
    can_parallel: bool
    depends_on: List[int]  # Previous batch IDs
    estimated_duration: Optional[int]  # seconds

@dataclass
class FileConflict:
    task_ids: List[int]
    predicted_files: List[str]
    conflict_type: str  # "same_file", "same_directory", "potential"
```

**Key Methods**:
```python
class ExecutionPlanBuilder:
    def __init__(self, db: TaskDatabase):
        self.db = db
        self.resolver = DependencyResolver()

    async def build_plan(self, project_id: UUID) -> ExecutionPlan:
        """Build complete execution plan for a project."""

    async def analyze_file_conflicts(self, tasks: List[Dict]) -> List[FileConflict]:
        """Predict which tasks might modify same files."""

    async def assign_worktrees(self, batches: List[ExecutionBatch], epics: List[Dict]) -> Dict[int, str]:
        """Pre-assign tasks to worktrees based on epic boundaries."""

    async def validate_batch(self, batch: ExecutionBatch, conflicts: List[FileConflict]) -> bool:
        """Ensure no conflicting tasks in same batch."""
```

**File Conflict Analysis Logic**:
- Parse task descriptions for file path patterns (e.g., "modify api/main.py")
- Extract mentioned file extensions and directories
- Check epic descriptions for module/area hints
- Mark tasks touching same predicted files as conflicting
- Force conflicting tasks into sequential batches

**Worktree Assignment Logic**:
- Group tasks by epic_id
- Assign one worktree per epic (up to max_worktrees)
- If more epics than worktrees, combine smaller epics
- Naming convention: `worktree-batch{N}-epic{M}`

**Validation**:
```bash
pytest tests/test_execution_plan.py -v
python -m mypy core/execution_plan.py
```

---

### File: core/database.py

**Purpose**: Add methods for execution plan storage and retrieval.

**Requirements**:
- Store plan in `projects.metadata.execution_plan`
- Store predicted files in `tasks.metadata.predicted_files`
- Methods: `save_execution_plan`, `get_execution_plan`, `update_task_predicted_files`

**Related Files**:
- `schema/postgresql/schema.sql` - Existing schema (uses JSONB)

**Code Style & Patterns**:
```python
# From database/expertise.yaml
async def save_execution_plan(
    self,
    project_id: UUID,
    plan: Dict[str, Any]
) -> None:
    async with self.acquire() as conn:
        await conn.execute(
            """
            UPDATE projects
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'),
                '{execution_plan}',
                $1::jsonb
            )
            WHERE id = $2
            """,
            json.dumps(plan), project_id
        )
```

**Methods to Add**:
```python
async def save_execution_plan(self, project_id: UUID, plan: Dict[str, Any]) -> None:
    """Save execution plan to project metadata."""

async def get_execution_plan(self, project_id: UUID) -> Optional[Dict[str, Any]]:
    """Get execution plan from project metadata."""

async def update_task_predicted_files(self, task_id: int, files: List[str]) -> None:
    """Update predicted files for a task."""

async def get_tasks_for_planning(self, project_id: UUID) -> List[Dict[str, Any]]:
    """Get all tasks with dependencies for execution planning."""
```

**Validation**:
```bash
pytest tests/test_database_abstraction.py -v -k "execution_plan"
```

---

### File: api/main.py

**Purpose**: Add API endpoints for execution plan management.

**Requirements**:
- `GET /api/projects/{id}/execution-plan` - Get current plan
- `POST /api/projects/{id}/execution-plan/build` - Trigger plan building
- `PATCH /api/projects/{id}/execution-plan` - Manual adjustments
- WebSocket event for plan updates

**Related Files**:
- `core/execution_plan.py` - Uses ExecutionPlanBuilder
- `core/database.py` - Uses for data access

**Code Style & Patterns**:
```python
# From backend/expertise.yaml
@app.get("/api/projects/{project_id}/execution-plan")
async def get_execution_plan(project_id: UUID):
    async with get_db() as db:
        plan = await db.get_execution_plan(project_id)
        if not plan:
            raise HTTPException(status_code=404, detail="No execution plan found")
        return plan

@app.post("/api/projects/{project_id}/execution-plan/build")
async def build_execution_plan(
    project_id: UUID,
    background_tasks: BackgroundTasks
):
    background_tasks.add_task(build_plan_task, project_id)
    return {"status": "building", "message": "Execution plan build started"}
```

**Pydantic Models**:
```python
class ExecutionPlanResponse(BaseModel):
    project_id: UUID
    created_at: datetime
    batches: List[Dict[str, Any]]
    worktree_assignments: Dict[str, str]
    predicted_conflicts: List[Dict[str, Any]]

class ExecutionPlanPatch(BaseModel):
    worktree_assignments: Optional[Dict[str, str]] = None
    batch_overrides: Optional[Dict[int, Dict[str, Any]]] = None
```

**Validation**:
```bash
curl http://localhost:8000/api/projects/{id}/execution-plan
```

---

### File: core/orchestrator.py

**Purpose**: Integrate execution plan building after Session 0 completes.

**Requirements**:
- After initialization session completes successfully, trigger plan building
- Store plan in database
- Log plan summary
- Broadcast WebSocket event

**Related Files**:
- `core/execution_plan.py` - Uses ExecutionPlanBuilder

**Integration Point** (around line 1110):
```python
# After: await self.quality.run_test_coverage_analysis(project_id, db)
# Add:
if is_initializer and status != "error":
    await self.quality.run_test_coverage_analysis(project_id, db)

    # Build execution plan after successful initialization
    await self._build_execution_plan(project_id, db, session_logger)
```

**New Method**:
```python
async def _build_execution_plan(
    self,
    project_id: UUID,
    db: TaskDatabase,
    session_logger: Optional[Any] = None
) -> None:
    """Build and store execution plan after initialization."""
    from core.execution_plan import ExecutionPlanBuilder

    builder = ExecutionPlanBuilder(db)
    plan = await builder.build_plan(project_id)

    # Save plan
    await db.save_execution_plan(project_id, plan.to_dict())

    # Log summary
    if session_logger:
        session_logger.log_event("execution_plan_built", {
            "batches": len(plan.batches),
            "total_tasks": sum(len(b.task_ids) for b in plan.batches),
            "parallel_batches": sum(1 for b in plan.batches if b.can_parallel),
            "conflicts_detected": len(plan.predicted_conflicts)
        })

    # Broadcast WebSocket update
    await self._broadcast_event(project_id, "execution_plan_ready", {
        "batches": len(plan.batches)
    })
```

**Validation**:
```bash
# Run initialization and verify plan is created
python -c "
import asyncio
from core.orchestrator import Orchestrator
# Test initialization creates plan
"
```

---

## Testing Strategy

### Unit Tests (`tests/test_execution_plan.py`)

```python
import pytest
from uuid import uuid4
from core.execution_plan import ExecutionPlanBuilder, ExecutionPlan

@pytest.mark.asyncio
async def test_build_plan_empty_project():
    """Plan for project with no tasks returns empty batches."""

@pytest.mark.asyncio
async def test_build_plan_single_batch():
    """Tasks with no dependencies form single batch."""

@pytest.mark.asyncio
async def test_build_plan_multiple_batches():
    """Tasks with dependencies form multiple batches."""

@pytest.mark.asyncio
async def test_file_conflict_detection():
    """Tasks mentioning same files are detected as conflicts."""

@pytest.mark.asyncio
async def test_worktree_assignment():
    """Tasks are assigned to worktrees by epic."""

@pytest.mark.asyncio
async def test_conflict_forces_sequential():
    """Conflicting tasks are moved to sequential batches."""
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_plan_saved_after_initialization():
    """After Session 0, execution plan is saved to database."""

@pytest.mark.asyncio
async def test_api_get_execution_plan():
    """API returns execution plan for project."""

@pytest.mark.asyncio
async def test_api_build_execution_plan():
    """API triggers execution plan building."""
```

## Acceptance Criteria

- [ ] Execution plan is automatically built after Session 0 completes
- [ ] Plan contains batches computed by DependencyResolver
- [ ] File conflicts are detected and logged
- [ ] Tasks are assigned to worktrees by epic
- [ ] Plan is stored in `projects.metadata.execution_plan`
- [ ] API endpoints return/modify execution plan
- [ ] WebSocket broadcasts plan ready event
- [ ] All tests pass

## Validation Commands

```bash
# Run all Phase 1 tests
pytest tests/test_execution_plan.py -v

# Type check new files
python -m mypy core/execution_plan.py

# Verify API endpoints
curl -X GET http://localhost:8000/api/projects/{id}/execution-plan
curl -X POST http://localhost:8000/api/projects/{id}/execution-plan/build

# Full test suite
pytest tests/ -v --ignore=tests/test_mcp.py
```

## Dependencies

- Existing: `core/parallel/dependency_resolver.py`
- Existing: `core/database.py` (JSONB metadata support)
- Existing: `api/main.py` (WebSocket infrastructure)

## Notes

- No schema migration needed - using existing JSONB `metadata` columns
- File conflict analysis uses heuristics (keywords in descriptions) - can be improved in future
- Max worktrees defaults to 4 (from settings.json)
