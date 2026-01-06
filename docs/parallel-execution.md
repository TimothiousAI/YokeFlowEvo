# Parallel Execution Guide

**YokeFlow v1.3.0+** supports parallel execution where multiple AI agents work on different tasks simultaneously, dramatically reducing development time for large projects.

## Table of Contents

- [Overview](#overview)
- [Configuration Options](#configuration-options)
- [Dependency Declaration](#dependency-declaration)
- [Performance Tuning](#performance-tuning)
- [Worktree Management](#worktree-management)
- [Merge Conflict Resolution](#merge-conflict-resolution)
- [Best Practices](#best-practices)
- [Advanced Topics](#advanced-topics)
- [Troubleshooting](#troubleshooting)

---

## Overview

### How Parallel Execution Works

1. **Dependency Analysis**: DependencyResolver analyzes all tasks and computes execution batches using topological sorting (Kahn's algorithm)
2. **Worktree Creation**: WorktreeManager creates isolated git worktrees, one per epic
3. **Concurrent Execution**: ParallelExecutor runs multiple agents simultaneously within concurrency limits
4. **Automatic Merging**: Completed worktrees are automatically merged back to the main branch
5. **State Tracking**: PostgreSQL database tracks all execution state and progress

### Architecture Components

```
┌─────────────────────────────────────────┐
│         DependencyResolver              │
│  - Analyzes task dependencies           │
│  - Computes parallel batches            │
│  - Detects circular dependencies        │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│         WorktreeManager                 │
│  - Creates isolated worktrees           │
│  - Manages git branches                 │
│  - Handles merges and conflicts         │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│         ParallelExecutor                │
│  - Orchestrates concurrent agents       │
│  - Controls concurrency with semaphore  │
│  - Tracks costs and performance         │
│  - Manages cancellation                 │
└─────────────────────────────────────────┘
```

---

## Configuration Options

### CLI Flags

| Flag | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `--parallel` | boolean | `false` | - | Enable parallel execution (opt-in) |
| `--max-concurrency` | integer | `3` | `1-10` | Number of concurrent agents |
| `--merge-strategy` | string | `regular` | `regular`, `squash` | Git merge strategy |

### Usage Examples

```bash
# Basic parallel execution (3 concurrent agents)
python scripts/run_self_enhancement.py --coding --parallel

# High concurrency (10 agents)
python scripts/run_self_enhancement.py --coding --parallel --max-concurrency 10

# Conservative concurrency (1 agent at a time, still uses worktrees)
python scripts/run_self_enhancement.py --coding --parallel --max-concurrency 1

# Squash merge for cleaner git history
python scripts/run_self_enhancement.py --coding --parallel --merge-strategy squash

# Combine with other flags
python scripts/run_self_enhancement.py --all --parallel --max-concurrency 5
```

### Programmatic Configuration

```python
from core.parallel.parallel_executor import ParallelExecutor

executor = ParallelExecutor(
    project_path="generations/my_project",
    project_id="uuid-here",
    max_concurrency=5,
    progress_callback=my_callback,
    db_connection=db
)

# Run parallel execution
results = await executor.execute()
```

### Environment Variables

None required. Parallel execution uses the same `DATABASE_URL` and `CLAUDE_CODE_OAUTH_TOKEN` as sequential mode.

---

## Dependency Declaration

### Dependency Types

**Hard Dependencies (blocking):**
- Task B **cannot start** until Task A is complete
- Used for topological sorting
- Determines batch execution order

**Soft Dependencies (non-blocking):**
- Task B **should** run after Task A, but doesn't block execution
- Informational only
- Not used for batch computation
- Useful for documentation or preferred ordering

### Declaring Dependencies

Dependencies are stored in the PostgreSQL database:

```python
# Via MCP tools (from agent session)
await create_task(
    epic_id=1,
    description="Implement user authentication",
    action="Create auth endpoints...",
    depends_on=[task_123, task_124],  # List of task IDs
    dependency_type='hard'             # or 'soft'
)

# Via database directly
async with DatabaseManager() as db:
    task_id = await db.create_task(
        project_id=project_uuid,
        epic_id=1,
        description="Build user dashboard",
        action="Create React components...",
        priority=10,
        depends_on=[456, 457],  # Array of task IDs
        dependency_type='hard'
    )
```

### Dependency Graph Example

```python
# Epic 1: Backend Infrastructure
Task 1: Database schema (no dependencies)
Task 2: Database models (depends_on=[1])
Task 3: API endpoints (depends_on=[2])

# Epic 2: Authentication
Task 4: Auth models (depends_on=[2])  # Depends on Epic 1, Task 2
Task 5: Auth endpoints (depends_on=[3, 4])

# Epic 3: Frontend
Task 6: UI components (no dependencies)
Task 7: API client (depends_on=[3])

# Execution Batches:
Batch 1: [1, 6]        # Parallel - no dependencies
Batch 2: [2]           # Depends on 1
Batch 3: [3, 4]        # Parallel - both depend only on Batch 2
Batch 4: [5, 7]        # Parallel - both depend on Batch 3
```

### Circular Dependency Detection

DependencyResolver automatically detects circular dependencies:

```python
# Example circular dependency
Task A depends_on=[Task B]
Task B depends_on=[Task C]
Task C depends_on=[Task A]  # ❌ Circular!

# Error output:
# "Circular dependencies detected: [(A, B, C, A)]"
```

**How to fix:**
1. Review the dependency chain
2. Break the cycle by removing one dependency
3. Use soft dependencies if tasks reference each other but don't block
4. Restructure tasks to remove the circular reference

---

## Performance Tuning

### Choosing Concurrency Level

**Factors to consider:**

1. **CPU Cores**: Set `--max-concurrency` to number of CPU cores or less
2. **Memory**: Each agent uses ~500MB-1GB RAM
3. **Network**: Higher concurrency = more concurrent API calls to Claude
4. **Cost**: More concurrent agents = higher cost per hour (but lower total time)

**Recommendations:**

| System | CPU Cores | RAM | Recommended Concurrency |
|--------|-----------|-----|-------------------------|
| Laptop | 4-8 | 8-16 GB | 2-3 agents |
| Desktop | 8-16 | 16-32 GB | 3-5 agents |
| Workstation | 16+ | 32+ GB | 5-10 agents |
| Server | 32+ | 64+ GB | 10 agents (max) |

### Cost vs. Speed Trade-offs

**Sequential execution:**
- Cost: Lower cost per hour
- Speed: Slower total time
- Best for: Small projects, limited resources

**Parallel execution (3 agents):**
- Cost: 3x cost per hour
- Speed: ~3x faster (if tasks are independent)
- Best for: Medium-large projects, multiple CPU cores

**Parallel execution (10 agents):**
- Cost: 10x cost per hour
- Speed: ~5-7x faster (diminishing returns due to dependencies)
- Best for: Large projects, powerful hardware, time-critical development

### When Parallelism Helps Most

**High parallelism benefit:**
- ✅ Many independent tasks (different files, different features)
- ✅ Few dependencies between tasks
- ✅ Multiple epics that don't interact
- ✅ Frontend + Backend tasks in separate epics

**Low parallelism benefit:**
- ⚠️ Sequential tasks (each depends on previous)
- ⚠️ Highly coupled features (everything touches same files)
- ⚠️ Small projects (<20 tasks)

### Monitoring Performance

```python
# ParallelExecutor tracks metrics
executor = ParallelExecutor(...)
results = await executor.execute()

for result in results:
    print(f"Task {result.task_id}: {result.duration:.1f}s, ${result.cost:.4f}")
```

---

## Worktree Management

### How Worktrees Work

**One worktree per epic** (not per task):
- Reduces git overhead
- Allows multiple tasks in same epic to share changes
- Each worktree has its own branch

**Worktree structure:**
```
project/
├── .git/                 # Main git directory
├── .worktrees/           # Worktrees directory
│   ├── epic-1-backend/   # Worktree for Epic 1
│   │   └── [isolated copy of repo on branch epic-1-backend]
│   ├── epic-2-frontend/  # Worktree for Epic 2
│   │   └── [isolated copy of repo on branch epic-2-frontend]
│   └── epic-3-auth/      # Worktree for Epic 3
└── [main repository]     # Main branch
```

### Worktree Lifecycle

1. **Creation**: WorktreeManager creates worktree before executing tasks in epic
   ```python
   worktree_info = await worktree_manager.create_worktree(
       epic_id=42,
       epic_name="User Authentication"
   )
   # Creates: .worktrees/epic-42-user-authentication/
   # Branch: epic-42-user-authentication
   ```

2. **Execution**: Agent works in isolated worktree
   - All changes stay in worktree
   - No conflicts with other agents
   - Can commit freely

3. **Merging**: After all tasks complete, worktree merges back to main
   ```python
   merge_result = await worktree_manager.merge_worktree(epic_id=42)
   # Merges branch epic-42-user-authentication into main
   ```

4. **Cleanup**: Worktree is removed after successful merge
   ```python
   await worktree_manager.cleanup_worktree(epic_id=42)
   # Removes .worktrees/epic-42-user-authentication/
   ```

### Branch Naming

WorktreeManager generates Windows-safe branch names:

```python
# Reserved Windows names are handled
epic_name = "CON"  # Reserved on Windows
branch = "epic-42-con-epic"  # Sanitized

# Special characters removed
epic_name = "API: User & Admin"
branch = "epic-42-api-user-admin"

# Length limited to 200 chars (Windows path limits)
epic_name = "Very long epic name that exceeds limits..."
branch = "epic-42-very-long-epic-name-that-exc..."  # Truncated
```

### Manual Worktree Management

```bash
# List all worktrees
git worktree list

# Check worktree status
cd .worktrees/epic-42-feature-name
git status
git log

# Manually remove worktree (if needed)
git worktree remove .worktrees/epic-42-feature-name

# Prune deleted worktrees
git worktree prune
```

### Recovery After Crashes

WorktreeManager can recover state after crashes:

```python
from core.parallel.worktree_manager import WorktreeManager

manager = WorktreeManager(
    project_path="generations/my_project",
    project_id=project_uuid,
    db=db_connection
)

# Recover state from both git and database
recovery_result = await manager.recover_state()
print(f"Recovered {recovery_result['recovered_count']} worktrees")
print(f"Cleaned {recovery_result['cleaned_count']} stale entries")
```

---

## Merge Conflict Resolution

### Automatic Conflict Detection

ParallelExecutor automatically detects merge conflicts:

```python
# During merge
try:
    merge_result = await worktree_manager.merge_worktree(epic_id=42)
except WorktreeConflictError as e:
    print(f"Merge conflict detected: {e}")
    # Conflict details available in exception
```

### Resolving Conflicts Manually

1. **Identify the conflict:**
   ```bash
   git worktree list
   # Find worktree path: .worktrees/epic-42-feature-name
   ```

2. **Navigate to worktree:**
   ```bash
   cd .worktrees/epic-42-feature-name
   git status
   # Shows conflicted files
   ```

3. **Resolve conflicts:**
   ```bash
   # Edit conflicted files
   vim path/to/conflicted/file.py

   # Mark as resolved
   git add path/to/conflicted/file.py

   # Commit resolution
   git commit -m "Resolve merge conflicts in feature implementation"
   ```

4. **Retry merge:**
   ```bash
   # Return to main repository
   cd ../..

   # Retry parallel execution (will retry merge)
   python scripts/run_self_enhancement.py --coding --parallel
   ```

### Preventing Conflicts

**Best practices:**

1. **Design independent epics**: Minimize overlap between epic scopes
2. **Use soft dependencies**: Document relationships without blocking
3. **Review dependency graph**: Visualize potential conflicts before execution
4. **Test with low concurrency first**: Start with `--max-concurrency 2` to identify issues

**Common conflict scenarios:**

- Two epics modify the same file
- Shared configuration files (package.json, .env.example)
- Database migrations in different epics
- Import statements that reference each other

**Solutions:**

- Structure epics to minimize file overlap
- Use different directories for different epics
- Create a "foundation" epic that runs first
- Declare dependencies between epics that touch same files

---

## Best Practices

### 1. Dependency Declaration

✅ **DO:**
- Declare all blocking dependencies explicitly
- Use hard dependencies for actual blockers
- Use soft dependencies for documentation
- Review dependency graph before execution

❌ **DON'T:**
- Create circular dependencies
- Over-declare dependencies (adds unnecessary sequencing)
- Forget cross-epic dependencies

### 2. Epic Structure

✅ **DO:**
- Group related tasks in same epic
- Design epics to be independent
- Keep epics focused on single feature/area
- Limit epic scope to reduce merge conflicts

❌ **DON'T:**
- Create giant epics with 50+ tasks
- Mix unrelated tasks in same epic
- Create epics that touch every file in the project

### 3. Concurrency Settings

✅ **DO:**
- Start with `--max-concurrency 2` for testing
- Scale up based on system resources
- Monitor CPU/memory usage
- Adjust based on project dependency structure

❌ **DON'T:**
- Max out concurrency on first run
- Ignore system resource limits
- Use high concurrency for small projects

### 4. Testing Before Production

✅ **DO:**
- Test parallel execution on small epics first
- Verify dependency graph is correct
- Check for merge conflicts with 2-3 agents
- Monitor costs and performance

❌ **DON'T:**
- Jump straight to 10 concurrent agents
- Skip dependency validation
- Ignore conflict warnings

### 5. Monitoring and Debugging

✅ **DO:**
- Use progress callbacks for real-time updates
- Check logs for each agent
- Review git history after merges
- Verify all tests pass after parallel execution

❌ **DON'T:**
- Run parallel execution and walk away
- Ignore error messages
- Skip verification after completion

---

## Advanced Topics

### Custom Progress Callbacks

```python
async def my_progress_callback(event):
    """Handle parallel execution events."""
    event_type = event.get('type')

    if event_type == 'batch_started':
        batch_num = event.get('batch_number')
        task_count = event.get('task_count')
        print(f"Batch {batch_num} started: {task_count} tasks")

    elif event_type == 'task_started':
        task_id = event.get('task_id')
        epic_id = event.get('epic_id')
        print(f"Task {task_id} (Epic {epic_id}) started")

    elif event_type == 'task_complete':
        task_id = event.get('task_id')
        duration = event.get('duration')
        cost = event.get('cost')
        print(f"Task {task_id} complete: {duration:.1f}s, ${cost:.4f}")

    elif event_type == 'batch_complete':
        batch_num = event.get('batch_number')
        print(f"Batch {batch_num} complete")

# Use callback
orchestrator = AgentOrchestrator(verbose=True)
session = await orchestrator.start_coding_sessions(
    project_id=project_uuid,
    coding_model='sonnet',
    parallel=True,
    max_concurrency=5,
    progress_callback=my_progress_callback
)
```

### Dependency Visualization

```python
from core.parallel.dependency_resolver import DependencyResolver

resolver = DependencyResolver(db_connection=db)
tasks = await db.list_tasks(project_uuid)

# Resolve dependencies
graph = resolver.resolve(tasks)

# Generate Mermaid diagram
mermaid_diagram = resolver.to_mermaid()
print(mermaid_diagram)

# Generate ASCII visualization
ascii_viz = resolver.to_ascii()
print(ascii_viz)

# Filter by epic
mermaid_epic_1 = resolver.to_mermaid(epic_filter=1)

# Filter by batch
mermaid_batch_0 = resolver.to_mermaid(batch_filter=0)
```

### Database Queries

```python
# Get parallel execution batches
batches = await db.get_parallel_batches(project_uuid)
for batch in batches:
    print(f"Batch {batch['batch_number']}: {len(batch['tasks'])} tasks")

# Get worktree state
worktrees = await db.list_worktrees(project_uuid)
for wt in worktrees:
    print(f"Epic {wt['epic_id']}: {wt['status']} ({wt['branch_name']})")

# Track costs across parallel execution
session = await db.get_session(session_id)
print(f"Total cost: ${session['total_cost']:.4f}")
print(f"Total duration: {session['duration_seconds']}s")
```

---

## Troubleshooting

### Issue: Circular Dependencies

**Symptoms:**
- Error: "Circular dependencies detected: [...]"
- Some tasks never execute

**Solution:**
1. Review dependency graph: `resolver.to_mermaid()`
2. Identify the cycle in error message
3. Remove one dependency from the cycle
4. Or use soft dependencies if relationship isn't blocking

### Issue: Merge Conflicts

**Symptoms:**
- Error: "WorktreeConflictError: Merge conflict in epic X"
- Git shows CONFLICT markers

**Solution:**
1. Navigate to worktree: `cd .worktrees/epic-X-name/`
2. Check conflicts: `git status`
3. Resolve conflicts manually
4. Commit resolution: `git add . && git commit`
5. Retry parallel execution

### Issue: Worktree Cleanup Fails

**Symptoms:**
- Error: "Cannot remove worktree: directory in use"
- Stale worktrees after crashes

**Solution:**
```bash
# Force remove worktree
git worktree remove --force .worktrees/epic-X-name

# Prune all stale worktrees
git worktree prune

# Manual cleanup
rm -rf .worktrees/epic-X-name
git worktree prune
```

### Issue: Performance Degradation

**Symptoms:**
- High CPU usage
- Agents taking longer than expected
- System becomes unresponsive

**Solution:**
1. Reduce `--max-concurrency` to 1-2
2. Check Docker resources: `docker stats`
3. Increase Docker memory limit
4. Close other applications
5. Consider sequential execution for resource-constrained systems

### Issue: Database Lock Errors

**Symptoms:**
- Error: "Database is locked"
- Timeout errors during parallel execution

**Solution:**
- YokeFlow uses PostgreSQL (not SQLite), which handles concurrent writes
- If you see lock errors, check PostgreSQL connection pool settings
- Increase `max_connections` in PostgreSQL config if needed

### Issue: Cost Overruns

**Symptoms:**
- Higher costs than expected
- Budget limits exceeded

**Solution:**
1. Reduce `--max-concurrency` to lower concurrent API usage
2. Use ModelSelector to assign cheaper models (Haiku) to simple tasks
3. Monitor costs in real-time via progress callbacks
4. Set budget limits in configuration (coming in v1.4.0)

---

## See Also

- [README.md](../README.md) - Main documentation and quick start
- [developer-guide.md](developer-guide.md) - Technical implementation details
- [configuration.md](configuration.md) - General configuration options
- [review-system.md](review-system.md) - Quality review system documentation
