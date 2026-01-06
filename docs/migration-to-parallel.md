# Migration Guide: Sequential to Parallel Execution

This guide helps you migrate existing YokeFlow projects from sequential execution to parallel execution mode.

## Table of Contents

- [Should You Migrate?](#should-you-migrate)
- [Prerequisites](#prerequisites)
- [Step-by-Step Migration](#step-by-step-migration)
- [Adding Dependencies](#adding-dependencies)
- [Configuration Changes](#configuration-changes)
- [Testing Before Production](#testing-before-production)
- [Rollback Instructions](#rollback-instructions)
- [FAQ](#faq)

---

## Should You Migrate?

### Good Candidates for Parallel Execution

✅ **Migrate if**:
- Project has 50+ remaining tasks
- Tasks are spread across multiple epics
- Many tasks are independent (different features/files)
- You have multiple CPU cores available
- You want faster completion time

### Poor Candidates for Parallel Execution

❌ **Don't migrate if**:
- Project has <20 remaining tasks (not worth the setup)
- All tasks are highly dependent (sequential chain)
- Limited system resources (2 cores, <8GB RAM)
- Project is nearly complete
- Working fine with sequential execution

### Cost/Benefit Analysis

**Benefits**:
- 3-10x faster completion time (depends on task dependencies)
- Better resource utilization (use all CPU cores)
- Automatic conflict detection with git worktrees

**Costs**:
- Initial setup time (1-2 hours to add dependencies)
- Higher concurrent API costs (but same total tokens)
- More complex debugging if issues arise
- Requires understanding dependency relationships

**Recommendation**: For projects with 100+ tasks across 5+ epics, the time savings (hours to days) far outweigh the setup cost.

---

## Prerequisites

Before migrating, ensure you have:

1. **YokeFlow v1.3.0+**:
   ```bash
   git pull
   # Check version
   cat VERSION
   # Should be 1.3.0 or higher
   ```

2. **Clean git state**:
   ```bash
   cd generations/your-project
   git status
   # Should show: "nothing to commit, working tree clean"
   ```

3. **Database backup**:
   ```bash
   # Backup PostgreSQL database
   docker exec yokeflow-postgres pg_dump -U agent yokeflow > backup.sql
   ```

4. **Task list review**:
   ```bash
   # Check remaining tasks
   python scripts/task_status.py generations/your-project
   ```

---

## Step-by-Step Migration

### Step 1: Analyze Current Tasks

**Understand your task structure**:

```python
# Run this in a Python shell or create a script
import asyncio
from core.database_connection import DatabaseManager
from uuid import UUID

async def analyze_tasks(project_name):
    async with DatabaseManager() as db:
        # Get project
        project = await db.get_project_by_name(project_name)
        project_id = project['id']

        # Get all tasks
        tasks = await db.list_tasks(project_id, only_pending=True)

        # Group by epic
        epics = {}
        for task in tasks:
            epic_id = task['epic_id']
            if epic_id not in epics:
                epics[epic_id] = []
            epics[epic_id].append(task)

        # Print summary
        print(f"Project: {project_name}")
        print(f"Total pending tasks: {len(tasks)}")
        print(f"Epics with pending tasks: {len(epics)}")
        print("\nTasks by epic:")
        for epic_id, epic_tasks in epics.items():
            print(f"  Epic {epic_id}: {len(epic_tasks)} tasks")

# Run analysis
asyncio.run(analyze_tasks("your-project-name"))
```

**Example output**:
```
Project: my-app
Total pending tasks: 87
Epics with pending tasks: 6

Tasks by epic:
  Epic 1: 12 tasks (Backend API)
  Epic 2: 18 tasks (Frontend UI)
  Epic 3: 15 tasks (Authentication)
  Epic 4: 22 tasks (Database)
  Epic 5: 10 tasks (Testing)
  Epic 6: 10 tasks (Deployment)
```

### Step 2: Identify Dependencies

**For each epic, identify task dependencies**:

1. **Review task descriptions**: Look for phrases like "build on", "extends", "integrates with"
2. **Check file overlap**: Tasks touching same files likely have dependencies
3. **Consider logical flow**: Database schema before models, models before API endpoints
4. **Cross-epic dependencies**: Frontend tasks that need API endpoints

**Create dependency map** (example):

```
Epic 1: Backend API
  Task 1: Database schema (no dependencies)
  Task 2: User model (depends on Task 1)
  Task 3: Auth endpoints (depends on Task 2)

Epic 2: Frontend UI
  Task 4: UI components (no dependencies)
  Task 5: Login form (no dependencies)
  Task 6: API integration (depends on Epic 1, Task 3)

Epic 3: Testing
  Task 7: Backend tests (depends on Epic 1, Task 3)
  Task 8: Frontend tests (depends on Epic 2, Task 5)
```

### Step 3: Add Dependencies to Database

**Use the MCP task manager or database directly**:

**Option A: Using MCP tools** (from agent session):
```python
# In agent's tool context
await update_task(
    task_id=6,
    depends_on=[3],  # Task 6 depends on Task 3
    dependency_type='hard'
)
```

**Option B: Using database directly**:
```python
import asyncio
from core.database_connection import DatabaseManager
from uuid import UUID

async def add_dependencies(project_name):
    async with DatabaseManager() as db:
        project = await db.get_project_by_name(project_name)
        project_id = project['id']

        # Add dependencies
        # Format: (task_id, [depends_on_ids], dependency_type)
        dependencies = [
            (2, [1], 'hard'),      # Task 2 depends on Task 1
            (3, [2], 'hard'),      # Task 3 depends on Task 2
            (6, [3], 'hard'),      # Task 6 depends on Task 3
            (7, [3], 'hard'),      # Task 7 depends on Task 3
            (8, [5], 'hard'),      # Task 8 depends on Task 5
        ]

        for task_id, deps, dep_type in dependencies:
            await db.update_task(
                project_id=project_id,
                task_id=task_id,
                depends_on=deps,
                dependency_type=dep_type
            )
            print(f"Task {task_id} now depends on {deps}")

asyncio.run(add_dependencies("your-project-name"))
```

### Step 4: Validate Dependency Graph

**Check for circular dependencies**:

```python
from core.parallel.dependency_resolver import DependencyResolver

async def validate_dependencies(project_name):
    async with DatabaseManager() as db:
        project = await db.get_project_by_name(project_name)
        tasks = await db.list_tasks(project['id'], only_pending=True)

        resolver = DependencyResolver(db_connection=db)
        graph = resolver.resolve(tasks)

        # Check for issues
        if graph.circular_deps:
            print("❌ CIRCULAR DEPENDENCIES DETECTED:")
            for cycle in graph.circular_deps:
                print(f"   {cycle}")
            return False

        if graph.missing_deps:
            print("❌ MISSING DEPENDENCIES:")
            for task_id in graph.missing_deps:
                print(f"   Task {task_id} references non-existent dependency")
            return False

        # Show execution plan
        print("✅ Dependency graph is valid!")
        print(f"\nExecution plan ({len(graph.batches)} batches):")
        for i, batch in enumerate(graph.batches, 1):
            print(f"  Batch {i}: {len(batch)} tasks (parallel)")
            for task_id in batch[:5]:  # Show first 5
                task = next(t for t in tasks if t['id'] == task_id)
                print(f"    - Task {task_id}: {task['description']}")
            if len(batch) > 5:
                print(f"    ... and {len(batch) - 5} more")

        return True

asyncio.run(validate_dependencies("your-project-name"))
```

### Step 5: Test with Low Concurrency

**Start with 2 concurrent agents** to verify everything works:

```bash
cd generations/your-project

# Test parallel execution with 2 agents
python ../../scripts/run_self_enhancement.py --coding --parallel --max-concurrency 2
```

**Monitor the first few batches**:
- ✅ Tasks complete successfully
- ✅ No merge conflicts
- ✅ Git history is clean
- ✅ Tests pass after each batch

**If issues occur**: See [Rollback Instructions](#rollback-instructions)

### Step 6: Scale Up Concurrency

**Once validated, increase concurrency**:

```bash
# Stop current execution (Ctrl+C)

# Restart with higher concurrency
python ../../scripts/run_self_enhancement.py --coding --parallel --max-concurrency 5
```

**Recommended scaling**:
1. Start: 2 agents (testing)
2. After 5 successful batches: 3-4 agents
3. After 10 successful batches: 5+ agents (based on CPU cores)

---

## Adding Dependencies

### Dependency Types

**Hard Dependencies** (blocking):
- Task B cannot start until Task A is complete
- Used for topological sorting
- Most common type

**Soft Dependencies** (non-blocking):
- Task B should run after Task A, but doesn't block
- Informational only
- Useful for preferred ordering

### Common Dependency Patterns

**1. Linear chain** (schema → model → endpoints):
```python
dependencies = [
    (2, [1], 'hard'),  # Model depends on schema
    (3, [2], 'hard'),  # Endpoints depend on model
]
```

**2. Fan-out** (one task enables many):
```python
dependencies = [
    (2, [1], 'hard'),  # Tasks 2, 3, 4 all depend on Task 1
    (3, [1], 'hard'),
    (4, [1], 'hard'),
]
```

**3. Fan-in** (many tasks converge):
```python
dependencies = [
    (5, [2, 3, 4], 'hard'),  # Task 5 depends on Tasks 2, 3, 4
]
```

**4. Cross-epic** (frontend needs backend):
```python
dependencies = [
    # Epic 2 Task 15 depends on Epic 1 Task 8
    (15, [8], 'hard'),
]
```

### Adding Dependencies via Database

**Direct SQL** (if needed):
```sql
-- Connect to database
psql $DATABASE_URL

-- Add dependency
UPDATE tasks
SET depends_on = ARRAY[1, 2],
    dependency_type = 'hard'
WHERE id = 3;

-- View dependencies
SELECT id, description, depends_on, dependency_type
FROM tasks
WHERE depends_on IS NOT NULL;
```

### Adding Dependencies via Python

**Bulk update**:
```python
async def bulk_add_dependencies(project_name, dependency_list):
    """
    Add multiple dependencies at once.

    dependency_list: [(task_id, [deps], type), ...]
    """
    async with DatabaseManager() as db:
        project = await db.get_project_by_name(project_name)

        for task_id, deps, dep_type in dependency_list:
            await db.update_task(
                project_id=project['id'],
                task_id=task_id,
                depends_on=deps,
                dependency_type=dep_type
            )

        print(f"Added {len(dependency_list)} dependencies")

# Example usage
dependencies = [
    (2, [1], 'hard'),
    (3, [2], 'hard'),
    (6, [3], 'hard'),
    # ... etc
]

asyncio.run(bulk_add_dependencies("my-app", dependencies))
```

---

## Configuration Changes

### Update .yokeflow.yaml

Add parallel execution configuration:

```yaml
# .yokeflow.yaml

# Parallel execution settings
parallel_execution:
  enabled: true
  max_concurrency: 5
  merge_strategy: 'regular'  # or 'squash'

# Cost optimization (optional)
cost_optimization:
  enabled: true
  domain_models:
    testing: 'haiku'      # Use Haiku for tests
    deployment: 'haiku'   # Use Haiku for deployment

# Self-learning (optional)
self_learning:
  enabled: true
  max_expertise_lines: 1000
```

### Environment Variables

No changes required to `.env` file. Parallel execution uses existing:
- `DATABASE_URL`
- `CLAUDE_CODE_OAUTH_TOKEN`

### Git Configuration

**Ensure git is configured**:
```bash
cd generations/your-project

# Check git config
git config user.name
git config user.email

# Set if needed
git config user.name "Your Name"
git config user.email "your@email.com"
```

---

## Testing Before Production

### Pre-Production Checklist

Before migrating a production project, test on a copy:

1. **Clone project**:
   ```bash
   cp -r generations/my-app generations/my-app-parallel-test
   cd generations/my-app-parallel-test
   ```

2. **Reset to earlier state** (optional):
   ```bash
   # Reset to after initialization
   python ../../scripts/reset_project.py --project my-app-parallel-test --yes
   ```

3. **Add dependencies** (see Step 3 above)

4. **Run parallel execution** on test copy:
   ```bash
   python ../../scripts/run_self_enhancement.py --coding --parallel --max-concurrency 2
   ```

5. **Verify results**:
   - ✅ All tasks complete successfully
   - ✅ Tests pass
   - ✅ Git history is clean (no conflicts)
   - ✅ Application runs correctly

6. **Compare to sequential** (optional):
   ```bash
   # Run sequential on original
   cd ../my-app
   python ../../scripts/run_self_enhancement.py --coding --max-sessions 10

   # Compare quality, time, cost
   ```

### Testing Scenarios

**Test these scenarios before production use**:

1. **Merge conflicts**:
   - Intentionally create overlapping tasks
   - Verify conflict detection works
   - Practice manual resolution

2. **Circular dependencies**:
   - Intentionally create circular dependency
   - Verify error detection works
   - Practice fixing the cycle

3. **Resource limits**:
   - Test with max concurrency = 10
   - Monitor CPU/RAM usage
   - Reduce if system struggles

4. **Cost tracking**:
   - Monitor costs during execution
   - Verify ModelSelector recommendations
   - Adjust if costs are too high

---

## Rollback Instructions

If parallel execution causes issues, roll back to sequential mode:

### Option 1: Quick Rollback (Keep Progress)

**Just disable parallel mode**:
```bash
# Run sequential execution instead
python scripts/run_self_enhancement.py --coding
# (omit --parallel flag)
```

**Dependencies remain in database** but won't affect sequential execution (it ignores them).

### Option 2: Full Rollback (Remove Dependencies)

**Remove all dependencies from database**:
```python
async def remove_all_dependencies(project_name):
    async with DatabaseManager() as db:
        project = await db.get_project_by_name(project_name)
        tasks = await db.list_tasks(project['id'])

        for task in tasks:
            if task.get('depends_on'):
                await db.update_task(
                    project_id=project['id'],
                    task_id=task['id'],
                    depends_on=None,
                    dependency_type=None
                )

        print(f"Removed dependencies from {len(tasks)} tasks")

asyncio.run(remove_all_dependencies("my-app"))
```

### Option 3: Git Reset (Emergency)

**If merge conflicts are severe**:
```bash
cd generations/my-app

# Find last good commit (before parallel execution)
git log --oneline -20

# Reset to that commit
git reset --hard <commit-hash>

# Clean worktrees
git worktree prune
rm -rf .worktrees/
```

### Option 4: Database Restore

**If database state is corrupted**:
```bash
# Stop PostgreSQL
docker-compose down

# Restore from backup
docker-compose up -d
cat backup.sql | docker exec -i yokeflow-postgres psql -U agent yokeflow

# Verify
python scripts/task_status.py generations/my-app
```

---

## FAQ

### Q: Do I need to add dependencies for all tasks?

**A**: No, only add dependencies where tasks truly block each other. Tasks with no dependencies can run in any order (parallel batch 1).

### Q: What if I'm not sure if two tasks have a dependency?

**A**: When in doubt, **don't add a dependency**. Parallel executor will detect merge conflicts if tasks actually conflict, and you can add the dependency then.

### Q: Can I use parallel execution for only some epics?

**A**: Yes! Add dependencies only within epics you want to parallelize. Epics without dependencies will run independently.

### Q: How do I know if my dependency graph is correct?

**A**: Use the validation script from Step 4. It will detect circular dependencies and show the execution plan.

### Q: Can I change dependencies mid-project?

**A**: Yes! You can add/remove/modify dependencies at any time. Changes take effect on next execution.

### Q: What happens if I have a merge conflict?

**A**: ParallelExecutor detects conflicts automatically, stops execution, and reports the conflict. You resolve manually (see [parallel-execution.md](parallel-execution.md#merge-conflict-resolution)), then resume.

### Q: Will parallel execution cost more money?

**A**: **Same total cost** (same tasks, same tokens), but **higher cost per hour** (more concurrent API calls). However, **total time is much lower** (3-10x faster).

### Q: Can I switch back to sequential execution?

**A**: Yes! Just omit the `--parallel` flag. Dependencies won't affect sequential execution.

### Q: Do I need to delete old worktrees?

**A**: No, they auto-clean after successful merge. But you can manually clean with `git worktree prune` if needed.

### Q: What if a task fails in parallel execution?

**A**: The agent continues with other tasks in the batch. Failed task is marked failed, and dependent tasks are skipped. You can fix and re-run later.

### Q: Can I mix hard and soft dependencies?

**A**: Yes! Use hard for blocking dependencies, soft for preferred ordering.

### Q: How do I visualize my dependency graph?

**A**: Use DependencyResolver's visualization:
```python
from core.parallel.dependency_resolver import DependencyResolver

resolver = DependencyResolver(db)
graph = resolver.resolve(tasks)

# Mermaid diagram
print(resolver.to_mermaid())

# ASCII diagram
print(resolver.to_ascii())
```

### Q: What's the minimum project size for parallel execution?

**A**: Recommended minimum: **50 tasks across 3+ epics**. Below this, setup time > time savings.

### Q: Can I run parallel execution on a project that's already partially complete?

**A**: Yes! Add dependencies to remaining (pending) tasks only. Completed tasks are ignored.

### Q: What if I want different concurrency for different epics?

**A**: Not currently supported. Concurrency is global. Use sequential execution for specific epics if needed.

---

## See Also

- [parallel-execution.md](parallel-execution.md) - Detailed parallel execution documentation
- [configuration.md](configuration.md) - Configuration options
- [README.md](../README.md) - Main documentation
- [developer-guide.md](developer-guide.md) - Technical implementation details
