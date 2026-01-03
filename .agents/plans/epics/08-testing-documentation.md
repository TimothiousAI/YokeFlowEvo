# Epic 08: Testing & Documentation

**Priority:** P1 (Required for Release)
**Estimated Duration:** 3-4 days
**Dependencies:** Epics 01-07 (All prior epics)
**Phase:** 3

---

## Overview

Comprehensive testing suite and documentation for the parallel execution system. Ensures reliability, provides migration guides, and enables future maintenance.

---

## Tasks

### 8.1 Unit Test Suite

**Description:** Complete unit test coverage for all new modules.

**Test Files:**

```
tests/
├── parallel/
│   ├── test_dependency_resolver.py
│   ├── test_worktree_manager.py
│   ├── test_parallel_executor.py
│   └── test_running_agents.py
├── learning/
│   ├── test_expertise_manager.py
│   └── test_model_selector.py
└── test_parallel_integration.py
```

**DependencyResolver Tests:**

```python
# tests/parallel/test_dependency_resolver.py
import pytest
from core.parallel.dependency_resolver import DependencyResolver, DependencyGraph

class TestDependencyResolver:
    """Tests for Kahn's algorithm implementation"""

    @pytest.fixture
    def resolver(self):
        return DependencyResolver()

    def test_no_dependencies_single_batch(self, resolver):
        """All independent tasks go in one batch"""
        tasks = [
            {"id": 1, "epic_id": 1, "depends_on": []},
            {"id": 2, "epic_id": 1, "depends_on": []},
            {"id": 3, "epic_id": 2, "depends_on": []},
        ]
        epics = [{"id": 1}, {"id": 2}]

        result = resolver.resolve(tasks, epics)

        assert len(result.batches) == 1
        assert set(result.batches[0]) == {1, 2, 3}
        assert result.circular_deps == []

    def test_linear_chain_multiple_batches(self, resolver):
        """A -> B -> C produces three batches"""
        tasks = [
            {"id": 1, "epic_id": 1, "depends_on": []},
            {"id": 2, "epic_id": 1, "depends_on": [1]},
            {"id": 3, "epic_id": 1, "depends_on": [2]},
        ]
        epics = [{"id": 1}]

        result = resolver.resolve(tasks, epics)

        assert len(result.batches) == 3
        assert result.task_order == [1, 2, 3]

    def test_diamond_dependency(self, resolver):
        """A -> (B, C) -> D produces three batches"""
        tasks = [
            {"id": 1, "epic_id": 1, "depends_on": []},
            {"id": 2, "epic_id": 1, "depends_on": [1]},
            {"id": 3, "epic_id": 1, "depends_on": [1]},
            {"id": 4, "epic_id": 1, "depends_on": [2, 3]},
        ]
        epics = [{"id": 1}]

        result = resolver.resolve(tasks, epics)

        assert len(result.batches) == 3
        assert result.batches[0] == [1]
        assert set(result.batches[1]) == {2, 3}
        assert result.batches[2] == [4]

    def test_circular_dependency_detection(self, resolver):
        """Detects A -> B -> C -> A cycle"""
        tasks = [
            {"id": 1, "epic_id": 1, "depends_on": [3]},
            {"id": 2, "epic_id": 1, "depends_on": [1]},
            {"id": 3, "epic_id": 1, "depends_on": [2]},
        ]
        epics = [{"id": 1}]

        result = resolver.resolve(tasks, epics)

        assert len(result.circular_deps) > 0
        assert {1, 2, 3}.issubset(result.circular_deps[0])

    def test_missing_dependency_reported(self, resolver):
        """Reports references to non-existent tasks"""
        tasks = [
            {"id": 1, "epic_id": 1, "depends_on": [999]},
        ]
        epics = [{"id": 1}]

        result = resolver.resolve(tasks, epics)

        assert (1, 999) in result.missing_deps

    def test_priority_ordering_within_batch(self, resolver):
        """Higher priority tasks first within batch"""
        tasks = [
            {"id": 1, "epic_id": 1, "priority": 2, "depends_on": []},
            {"id": 2, "epic_id": 1, "priority": 1, "depends_on": []},
            {"id": 3, "epic_id": 2, "priority": 3, "depends_on": []},
        ]
        epics = [{"id": 1, "priority": 1}, {"id": 2, "priority": 2}]

        result = resolver.resolve(tasks, epics)

        # Task 2 has priority 1, should be first
        assert result.batches[0][0] == 2

    def test_epic_dependency_inheritance(self, resolver):
        """Tasks inherit epic-level dependencies"""
        tasks = [
            {"id": 1, "epic_id": 1, "depends_on": []},
            {"id": 2, "epic_id": 2, "depends_on": []},  # Epic 2 depends on Epic 1
        ]
        epics = [
            {"id": 1, "depends_on": []},
            {"id": 2, "depends_on": [1]},
        ]

        result = resolver.resolve(tasks, epics)

        # Task 2 should come after task 1
        assert result.task_order.index(1) < result.task_order.index(2)
```

**WorktreeManager Tests:**

```python
# tests/parallel/test_worktree_manager.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from core.parallel.worktree_manager import WorktreeManager, WorktreeInfo

class TestWorktreeManager:
    """Tests for git worktree management"""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create a temporary git repository"""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        # Initialize git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "Initial"],
                       cwd=repo_path, capture_output=True)
        return repo_path

    @pytest.fixture
    def manager(self, temp_repo):
        return WorktreeManager(temp_repo)

    @pytest.mark.asyncio
    async def test_create_worktree(self, manager, temp_repo):
        """Creates worktree and branch successfully"""
        path = await manager.create_worktree(1, "Auth Feature")

        assert path.exists()
        assert (path / ".git").exists()
        assert "epic/1-auth-feature" in await manager._get_current_branch(path)

    @pytest.mark.asyncio
    async def test_reuse_existing_worktree(self, manager):
        """Reuses existing worktree instead of creating new"""
        path1 = await manager.create_worktree(1, "Auth Feature")
        path2 = await manager.create_worktree(1, "Auth Feature")

        assert path1 == path2

    @pytest.mark.asyncio
    async def test_merge_no_conflicts(self, manager, temp_repo):
        """Merges worktree successfully when no conflicts"""
        # Create worktree
        wt_path = await manager.create_worktree(1, "Test Epic")

        # Make a change in worktree
        test_file = wt_path / "test.txt"
        test_file.write_text("test content")
        await manager._run_git(["add", "."], wt_path)
        await manager._run_git(["commit", "-m", "Test commit"], wt_path)

        # Merge
        success = await manager.merge_worktree(1)

        assert success
        assert (temp_repo / "test.txt").exists()

    @pytest.mark.asyncio
    async def test_merge_with_conflicts(self, manager, temp_repo):
        """Detects and handles merge conflicts"""
        # Create worktree
        wt_path = await manager.create_worktree(1, "Test Epic")

        # Create conflict - same file modified in both
        conflict_file = temp_repo / "conflict.txt"
        conflict_file.write_text("main branch content")
        await manager._run_git(["add", "."], temp_repo)
        await manager._run_git(["commit", "-m", "Main change"], temp_repo)

        wt_conflict = wt_path / "conflict.txt"
        wt_conflict.write_text("worktree content")
        await manager._run_git(["add", "."], wt_path)
        await manager._run_git(["commit", "-m", "Worktree change"], wt_path)

        # Merge should fail
        success = await manager.merge_worktree(1)

        assert not success
        worktree = await manager.get_worktree_status(1)
        assert worktree.status == 'conflict'

    @pytest.mark.asyncio
    async def test_cleanup_worktree(self, manager):
        """Removes worktree and branch after merge"""
        wt_path = await manager.create_worktree(1, "Test Epic")
        await manager.merge_worktree(1)
        await manager.cleanup_worktree(1)

        assert not wt_path.exists()
        assert 1 not in manager._active_worktrees

    @pytest.mark.asyncio
    async def test_branch_name_sanitization(self, manager):
        """Handles special characters in epic names"""
        path = await manager.create_worktree(1, "Feature: Auth & User's Login!")

        worktree = await manager.get_worktree_status(1)
        # Should have sanitized branch name
        assert " " not in worktree.branch
        assert ":" not in worktree.branch
```

**ParallelExecutor Tests:**

```python
# tests/parallel/test_parallel_executor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.parallel.parallel_executor import ParallelExecutor

class TestParallelExecutor:
    """Tests for parallel task execution"""

    @pytest.fixture
    def executor(self):
        return ParallelExecutor(
            project_id="test-project",
            max_concurrency=3
        )

    @pytest.mark.asyncio
    async def test_respects_concurrency_limit(self, executor):
        """Never exceeds max_concurrency agents"""
        tasks = [{"id": i, "epic_id": 1} for i in range(10)]
        batches = [[1, 2, 3, 4, 5]]  # 5 tasks, limit 3

        concurrent_count = 0
        max_concurrent = 0

        async def mock_execute(task):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)
            concurrent_count -= 1
            return True

        with patch.object(executor, '_execute_task', mock_execute):
            await executor.execute_batch(batches[0], tasks)

        assert max_concurrent <= 3

    @pytest.mark.asyncio
    async def test_batch_waits_for_all(self, executor):
        """Batch completes only when all tasks done"""
        completion_order = []

        async def mock_execute(task):
            await asyncio.sleep(task['id'] * 0.1)  # Variable delay
            completion_order.append(task['id'])
            return True

        tasks = [{"id": i, "epic_id": 1} for i in [3, 1, 2]]

        with patch.object(executor, '_execute_task', mock_execute):
            await executor.execute_batch([1, 2, 3], tasks)

        # All tasks should be complete
        assert set(completion_order) == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_abort_stops_execution(self, executor):
        """Abort cancels running tasks"""
        started = []

        async def mock_execute(task):
            started.append(task['id'])
            await asyncio.sleep(10)  # Long running
            return True

        tasks = [{"id": i, "epic_id": 1} for i in range(5)]

        async def abort_after_delay():
            await asyncio.sleep(0.1)
            await executor.abort()

        with patch.object(executor, '_execute_task', mock_execute):
            asyncio.create_task(abort_after_delay())
            await executor.execute_batch([1, 2, 3, 4, 5], tasks)

        # Not all tasks should have completed
        assert len(started) < 5

    @pytest.mark.asyncio
    async def test_handles_task_failure(self, executor):
        """Continues batch despite individual task failures"""
        results = []

        async def mock_execute(task):
            if task['id'] == 2:
                raise Exception("Task 2 failed")
            results.append(task['id'])
            return True

        tasks = [{"id": i, "epic_id": 1} for i in [1, 2, 3]]

        with patch.object(executor, '_execute_task', mock_execute):
            await executor.execute_batch([1, 2, 3], tasks)

        # Other tasks should still complete
        assert 1 in results
        assert 3 in results
```

**Acceptance Criteria:**
- [ ] > 80% code coverage for new modules
- [ ] All edge cases tested
- [ ] Async tests work correctly
- [ ] Mocking used appropriately

---

### 8.2 Integration Test Suite

**Description:** End-to-end tests for parallel execution flow.

**File:** `tests/test_parallel_integration.py`

```python
import pytest
import asyncio
from pathlib import Path
from core.parallel import DependencyResolver, WorktreeManager, ParallelExecutor
from core.database import DatabaseManager

class TestParallelIntegration:
    """End-to-end integration tests"""

    @pytest.fixture
    async def setup_project(self, tmp_path):
        """Set up a test project with tasks"""
        # Initialize git repo
        project_path = tmp_path / "test_project"
        project_path.mkdir()
        subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "Initial"],
                       cwd=project_path, capture_output=True)

        # Create database entries
        async with DatabaseManager() as db:
            project = await db.create_project(
                name="Test Project",
                project_path=str(project_path),
                spec_path=str(project_path / "spec.txt")
            )

            # Create epics
            epic1 = await db.create_epic(
                project_id=project['id'],
                name="Epic 1",
                description="First epic"
            )
            epic2 = await db.create_epic(
                project_id=project['id'],
                name="Epic 2",
                description="Second epic",
                depends_on=[epic1['id']]
            )

            # Create tasks
            task1 = await db.create_task(
                project_id=project['id'],
                epic_id=epic1['id'],
                description="Task 1"
            )
            task2 = await db.create_task(
                project_id=project['id'],
                epic_id=epic1['id'],
                description="Task 2"
            )
            task3 = await db.create_task(
                project_id=project['id'],
                epic_id=epic2['id'],
                description="Task 3",
                depends_on=[task1['id'], task2['id']]
            )

        return {
            'project': project,
            'project_path': project_path,
            'epics': [epic1, epic2],
            'tasks': [task1, task2, task3]
        }

    @pytest.mark.asyncio
    async def test_full_parallel_execution(self, setup_project):
        """Complete parallel execution flow"""
        project = setup_project['project']
        project_path = setup_project['project_path']

        # Resolve dependencies
        resolver = DependencyResolver()
        async with DatabaseManager() as db:
            tasks = await db.list_tasks(project['id'])
            epics = await db.list_epics(project['id'])

        graph = resolver.resolve(tasks, epics)

        # Should have 2 batches: [task1, task2] then [task3]
        assert len(graph.batches) == 2
        assert set(graph.batches[0]) == {tasks[0]['id'], tasks[1]['id']}
        assert graph.batches[1] == [tasks[2]['id']]

        # Create worktrees
        worktree_manager = WorktreeManager(project_path)
        await worktree_manager.initialize()

        wt1 = await worktree_manager.create_worktree(epics[0]['id'], "Epic 1")
        wt2 = await worktree_manager.create_worktree(epics[1]['id'], "Epic 2")

        assert wt1.exists()
        assert wt2.exists()

        # Execute (with mocked agent)
        executor = ParallelExecutor(project['id'], max_concurrency=2)

        async def mock_agent(task, worktree):
            # Simulate work
            (worktree / f"task_{task['id']}.py").write_text(f"# Task {task['id']}")
            await worktree_manager._run_git(["add", "."], worktree)
            await worktree_manager._run_git(
                ["commit", "-m", f"Implement task {task['id']}"],
                worktree
            )
            return True

        with patch.object(executor, '_run_agent', mock_agent):
            results = await executor.execute_all_batches(graph.batches, tasks, worktree_manager)

        assert all(r['success'] for r in results)

        # Merge worktrees
        assert await worktree_manager.merge_worktree(epics[0]['id'])
        assert await worktree_manager.merge_worktree(epics[1]['id'])

        # Verify files exist in main
        assert (project_path / "task_1.py").exists()
        assert (project_path / "task_2.py").exists()
        assert (project_path / "task_3.py").exists()

    @pytest.mark.asyncio
    async def test_handles_merge_conflict(self, setup_project):
        """Handles merge conflicts gracefully"""
        project_path = setup_project['project_path']
        epics = setup_project['epics']

        worktree_manager = WorktreeManager(project_path)
        await worktree_manager.initialize()

        wt1 = await worktree_manager.create_worktree(epics[0]['id'], "Epic 1")
        wt2 = await worktree_manager.create_worktree(epics[1]['id'], "Epic 2")

        # Create conflict - both modify same file
        conflict_file_1 = wt1 / "shared.py"
        conflict_file_1.write_text("# Epic 1 version")
        await worktree_manager._run_git(["add", "."], wt1)
        await worktree_manager._run_git(["commit", "-m", "Epic 1 change"], wt1)

        conflict_file_2 = wt2 / "shared.py"
        conflict_file_2.write_text("# Epic 2 version")
        await worktree_manager._run_git(["add", "."], wt2)
        await worktree_manager._run_git(["commit", "-m", "Epic 2 change"], wt2)

        # First merge succeeds
        assert await worktree_manager.merge_worktree(epics[0]['id'])

        # Second merge detects conflict
        success = await worktree_manager.merge_worktree(epics[1]['id'])
        assert not success

        details = await worktree_manager.get_conflict_details(epics[1]['id'])
        assert 'shared.py' in str(details['conflicting_files'])
```

**Acceptance Criteria:**
- [ ] Full flow tested
- [ ] Merge conflicts handled
- [ ] Database state correct
- [ ] Git state correct

---

### 8.3 Performance Benchmarks

**Description:** Benchmark parallel vs sequential execution.

**File:** `tests/benchmarks/test_parallel_performance.py`

```python
import pytest
import time
import asyncio

class TestParallelPerformance:
    """Performance benchmarks for parallel execution"""

    @pytest.mark.benchmark
    async def test_parallel_vs_sequential_speedup(self):
        """Measure speedup from parallel execution"""
        num_tasks = 10
        task_duration = 0.5  # seconds

        # Sequential execution
        start = time.time()
        for i in range(num_tasks):
            await asyncio.sleep(task_duration)
        sequential_time = time.time() - start

        # Parallel execution (concurrency=3)
        executor = ParallelExecutor(max_concurrency=3)
        start = time.time()
        await asyncio.gather(*[
            asyncio.sleep(task_duration)
            for _ in range(num_tasks)
        ])
        parallel_time = time.time() - start

        speedup = sequential_time / parallel_time

        # With concurrency=3, expect ~3x speedup
        assert speedup > 2.5
        print(f"Speedup: {speedup:.2f}x")

    @pytest.mark.benchmark
    async def test_dependency_resolution_performance(self):
        """Benchmark dependency resolution with many tasks"""
        resolver = DependencyResolver()

        # Generate large task graph
        num_tasks = 1000
        tasks = []
        for i in range(num_tasks):
            deps = [j for j in range(max(0, i-5), i)]  # Each task depends on up to 5 prior
            tasks.append({"id": i, "epic_id": i % 10, "depends_on": deps})

        epics = [{"id": i} for i in range(10)]

        start = time.time()
        result = resolver.resolve(tasks, epics)
        duration = time.time() - start

        assert duration < 1.0  # Should complete in under 1 second
        print(f"Resolved {num_tasks} tasks in {duration:.3f}s")

    @pytest.mark.benchmark
    async def test_worktree_creation_overhead(self):
        """Measure worktree creation overhead"""
        # This tests actual git operations
        # Expect < 500ms per worktree
        pass
```

**Acceptance Criteria:**
- [ ] Speedup measured
- [ ] Resolution scales to 1000+ tasks
- [ ] Worktree overhead acceptable
- [ ] Results documented

---

### 8.4 Documentation Updates

**Description:** Update documentation for parallel execution.

**Files to Update:**

**`docs/parallel-execution.md` (new):**

```markdown
# Parallel Execution Guide

## Overview

YokeFlow supports parallel execution of independent tasks across multiple
agent instances. This dramatically reduces total execution time for large
projects.

## How It Works

1. **Dependency Resolution**: Tasks are analyzed using Kahn's algorithm to
   identify which can run in parallel.

2. **Worktree Isolation**: Each epic gets its own git worktree, preventing
   file conflicts between parallel agents.

3. **Batch Execution**: Tasks are grouped into batches. All tasks in a batch
   run concurrently; batches execute sequentially.

4. **Merge Process**: After each batch completes, worktrees are merged back
   to the main branch.

## Configuration

```yaml
# .yokeflow.yaml
parallel:
  enabled: true
  max_concurrency: 3
  strategy: "by_epic"
  worktree_dir: ".worktrees"
  merge_strategy: "merge"
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| enabled | false | Enable parallel execution |
| max_concurrency | 3 | Maximum concurrent agents |
| strategy | by_epic | Parallelization strategy |
| worktree_dir | .worktrees | Worktree location |
| merge_strategy | merge | How to merge (merge/squash) |

## Dependencies

Tasks can declare dependencies:

```json
{
  "description": "Implement login API",
  "depends_on": [1, 2],
  "dependency_type": "hard"
}
```

### Dependency Types

- **hard**: Must complete before starting (default)
- **soft**: Should complete but can proceed

## Viewing Progress

### Web UI

Navigate to `/projects/{id}/parallel` for the parallel execution dashboard:
- Swimlane visualization of tasks
- Real-time agent output streaming
- Worktree status panel
- Cost tracking

### API

```bash
# Get parallel batches
curl http://localhost:8000/api/projects/{id}/dependencies/batches

# Get worktree status
curl http://localhost:8000/api/projects/{id}/worktrees
```

## Troubleshooting

### Merge Conflicts

If a merge conflict occurs:

1. The worktree status shows "conflict"
2. Check conflict details via API
3. Resolve manually or use resolution strategy

### Agent Failures

Failed agents don't block the batch:
- Other tasks continue
- Failed task marked for retry
- Check logs for error details

## Best Practices

1. **Keep tasks independent**: Minimize dependencies for more parallelism
2. **Use epic-level isolation**: Group related tasks in epics
3. **Monitor costs**: Parallel execution increases API costs
4. **Set reasonable concurrency**: 3-5 is usually optimal
```

**`CLAUDE.md` Update:**

Add section:

```markdown
## Parallel Execution

**Status**: Available (disabled by default)

**Enable**: Set `parallel.enabled: true` in `.yokeflow.yaml`

**Key concepts**:
- Kahn's algorithm for dependency resolution
- Git worktrees for isolation
- Batch-based concurrent execution
- WebSocket events for real-time updates

**Files**:
- `core/parallel/` - Parallel execution modules
- `core/learning/` - Self-learning and cost optimization
- `web-ui/src/pages/projects/[id]/parallel.tsx` - Dashboard
```

**Acceptance Criteria:**
- [ ] Parallel guide complete
- [ ] CLAUDE.md updated
- [ ] API docs updated
- [ ] Configuration documented

---

### 8.5 Migration Guide

**Description:** Guide for upgrading existing projects.

**File:** `docs/migration/parallel-upgrade.md`

```markdown
# Upgrading to Parallel Execution

## Prerequisites

- YokeFlow v2.0+
- PostgreSQL with updated schema
- Git 2.20+ (worktree support)

## Database Migration

Run the schema migration:

```bash
psql $DATABASE_URL < schema/postgresql/parallel_execution.sql
```

This adds:
- `parallel_batches` table
- `worktrees` table
- `agent_costs` table
- `expertise_files` table
- `depends_on` columns to tasks/epics

## Configuration Update

Add to `.yokeflow.yaml`:

```yaml
parallel:
  enabled: true
  max_concurrency: 3
  strategy: "by_epic"

learning:
  enabled: true
  expertise_max_lines: 1000

cost:
  enabled: true
  budget_limit_usd: null
```

## Existing Projects

Existing projects can be upgraded:

1. Dependencies will be inferred from task descriptions
2. Worktrees created on next run
3. Progress preserved

## Breaking Changes

None - parallel execution is opt-in.

## Rollback

To disable parallel execution:

1. Set `parallel.enabled: false`
2. Delete `.worktrees/` directory
3. Tables can remain (not used)
```

**Acceptance Criteria:**
- [ ] Migration steps clear
- [ ] Database migration works
- [ ] Backward compatible
- [ ] Rollback documented

---

### 8.6 API Documentation

**Description:** Document new API endpoints.

**File:** `docs/api/parallel-endpoints.md`

```markdown
# Parallel Execution API

## Dependencies

### GET /api/projects/{project_id}/dependencies

Get the full dependency graph.

**Query Parameters:**
- `format`: json | mermaid | ascii (default: json)

**Response:**
```json
{
  "batches": [[1, 2], [3, 4], [5]],
  "task_order": [1, 2, 3, 4, 5],
  "circular_deps": [],
  "missing_deps": []
}
```

### GET /api/projects/{project_id}/dependencies/batches

Get tasks grouped into parallel batches.

**Response:**
```json
{
  "batches": [
    {
      "batch_number": 1,
      "status": "completed",
      "task_ids": [1, 2],
      "started_at": "2024-01-15T10:00:00Z",
      "completed_at": "2024-01-15T10:15:00Z"
    }
  ]
}
```

## Worktrees

### GET /api/projects/{project_id}/worktrees

List all worktrees.

**Response:**
```json
{
  "worktrees": [
    {
      "epic_id": 1,
      "branch": "epic/1-auth",
      "status": "active",
      "tasks_completed": 3,
      "total_tasks": 5
    }
  ]
}
```

### POST /api/projects/{project_id}/worktrees/{epic_id}/merge

Merge a worktree back to main.

**Request:**
```json
{
  "squash": false
}
```

**Response:**
```json
{
  "success": true,
  "merge_commit": "abc123..."
}
```

## Costs

### GET /api/projects/{project_id}/costs

Get cost breakdown.

**Response:**
```json
{
  "total_cost_usd": 12.45,
  "budget_limit_usd": 50.0,
  "by_model": {
    "opus": { "cost": 8.20, "calls": 5 },
    "sonnet": { "cost": 4.15, "calls": 42 }
  }
}
```

## Parallel Execution Control

### POST /api/projects/{project_id}/parallel/start

Start parallel execution.

### POST /api/projects/{project_id}/parallel/stop

Stop parallel execution (graceful).

### POST /api/projects/{project_id}/parallel/abort

Abort all running agents immediately.
```

**Acceptance Criteria:**
- [ ] All endpoints documented
- [ ] Request/response examples
- [ ] Error codes listed
- [ ] Authentication noted

---

## Testing Requirements

### Documentation Tests

```python
class TestDocumentation:
    def test_all_endpoints_documented(self):
        """Every API endpoint has documentation"""

    def test_code_examples_valid(self):
        """Code examples in docs are syntactically valid"""

    def test_config_examples_valid(self):
        """YAML config examples are valid"""
```

---

## Dependencies

- All prior epics (01-07)

## Dependents

- None (final epic)

---

## Notes

- Keep docs in sync with implementation
- Include real-world examples
- Test migration on sample project
- Consider video walkthrough
