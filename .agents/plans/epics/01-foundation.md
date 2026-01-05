# Epic 01: Foundation Infrastructure

**Priority:** P0 (Critical Path)
**Estimated Duration:** 3-4 days
**Dependencies:** None
**Phase:** 1

---

## Overview

Establish the database schema and core infrastructure required for parallel execution. This epic creates the foundation that all other epics depend on.

---

## Tasks

### 1.1 Database Schema Extensions

**Description:** Add new tables and columns to support parallel execution, worktrees, cost tracking, and expertise storage.

**Files to Create/Modify:**
- `schema/postgresql/parallel_execution.sql` (new)
- `schema/postgresql/schema.sql` (modify - add to existing)

**Schema Changes:**

```sql
-- Task dependencies
ALTER TABLE tasks ADD COLUMN depends_on INTEGER[] DEFAULT '{}';
ALTER TABLE tasks ADD COLUMN dependency_type VARCHAR(20) DEFAULT 'hard';

-- Epic dependencies
ALTER TABLE epics ADD COLUMN depends_on INTEGER[] DEFAULT '{}';

-- Parallel batch tracking
CREATE TABLE parallel_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    batch_number INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    task_ids INTEGER[] NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(project_id, batch_number)
);

-- Git worktree tracking
CREATE TABLE worktrees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    epic_id INTEGER REFERENCES epics(id) ON DELETE CASCADE,
    branch_name VARCHAR(255) NOT NULL,
    worktree_path TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    merged_at TIMESTAMP WITH TIME ZONE,
    merge_commit VARCHAR(40)
);

-- Agent cost tracking
CREATE TABLE agent_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id),
    task_id INTEGER REFERENCES tasks(id),
    model VARCHAR(50) NOT NULL,
    operation_type VARCHAR(50),
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 6) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Domain expertise storage
CREATE TABLE expertise_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    domain VARCHAR(100) NOT NULL,
    content JSONB NOT NULL,
    version INTEGER DEFAULT 1,
    line_count INTEGER DEFAULT 0,
    validated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(project_id, domain)
);

-- Expertise learning history
CREATE TABLE expertise_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expertise_id UUID REFERENCES expertise_files(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id),
    change_type VARCHAR(50) NOT NULL,
    change_summary TEXT NOT NULL,
    diff JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Acceptance Criteria:**
- [ ] All new tables created successfully
- [ ] Foreign key constraints work correctly
- [ ] Indexes added for common query patterns
- [ ] Existing data unaffected

---

### 1.2 Database Views for Parallel Progress

**Description:** Create views for querying parallel execution progress.

**SQL:**

```sql
-- Cost aggregation view
CREATE VIEW v_project_costs AS
SELECT
    project_id,
    model,
    operation_type,
    COUNT(*) as operation_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_usd) as total_cost_usd,
    AVG(cost_usd) as avg_cost_per_operation
FROM agent_costs
GROUP BY project_id, model, operation_type;

-- Parallel progress view
CREATE VIEW v_parallel_progress AS
SELECT
    pb.project_id,
    pb.batch_number,
    pb.status as batch_status,
    array_length(pb.task_ids, 1) as total_tasks,
    COUNT(t.id) FILTER (WHERE t.done = true) as completed_tasks,
    pb.started_at,
    pb.completed_at,
    EXTRACT(EPOCH FROM (COALESCE(pb.completed_at, NOW()) - pb.started_at)) as duration_seconds
FROM parallel_batches pb
LEFT JOIN tasks t ON t.id = ANY(pb.task_ids)
GROUP BY pb.id;

-- Worktree status view
CREATE VIEW v_worktree_status AS
SELECT
    w.project_id,
    w.epic_id,
    e.name as epic_name,
    w.branch_name,
    w.status,
    w.created_at,
    w.merged_at,
    COUNT(t.id) FILTER (WHERE t.done = true) as completed_tasks,
    COUNT(t.id) as total_tasks
FROM worktrees w
JOIN epics e ON w.epic_id = e.id
LEFT JOIN tasks t ON t.epic_id = w.epic_id
GROUP BY w.id, e.id;
```

**Acceptance Criteria:**
- [ ] Views return correct aggregations
- [ ] Performance acceptable for large projects

---

### 1.3 Database Abstraction Layer Updates

**Description:** Add methods to `core/database.py` for new tables.

**New Methods:**

```python
# Parallel batches
async def create_parallel_batch(project_id, batch_number, task_ids) -> Dict
async def get_parallel_batch(batch_id) -> Optional[Dict]
async def list_parallel_batches(project_id) -> List[Dict]
async def update_batch_status(batch_id, status) -> None
async def start_batch(batch_id) -> None
async def complete_batch(batch_id) -> None

# Worktrees
async def create_worktree(project_id, epic_id, branch_name, worktree_path) -> Dict
async def get_worktree(worktree_id) -> Optional[Dict]
async def get_worktree_by_epic(project_id, epic_id) -> Optional[Dict]
async def list_worktrees(project_id) -> List[Dict]
async def update_worktree_status(worktree_id, status) -> None
async def mark_worktree_merged(worktree_id, merge_commit) -> None

# Cost tracking
async def record_agent_cost(project_id, session_id, task_id, model, input_tokens, output_tokens) -> Dict
async def get_project_costs(project_id) -> Dict
async def get_cost_by_model(project_id) -> Dict
async def get_cost_by_task_type(project_id) -> Dict

# Expertise
async def get_expertise(project_id, domain) -> Optional[Dict]
async def save_expertise(project_id, domain, content) -> Dict
async def list_expertise_domains(project_id) -> List[str]
async def record_expertise_update(expertise_id, session_id, change_type, summary, diff) -> Dict

# Dependencies
async def get_task_dependencies(task_id) -> List[int]
async def set_task_dependencies(task_id, depends_on) -> None
async def get_tasks_with_dependencies(project_id) -> List[Dict]
```

**Acceptance Criteria:**
- [ ] All CRUD operations work correctly
- [ ] Proper error handling
- [ ] Async operations complete without blocking
- [ ] Unit tests pass

---

### 1.4 Configuration Schema Updates

**Description:** Add configuration options for parallel execution.

**File:** `.yokeflow.yaml` schema update

```yaml
# New configuration options
parallel:
  enabled: true
  max_concurrency: 3
  strategy: "by_epic"  # "by_epic", "by_task", "smart"
  worktree_dir: ".worktrees"
  merge_strategy: "merge"  # "merge", "squash"

learning:
  enabled: true
  expertise_max_lines: 1000
  self_improve_interval: "daily"  # "never", "session", "daily"
  domains:
    - database
    - api
    - frontend
    - testing
    - security
    - deployment
    - general

cost:
  enabled: true
  budget_limit_usd: null  # null = unlimited
  optimization_enabled: true
  default_model: "sonnet"
  model_overrides:
    critical_tasks: "opus"
    documentation: "haiku"
```

**Files to Modify:**
- `core/config.py` - Add new config classes
- `core/config_schema.py` - Add validation (if exists)

**Acceptance Criteria:**
- [ ] Config loads correctly with defaults
- [ ] Validation errors for invalid values
- [ ] Backward compatible (works without new options)

---

### 1.5 Core Module Structure

**Description:** Create the module structure for new components.

**Files to Create:**

```
core/
├── parallel/
│   ├── __init__.py
│   ├── dependency_resolver.py   # Epic 02
│   ├── worktree_manager.py      # Epic 03
│   ├── parallel_executor.py     # Epic 04
│   └── running_agents.py        # Epic 04
├── learning/
│   ├── __init__.py
│   ├── expertise_manager.py     # Epic 05
│   └── model_selector.py        # Epic 06
```

**Initial `__init__.py` Content:**

```python
# core/parallel/__init__.py
"""
Parallel execution components for YokeFlow.

This module provides:
- DependencyResolver: Compute task execution order
- WorktreeManager: Git worktree isolation
- ParallelExecutor: Concurrent task execution
"""

from .dependency_resolver import DependencyResolver
from .worktree_manager import WorktreeManager
from .parallel_executor import ParallelExecutor

__all__ = ['DependencyResolver', 'WorktreeManager', 'ParallelExecutor']
```

**Acceptance Criteria:**
- [ ] Directory structure created
- [ ] Imports work correctly
- [ ] No circular dependencies

---

## Dependencies

- None (this is the foundation epic)

## Dependents

- Epic 02: Dependency Resolution (needs schema)
- Epic 03: Worktree Manager (needs schema)
- Epic 04: Parallel Executor (needs schema and config)
- Epic 05: Self-Learning (needs schema)
- Epic 06: Cost Optimization (needs schema)

---

## Testing Requirements

1. Schema migration tests
2. Database method unit tests
3. Configuration loading tests
4. Import and module structure tests

---

## Rollback Plan

1. Drop new tables (no data loss for existing tables)
2. Remove new columns via ALTER TABLE DROP COLUMN
3. Delete new module directories
4. Revert config changes

---

---

### 1.6 MCP Transaction Utilities (CRITICAL)

**Description:** Add transaction wrapper utilities to support concurrent MCP operations.

**Background (Research Finding):** The MCP task-manager has NO transaction isolation - concurrent agents can cause race conditions on task/epic status updates. This MUST be addressed before enabling parallel execution.

**File:** `mcp-task-manager/src/database.ts`

**Required Changes:**

```typescript
// Add transaction wrapper
async transaction<T>(fn: (client: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
        await client.query('BEGIN');
        const result = await fn(client);
        await client.query('COMMIT');
        return result;
    } catch (e) {
        await client.query('ROLLBACK');
        throw e;
    } finally {
        client.release();
    }
}

// Add row-level locking for task updates
async updateTaskStatusSafe(taskId: string, done: boolean): Promise<Task | null> {
    return this.transaction(async (client) => {
        // Lock the row first
        const locked = await client.query(
            'SELECT * FROM tasks WHERE id = $1 AND project_id = $2 FOR UPDATE',
            [taskId, this.projectId]
        );

        if (locked.rows.length === 0) return null;

        // Validate tests if marking complete
        if (done) {
            const tests = await client.query(
                'SELECT * FROM tests WHERE task_id = $1 AND passed = false',
                [taskId]
            );
            if (tests.rows.length > 0) {
                throw new Error('Cannot complete task: failing tests');
            }
        }

        // Update with lock held
        await client.query(
            'UPDATE tasks SET done = $1, completed_at = $2 WHERE id = $3',
            [done, done ? new Date() : null, taskId]
        );

        return locked.rows[0];
    });
}
```

**Acceptance Criteria:**
- [ ] Transaction wrapper implemented
- [ ] Row-level locking with FOR UPDATE
- [ ] Epic completion check is atomic
- [ ] Concurrent updates don't cause race conditions

---

## Notes

- All schema changes should be idempotent (can run multiple times)
- Consider adding migration version tracking
- Keep existing schema.sql intact, add parallel_execution.sql separately
- **CRITICAL**: Task 1.6 (MCP Transaction Utilities) is a prerequisite for Epic 04 (Parallel Executor) - without it, concurrent agents will cause data corruption
