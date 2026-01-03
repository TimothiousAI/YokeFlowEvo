# Epic 04: Parallel Execution Engine

**Priority:** P0 (Critical Path)
**Estimated Duration:** 3-4 days
**Dependencies:** Epic 01 (Foundation), Epic 02 (Dependency Resolution), Epic 03 (Worktree Isolation)
**Phase:** 2

---

## Overview

Implement the core parallel execution engine that orchestrates multiple agents working on independent tasks simultaneously. This is the central component that brings together dependency resolution, worktree isolation, and concurrent execution.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   ParallelExecutor                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Batch Scheduler                                      │   │
│  │  ├── Load tasks and dependencies                     │   │
│  │  ├── Compute parallel batches                        │   │
│  │  └── Queue batches for execution                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Concurrency Controller                               │   │
│  │  ├── Semaphore (max_concurrency)                     │   │
│  │  ├── Running agents map                              │   │
│  │  └── Cancel event handling                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│           ┌──────────────┼──────────────┐                  │
│           ▼              ▼              ▼                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │   Agent 1   │ │   Agent 2   │ │   Agent 3   │          │
│  │  Worktree A │ │  Worktree B │ │  Worktree C │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Tasks

### 4.1 ParallelExecutor Core Implementation

**Description:** Implement the main parallel execution orchestrator.

**File:** `core/parallel/parallel_executor.py`

**Class Structure:**

```python
@dataclass
class ExecutionResult:
    """Result of parallel execution"""
    total_batches: int
    completed_batches: int
    total_tasks: int
    completed_tasks: int
    failed_tasks: List[Dict]
    batch_results: List[Dict]
    total_duration: float
    total_cost: float

@dataclass
class RunningAgent:
    """Tracks a running agent instance"""
    task_id: int
    epic_id: int
    worktree_path: Path
    cancel_event: asyncio.Event
    start_time: float
    model: str

class ParallelExecutor:
    """
    Executes tasks in parallel batches with:
    - Git worktree isolation per epic
    - Dependency-aware batch scheduling
    - Cost-optimized model selection
    - Expertise-informed context injection
    """

    def __init__(
        self,
        project_path: Path,
        project_id: UUID,
        max_concurrency: int = 3,
        progress_callback: Optional[Callable] = None
    ):
        self.project_path = project_path
        self.project_id = project_id
        self.max_concurrency = max_concurrency
        self.progress_callback = progress_callback

        self.worktree_manager = WorktreeManager(project_path)
        self.dependency_resolver = DependencyResolver()
        self.expertise_manager = ExpertiseManager(project_path, project_id)
        self.model_selector = ModelSelector()

        self.running_agents: Dict[str, RunningAgent] = {}
        self.cancel_event = asyncio.Event()

    async def execute_project(self) -> ExecutionResult:
        """Execute all project tasks with parallel batching"""

    async def execute_batch(self, batch_num: int, task_ids: List[int]) -> Dict:
        """Execute a single batch of tasks in parallel"""

    async def run_task_agent(self, task: Dict, worktree_path: Path) -> Dict:
        """Run a single task with its own agent"""

    def cancel(self) -> None:
        """Cancel all running agents"""

    async def get_status(self) -> Dict:
        """Get current execution status"""
```

**Acceptance Criteria:**
- [ ] Executes batches sequentially
- [ ] Executes tasks within batch in parallel
- [ ] Respects max_concurrency limit
- [ ] Handles failures gracefully
- [ ] Supports cancellation

---

### 4.2 Batch Execution Flow

**Description:** Implement the batch-by-batch execution logic.

**Implementation:**

```python
async def execute_project(self) -> ExecutionResult:
    """Execute all project tasks with parallel batching"""
    start_time = time.time()

    async with DatabaseManager() as db:
        # Load tasks and epics
        tasks = await db.list_tasks(self.project_id)
        epics = await db.list_epics(self.project_id)

        # Filter to incomplete tasks only
        incomplete_tasks = [t for t in tasks if not t['done']]

        if not incomplete_tasks:
            return ExecutionResult(
                total_batches=0, completed_batches=0,
                total_tasks=0, completed_tasks=0,
                failed_tasks=[], batch_results=[],
                total_duration=0, total_cost=0
            )

        # Resolve dependencies into batches
        graph = self.dependency_resolver.resolve(incomplete_tasks, epics)

        if graph.circular_deps:
            raise CircularDependencyError(graph.circular_deps)

        # Store batches in database
        for batch_num, task_ids in enumerate(graph.batches):
            await db.create_parallel_batch(
                project_id=self.project_id,
                batch_number=batch_num,
                task_ids=task_ids
            )

        # Initialize worktree manager
        await self.worktree_manager.initialize()

        # Execute batches
        results = ExecutionResult(
            total_batches=len(graph.batches),
            completed_batches=0,
            total_tasks=len(incomplete_tasks),
            completed_tasks=0,
            failed_tasks=[],
            batch_results=[],
            total_duration=0,
            total_cost=0
        )

        for batch_num, task_ids in enumerate(graph.batches):
            if self.cancel_event.is_set():
                break

            await self._emit_progress({
                'type': 'batch_start',
                'batch_number': batch_num,
                'total_batches': len(graph.batches),
                'task_count': len(task_ids)
            })

            batch_result = await self.execute_batch(batch_num, task_ids, db)

            results.batch_results.append(batch_result)
            results.completed_batches += 1
            results.completed_tasks += batch_result['completed']
            results.failed_tasks.extend(batch_result['failed'])
            results.total_cost += batch_result.get('cost', 0)

            await self._emit_progress({
                'type': 'batch_complete',
                'batch_number': batch_num,
                'result': batch_result
            })

        results.total_duration = time.time() - start_time
        return results
```

**Acceptance Criteria:**
- [ ] Loads and filters tasks correctly
- [ ] Creates batch records in database
- [ ] Processes batches in order
- [ ] Aggregates results correctly
- [ ] Emits progress events

---

### 4.3 Concurrent Task Execution

**Description:** Implement parallel task execution within a batch.

**Implementation:**

```python
async def execute_batch(
    self,
    batch_num: int,
    task_ids: List[int],
    db: TaskDatabase
) -> Dict:
    """Execute a single batch of tasks in parallel"""
    batch_start = time.time()

    # Load full task details
    tasks = [await db.get_task(tid) for tid in task_ids]

    # Group tasks by epic for worktree assignment
    epic_tasks = defaultdict(list)
    for task in tasks:
        epic_tasks[task['epic_id']].append(task)

    # Create worktrees for each epic in this batch
    worktrees = {}
    for epic_id in epic_tasks.keys():
        epic = await db.get_epic(epic_id)
        worktree = await self.worktree_manager.create_worktree(
            epic_id, epic['name']
        )
        worktrees[epic_id] = worktree

    # Create task coroutines
    task_coros = []
    for task in tasks:
        worktree_path = worktrees[task['epic_id']]
        task_coros.append(
            self._run_task_with_semaphore(task, worktree_path, db)
        )

    # Execute with concurrency limit
    results = await asyncio.gather(*task_coros, return_exceptions=True)

    # Process results
    completed = []
    failed = []
    batch_cost = 0

    for task, result in zip(tasks, results):
        if isinstance(result, Exception):
            failed.append({
                'task_id': task['id'],
                'error': str(result),
                'traceback': traceback.format_exc()
            })
        elif result.get('status') == 'completed':
            completed.append(task['id'])
            batch_cost += result.get('cost', 0)
        else:
            failed.append({
                'task_id': task['id'],
                'error': result.get('error', 'Unknown error')
            })

    # Merge completed worktrees
    for epic_id in epic_tasks.keys():
        epic_completed = all(
            t['id'] in completed for t in epic_tasks[epic_id]
        )
        if epic_completed:
            success = await self.worktree_manager.merge_worktree(epic_id)
            if success:
                await self.worktree_manager.cleanup_worktree(epic_id)
            else:
                # Mark as needing manual resolution
                for task in epic_tasks[epic_id]:
                    if task['id'] in completed:
                        completed.remove(task['id'])
                        failed.append({
                            'task_id': task['id'],
                            'error': 'Merge conflict'
                        })

    return {
        'batch_number': batch_num,
        'completed': len(completed),
        'failed': failed,
        'duration': time.time() - batch_start,
        'cost': batch_cost
    }

async def _run_task_with_semaphore(
    self,
    task: Dict,
    worktree_path: Path,
    db: TaskDatabase
) -> Dict:
    """Run task with semaphore-based concurrency control"""
    async with self._semaphore:
        return await self.run_task_agent(task, worktree_path, db)
```

**Acceptance Criteria:**
- [ ] Respects max_concurrency via semaphore
- [ ] Groups tasks by epic correctly
- [ ] Merges successful worktrees
- [ ] Handles individual task failures
- [ ] Accumulates costs

---

### 4.4 Individual Task Agent Execution

**Description:** Implement the single task agent runner.

**Implementation:**

```python
async def run_task_agent(
    self,
    task: Dict,
    worktree_path: Path,
    db: TaskDatabase
) -> Dict:
    """Run a single task with its own agent"""
    task_id = task['id']
    agent_id = f"task_{task_id}"

    try:
        # Load expertise for this task's domain
        expertise = await self.expertise_manager.get_expertise_for_task(task)

        # Select optimal model
        model = self.model_selector.select_model(task)

        # Build context-rich prompt
        prompt = self._build_task_prompt(task, expertise)

        # Register running agent
        self.running_agents[agent_id] = RunningAgent(
            task_id=task_id,
            epic_id=task['epic_id'],
            worktree_path=worktree_path,
            cancel_event=asyncio.Event(),
            start_time=time.time(),
            model=model
        )

        await self._emit_progress({
            'type': 'task_start',
            'task_id': task_id,
            'epic_id': task['epic_id'],
            'model': model
        })

        # Create session in database
        session_number = await db.get_next_session_number(self.project_id)
        session = await db.create_session(
            project_id=self.project_id,
            session_number=session_number,
            session_type="coding",
            model=model
        )

        # Run agent session
        result = await self._execute_agent_session(
            task=task,
            prompt=prompt,
            model=model,
            worktree_path=worktree_path,
            session_id=session['id'],
            db=db
        )

        # Update task status
        if result['status'] == 'completed':
            await db.update_task_status(task_id, done=True)

        # Record cost
        cost = self.model_selector.record_usage(
            task=task,
            model=model,
            input_tokens=result.get('input_tokens', 0),
            output_tokens=result.get('output_tokens', 0),
            success=result['status'] == 'completed'
        )

        # Learn from result
        await self.expertise_manager.learn_from_session(
            task, result, result.get('logs', [])
        )

        await self._emit_progress({
            'type': 'task_complete',
            'task_id': task_id,
            'status': result['status'],
            'cost': cost.cost_usd
        })

        return {
            'status': result['status'],
            'cost': cost.cost_usd,
            'duration': time.time() - self.running_agents[agent_id].start_time
        }

    except asyncio.CancelledError:
        return {'status': 'cancelled', 'error': 'Task was cancelled'}

    except Exception as e:
        logger.exception(f"Task {task_id} failed")
        return {'status': 'error', 'error': str(e)}

    finally:
        self.running_agents.pop(agent_id, None)
```

**Acceptance Criteria:**
- [ ] Loads expertise before execution
- [ ] Selects appropriate model
- [ ] Creates session records
- [ ] Updates task status on completion
- [ ] Records costs
- [ ] Learns from results
- [ ] Handles cancellation

---

### 4.5 Agent Session Execution

**Description:** Execute the actual Claude agent session.

**Implementation:**

```python
async def _execute_agent_session(
    self,
    task: Dict,
    prompt: str,
    model: str,
    worktree_path: Path,
    session_id: UUID,
    db: TaskDatabase
) -> Dict:
    """Execute the actual agent session"""
    from core.client import create_client
    from core.agent import run_agent_session
    from core.observability import create_session_logger

    # Create client pointing to worktree
    client = create_client(
        worktree_path,
        model,
        project_id=str(self.project_id)
    )

    # Create session logger
    session_number = await db.get_session_number(session_id)
    session_logger = create_session_logger(
        worktree_path,
        session_number,
        "coding",
        model,
        sandbox_type="local"
    )

    # Run agent
    logs = []
    async with client:
        status, response, summary = await run_agent_session(
            client,
            prompt,
            worktree_path,
            logger=session_logger,
            verbose=False,
            progress_callback=lambda e: logs.append(e)
        )

    # End session in database
    metrics = {
        'duration_seconds': summary.get('duration_seconds', 0),
        'message_count': summary.get('message_count', 0),
        'tool_calls_count': summary.get('tool_use_count', 0),
        'tokens_input': summary.get('tokens_input', 0),
        'tokens_output': summary.get('tokens_output', 0),
    }

    await db.end_session(
        session_id,
        'completed' if status == 'success' else 'error',
        metrics=metrics
    )

    return {
        'status': 'completed' if status == 'success' else 'error',
        'response': response,
        'input_tokens': summary.get('tokens_input', 0),
        'output_tokens': summary.get('tokens_output', 0),
        'logs': logs
    }
```

**Acceptance Criteria:**
- [ ] Creates client with worktree path
- [ ] Runs session successfully
- [ ] Captures all metrics
- [ ] Updates session in database

---

### 4.6 Task Prompt Builder

**Description:** Build context-rich prompts for tasks.

**Implementation:**

```python
def _build_task_prompt(self, task: Dict, expertise: str) -> str:
    """Build a context-rich prompt for the task"""
    return f"""
# Task: {task['description']}

## Task ID
{task['id']}

## Epic
{task.get('epic_name', 'Unknown Epic')}

## Action Required
{task.get('action', 'Implement the feature as described.')}

## Domain Expertise
{expertise}

## Guidelines

1. **Working Directory**: You are working in an isolated git worktree.
   Changes here won't affect other parallel tasks.

2. **Commits**: Commit your changes frequently with descriptive messages.
   Each logical change should be a separate commit.

3. **Testing**: Run relevant tests before marking the task complete.
   Use Playwright for UI verification if applicable.

4. **Documentation**: Update any relevant documentation if your changes
   affect public APIs or user-facing features.

5. **Dependencies**: This task may have dependencies on other tasks.
   If you encounter missing dependencies, note them but proceed with
   what can be implemented.

## Verification

After implementation:
1. Ensure all tests pass
2. Verify the feature works as expected
3. Check for any console errors or warnings
4. Document any edge cases discovered

## When Complete

Use the MCP task-manager tools to:
1. Update the task status to done
2. Log any issues encountered
3. Note any follow-up tasks needed
"""
```

**Acceptance Criteria:**
- [ ] Includes task details
- [ ] Includes expertise
- [ ] Provides clear guidelines
- [ ] Explains worktree context

---

### 4.7 Cancellation and Status

**Description:** Implement cancellation and status reporting.

**Implementation:**

```python
def cancel(self) -> int:
    """Cancel all running agents, return count of cancelled"""
    self.cancel_event.set()

    cancelled = 0
    for agent_id, agent in self.running_agents.items():
        agent.cancel_event.set()
        cancelled += 1

    logger.info(f"Cancelled {cancelled} running agents")
    return cancelled

async def get_status(self) -> Dict:
    """Get current execution status"""
    return {
        'running': not self.cancel_event.is_set(),
        'active_agents': len(self.running_agents),
        'agents': [
            {
                'task_id': agent.task_id,
                'epic_id': agent.epic_id,
                'model': agent.model,
                'duration': time.time() - agent.start_time
            }
            for agent in self.running_agents.values()
        ],
        'max_concurrency': self.max_concurrency
    }
```

**Acceptance Criteria:**
- [ ] Cancellation stops all agents
- [ ] Status returns accurate information
- [ ] Cancelled agents clean up properly

---

### 4.8 Orchestrator Integration

**Description:** Integrate ParallelExecutor with existing Orchestrator.

**File:** `core/orchestrator.py` modifications

**Changes:**

```python
async def start_coding_sessions(
    self,
    project_id: UUID,
    parallel: bool = False,  # NEW PARAMETER
    max_concurrency: int = 3,  # NEW PARAMETER
    # ... existing parameters
) -> SessionInfo:
    """Start coding sessions for a project"""

    if parallel:
        # Use new parallel executor
        from core.parallel import ParallelExecutor

        executor = ParallelExecutor(
            project_path=project_path,
            project_id=project_id,
            max_concurrency=max_concurrency,
            progress_callback=progress_callback
        )

        # Store executor for status/cancellation
        self.parallel_executors[str(project_id)] = executor

        result = await executor.execute_project()

        return self._convert_to_session_info(result)

    else:
        # Existing sequential behavior
        while True:
            session = await self.start_session(...)
            # ... existing loop
```

**Acceptance Criteria:**
- [ ] `parallel=True` uses new executor
- [ ] `parallel=False` uses existing behavior
- [ ] Backward compatible

---

### 4.9 API Endpoints

**Description:** Add API endpoints for parallel execution.

**Endpoints:**

```python
@app.post("/api/projects/{project_id}/parallel/start")
async def start_parallel_execution(
    project_id: str,
    max_concurrency: int = 3,
    current_user: dict = Depends(get_current_user)
):
    """Start parallel task execution"""

@app.get("/api/projects/{project_id}/parallel/status")
async def get_parallel_status(project_id: str):
    """Get parallel execution status"""

@app.post("/api/projects/{project_id}/parallel/cancel")
async def cancel_parallel_execution(project_id: str):
    """Cancel parallel execution"""

@app.get("/api/projects/{project_id}/parallel/batches")
async def list_batches(project_id: str):
    """List all parallel batches"""

@app.get("/api/projects/{project_id}/parallel/batches/{batch_num}")
async def get_batch(project_id: str, batch_num: int):
    """Get batch details"""
```

**Acceptance Criteria:**
- [ ] All endpoints functional
- [ ] Proper authentication
- [ ] WebSocket events for progress

---

### 4.10 CLI Integration

**Description:** Add CLI flag for parallel execution.

**File:** CLI entry point modifications

```python
# Add to CLI arguments
parser.add_argument(
    '--parallel',
    action='store_true',
    help='Enable parallel task execution'
)
parser.add_argument(
    '--max-concurrency',
    type=int,
    default=3,
    help='Maximum concurrent agents (default: 3)'
)

# In main execution
await orchestrator.start_coding_sessions(
    project_id=project_id,
    parallel=args.parallel,
    max_concurrency=args.max_concurrency
)
```

**Acceptance Criteria:**
- [ ] `--parallel` flag enables parallel mode
- [ ] `--max-concurrency` sets limit
- [ ] Help text explains options

---

## Testing Requirements

### Unit Tests

```python
class TestParallelExecutor:
    def test_single_batch(self):
        """Executes single batch correctly"""

    def test_multiple_batches(self):
        """Executes batches in order"""

    def test_concurrency_limit(self):
        """Respects max_concurrency"""

    def test_task_failure_handling(self):
        """Handles failed tasks gracefully"""

    def test_cancellation(self):
        """Cancels running agents"""

    def test_worktree_merge(self):
        """Merges successful worktrees"""
```

### Integration Tests

```python
class TestParallelIntegration:
    def test_end_to_end_parallel(self):
        """Full project execution in parallel mode"""

    def test_parallel_vs_sequential(self):
        """Same result, faster execution"""

    def test_failure_recovery(self):
        """Continues after single task failure"""
```

---

## Dependencies

- Epic 01: Foundation
- Epic 02: Dependency Resolution
- Epic 03: Worktree Isolation

## Dependents

- Epic 05: Self-Learning (learns from execution)
- Epic 06: Cost Optimization (model selection)
- Epic 07: Observability (progress tracking)

---

## Notes

- Consider adding retry logic for failed tasks
- May need connection pooling for many concurrent database operations
- Consider memory usage with many concurrent agents
