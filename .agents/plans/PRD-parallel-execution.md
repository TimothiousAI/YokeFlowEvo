# Product Requirements Document: YokeFlow Parallel Execution Upgrade

**Version:** 1.0
**Status:** Draft
**Author:** Claude
**Created:** 2025-01-01
**Last Updated:** 2025-01-01

---

## Executive Summary

This PRD outlines a major upgrade to YokeFlow that introduces parallel task execution, self-learning capabilities, and intelligent orchestration. The upgrade synthesizes proven patterns from three production systems:

1. **YokeFlow** (current) - Robust PostgreSQL schema, MCP protocol, Docker isolation
2. **Automaker** - Git worktree isolation, dependency resolution, lightweight parallelism
3. **Orchestrator-ADWS** - Expertise files, cost optimization, meta-agent orchestration

The result will be a system that can execute independent tasks in parallel (5-10x speedup), learn from experience (self-improving agents), and optimize costs (intelligent model selection).

---

## Problem Statement

### Current Limitations

1. **Sequential Execution Bottleneck**
   - `get_next_task()` returns exactly ONE task
   - Orchestrator runs ONE session at a time per project
   - Single-session lock prevents any parallelism
   - Result: Linear time scaling O(n) where n = number of tasks

2. **No Learning Between Sessions**
   - Agents start fresh each session with no memory
   - Mistakes are repeated across sessions
   - Domain knowledge not accumulated
   - No feedback loop from failures

3. **Fixed Model Selection**
   - Opus for initialization, Sonnet for coding (hardcoded)
   - No cost optimization based on task complexity
   - Expensive operations use same model as trivial ones
   - No budget awareness

4. **No Dependency Tracking**
   - Tasks assumed independent
   - No explicit dependency declarations
   - Implicit ordering only through priority
   - Cannot safely parallelize without dependency knowledge

### Impact

- **Time**: 24 epics × 10 tasks × 60s/task = 4+ hours (sequential)
- **Cost**: ~$50-100 per project with no optimization
- **Quality**: Same errors repeated, no learning curve

---

## Solution Overview

### Architecture Vision

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         YOKEFLOW ENHANCED                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SESSION 0: PLANNING                                                        │
│  ├── Read app_spec.txt                                                      │
│  ├── Generate epics/tasks WITH DEPENDENCIES                                 │
│  ├── Build dependency graph (Kahn's algorithm)                              │
│  └── Compute parallel batches                                               │
│                                                                             │
│  PARALLEL EXECUTION ENGINE                                                  │
│  ├── For each batch (sequential across batches):                            │
│  │   ├── Create git worktrees per epic (isolation)                          │
│  │   ├── Spawn parallel agents (max_concurrency limit)                      │
│  │   ├── Each agent reads domain expertise                                  │
│  │   ├── Execute tasks in isolated worktrees                                │
│  │   └── Merge to main when batch complete                                  │
│  │                                                                          │
│  │   SELF-LEARNING LAYER                                                    │
│  │   ├── Expertise files persist domain knowledge                           │
│  │   ├── Cost tracker informs model selection                               │
│  │   └── Feedback loop: Session N learns from N-1                           │
│  │                                                                          │
│  └── Continue until all batches complete                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Features

| Feature | Description | Source |
|---------|-------------|--------|
| Parallel Batch Execution | Tasks grouped by dependency level, each batch runs in parallel | Automaker |
| Git Worktree Isolation | Each epic gets isolated git branch/worktree | Automaker |
| Dependency Resolution | Kahn's algorithm for topological sorting | Automaker |
| Expertise Files | Persistent domain knowledge that self-updates | ADWS |
| Cost-Aware Model Selection | Choose Opus/Sonnet/Haiku based on task complexity | ADWS |
| Meta-Agent Orchestration | Orchestrator manages sub-agents via tools | ADWS |
| Self-Improvement Loop | ACT → LEARN → REUSE pattern | ADWS |

---

## Detailed Requirements

### 1. Dependency Resolution System

#### 1.1 Database Schema Changes

```sql
-- Task dependencies
ALTER TABLE tasks ADD COLUMN depends_on INTEGER[] DEFAULT '{}';
ALTER TABLE tasks ADD COLUMN dependency_type VARCHAR(20) DEFAULT 'hard';

-- Epic dependencies
ALTER TABLE epics ADD COLUMN depends_on INTEGER[] DEFAULT '{}';

-- Parallel batch tracking
CREATE TABLE parallel_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    batch_number INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    task_ids INTEGER[] NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(project_id, batch_number)
);
```

#### 1.2 Dependency Resolver

- Implement Kahn's algorithm for topological sorting
- Detect circular dependencies and report errors
- Generate parallel batches where each batch contains independent tasks
- Priority-aware ordering within batches
- Support both hard dependencies (must complete) and soft (should complete)

#### 1.3 Session 0 Enhancement

- Prompt agent to declare dependencies when creating tasks
- Parse dependency declarations from agent output
- Store in database for batch computation
- Generate initial parallel batch plan

### 2. Git Worktree Isolation

#### 2.1 Worktree Manager

- Create isolated worktree per epic: `project/.worktrees/epic-{id}/`
- Branch naming: `epic/{id}-{sanitized-name}`
- Automatic branch creation from main
- Support for worktree reuse (resume after failure)

#### 2.2 Merge Strategy

- Merge completed worktrees back to main after batch
- Handle merge conflicts gracefully
- Support squash merge option
- Cleanup worktrees after successful merge

#### 2.3 Database Tracking

```sql
CREATE TABLE worktrees (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    epic_id INTEGER REFERENCES epics(id),
    branch_name VARCHAR(255) NOT NULL,
    worktree_path TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    merged_at TIMESTAMP WITH TIME ZONE,
    merge_commit VARCHAR(40)
);
```

### 3. Parallel Execution Engine

#### 3.1 Concurrency Control

- Configurable `max_concurrency` (default: 3)
- Semaphore-based limiting
- Running agents tracked in memory map
- Graceful cancellation via asyncio.Event

#### 3.2 Batch Execution Flow

```python
async def execute_project():
    batches = compute_parallel_batches(tasks, epics)

    for batch in batches:
        # Create worktrees for epics in this batch
        worktrees = await create_batch_worktrees(batch)

        # Execute tasks in parallel (up to max_concurrency)
        results = await asyncio.gather(*[
            run_task_agent(task, worktrees[task.epic_id])
            for task in batch
        ])

        # Merge successful worktrees
        await merge_completed_worktrees(results)

        # Handle failures before next batch
        await handle_batch_failures(results)
```

#### 3.3 Progress Tracking

- Real-time WebSocket events per agent
- Batch-level progress aggregation
- Task-level status updates
- Duration and cost tracking per batch

### 4. Self-Learning System

#### 4.1 Expertise Files

Structure per domain:
```yaml
domain: database
overview: "PostgreSQL patterns for this project"
core_files:
  - src/db/schema.sql
  - src/db/migrations/
patterns:
  - "Always use UUID for primary keys"
  - "JSONB for flexible metadata"
best_practices:
  - "Run migrations in transactions"
learned_from_failures:
  - issue: "Windows encoding error"
    error: "UnicodeDecodeError"
    solution: "Use encoding='utf-8'"
effective_patterns:
  - "Read → Edit → Test sequence works well"
```

#### 4.2 Learning Loop

1. **Pre-Task**: Load relevant expertise, inject into prompt
2. **During-Task**: Agent validates expertise against actual code
3. **Post-Task**: Extract learnings from session logs
4. **Update**: Merge new learnings into expertise file
5. **Validate**: Periodically verify expertise against codebase

#### 4.3 Constraints

- Maximum 1000 lines per expertise file (forces conciseness)
- Automatic pruning of old entries
- Version history for rollback
- Domain classification: database, api, frontend, testing, security, deployment, general

### 5. Cost Optimization

#### 5.1 Model Selection Logic

```python
def select_model(task):
    complexity = analyze_complexity(task)

    if task.is_critical or complexity == 'high':
        return OPUS

    if complexity == 'low':
        haiku_success = get_success_rate(task.type, HAIKU)
        if haiku_success >= 0.85:
            return HAIKU

    # Budget check
    if budget_remaining < budget_limit * 0.1:
        return HAIKU

    return SONNET  # Default balanced choice
```

#### 5.2 Cost Tracking

```sql
CREATE TABLE agent_costs (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    session_id UUID REFERENCES sessions(id),
    task_id INTEGER REFERENCES tasks(id),
    model VARCHAR(50) NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 6) DEFAULT 0
);
```

#### 5.3 Complexity Analysis

- Keyword-based scoring (security, migration = high; documentation = low)
- Historical cost data for similar tasks
- Success rate tracking per model per task type
- Budget enforcement with automatic downgrade

### 6. Observability & UI

#### 6.1 Swimlane Visualization

- Column per epic
- Row per task within epic
- Real-time status coloring (pending, running, complete, error)
- Dependency arrows between related tasks

#### 6.2 Progress Dashboard

- Batch progress bar
- Running agents list with status
- Cost accumulator
- ETA based on historical data

#### 6.3 API Endpoints

```
POST /api/projects/{id}/parallel/start
GET  /api/projects/{id}/parallel/status
POST /api/projects/{id}/parallel/cancel
GET  /api/projects/{id}/parallel/batches
GET  /api/projects/{id}/costs
GET  /api/projects/{id}/expertise/{domain}
POST /api/projects/{id}/expertise/{domain}/validate
```

---

## Technical Architecture

### New Modules

```
core/
├── dependency_resolver.py    # Kahn's algorithm, batch computation
├── worktree_manager.py       # Git worktree operations
├── parallel_executor.py      # Parallel batch execution engine
├── expertise_manager.py      # Self-learning expertise files
├── model_selector.py         # Cost-aware model selection
└── running_agents.py         # Agent tracking and coordination
```

### Integration Points

1. **Orchestrator Integration**
   - Add `--parallel` flag to CLI
   - Add parallel toggle in Web UI
   - Maintain backward compatibility (sequential as default initially)

2. **Session 0 Enhancement**
   - Prompt modification to request dependencies
   - Dependency parsing from agent output
   - Initial batch computation

3. **Agent Loop Modification**
   - Support worktree as working directory
   - Expertise injection into prompt
   - Learning extraction from session logs

4. **Database Abstraction**
   - New methods for batch CRUD
   - Worktree tracking
   - Cost recording

---

## Migration Strategy

### Phase 1: Non-Breaking Additions
- Add new tables (parallel_batches, worktrees, agent_costs, expertise_files)
- Add new modules alongside existing code
- Add new API endpoints
- No changes to existing behavior

### Phase 2: Optional Parallel Mode
- Add `enable_parallel` configuration option
- When enabled, use new parallel executor
- When disabled, existing sequential behavior
- Extensive testing in parallel mode

### Phase 3: Default Parallel
- Make parallel mode default
- Keep sequential as fallback option
- Deprecation warnings for old patterns
- Migration documentation

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Execution Time | 4+ hours | <1 hour | End-to-end project completion |
| Cost per Project | $50-100 | $30-60 | API cost tracking |
| First-Pass Success | ~70% | >85% | Tasks completed without retry |
| Learning Retention | 0% | 80%+ | Expertise file utilization |
| Parallel Speedup | 1x | 3-5x | Batch vs sequential timing |

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Git worktree merge conflicts | Medium | Medium | Conflict detection, manual resolution workflow |
| Database concurrency issues | Low | High | PostgreSQL MVCC, optimistic locking |
| Resource exhaustion | Medium | Medium | max_concurrency limits, monitoring |
| Expertise file noise | Medium | Low | 1000-line cap, periodic validation |
| Cost explosion | Low | High | Budget limits, automatic downgrade |
| Circular dependencies | Low | Medium | Detection in resolver, error reporting |

---

## Dependencies

### External
- Git 2.20+ (worktree support)
- PostgreSQL 14+ (current requirement)
- Python 3.11+ (current requirement)

### Internal
- Existing MCP task-manager
- Existing WebSocket infrastructure
- Existing session logging

---

## Epics Overview

| Epic | Name | Priority | Phase | Dependencies |
|------|------|----------|-------|--------------|
| 00 | Core Refinements | P0 | 0 | None |
| 01 | Foundation Infrastructure | P0 | 1 | None |
| 02 | Dependency Resolution | P0 | 1 | Epic 01 |
| 03 | Git Worktree Isolation | P0 | 1 | Epic 01 |
| 04 | Parallel Executor | P0 | 1 | Epics 01, 02, 03 |
| 05 | Self-Learning System | P1 | 2 | Epic 01 |
| 06 | Cost Optimization | P1 | 2 | Epics 01, 05 |
| 07 | Observability & UI | P1 | 2 | Epics 01, 04 |
| 08 | Testing & Documentation | P1 | 3 | Epics 01-07 |

### Epic Summaries

0. **Epic 00: Core Refinements** - .gitignore handling, post-session validation, export documentation (quick wins from real-world usage)
1. **Epic 01: Foundation Infrastructure** - Database schema, configuration, module structure
2. **Epic 02: Dependency Resolution** - Kahn's algorithm, dependency parsing, batch computation
3. **Epic 03: Git Worktree Isolation** - WorktreeManager, merge handling, conflict resolution
4. **Epic 04: Parallel Executor** - Core execution engine, concurrency control, orchestrator integration
5. **Epic 05: Self-Learning System** - ExpertiseManager, domain knowledge, learning loop
6. **Epic 06: Cost Optimization** - ModelSelector, cost tracking, budget management
7. **Epic 07: Observability & UI** - Swimlane visualization, WebSocket events, dashboards
8. **Epic 08: Testing & Documentation** - Unit tests, integration tests, migration guide

---

## Timeline

| Phase | Epics | Deliverables |
|-------|-------|--------------|
| Phase 0: Quick Wins | 00 | .gitignore fixes, validation, export docs (can be done immediately) |
| Phase 1: Core Infrastructure | 01, 02, 03, 04 | Schema, dependency resolution, worktrees, parallel executor |
| Phase 2: Intelligence Layer | 05, 06 | Self-learning, cost optimization |
| Phase 3: User Experience | 07 | Swimlane UI, dashboards, real-time updates |
| Phase 4: Quality Assurance | 08 | Tests, benchmarks, documentation |

---

## Open Questions

1. **Worktree vs Docker**: Should we use worktrees exclusively or hybrid approach?
2. **Dependency Declaration**: How to prompt agent to declare dependencies reliably?
3. **Expertise Seeding**: Should we pre-populate expertise from YokeFlow's own patterns?
4. **Budget Enforcement**: Hard limit (stop execution) or soft (warnings only)?
5. **Merge Strategy**: Always squash or preserve commit history?

---

## References

### Source Repositories

1. **YokeFlow** (current)
   - Location: `C:\Users\Timo\Projects\OpenSource\YokeFlow`
   - Key files: `core/orchestrator.py`, `core/database.py`, `schema/postgresql/schema.sql`

2. **Automaker**
   - Location: `C:\Users\Timo\Projects\OpenSource\automaker`
   - Key patterns: Git worktrees, dependency resolution, concurrency control
   - Key files: `auto-mode-service.ts`, `dependency-resolver.ts`

3. **Orchestrator-ADWS**
   - Location: `C:\Users\Timo\Projects\OpenSource\orchestrator-agent-with-adws`
   - Key patterns: Expertise files, meta-agent orchestration, cost tracking
   - Key files: `experts/*/expertise.yaml`, `agent_manager.py`, `orchestrator_service.py`

### Design Documents

- This PRD: `.agents/plans/PRD-parallel-execution.md`
- Epics: `.agents/plans/epics/`

---

## Appendix A: Database Schema Changes

See `schema/postgresql/parallel_execution.sql` (to be created)

## Appendix B: API Specification

See `docs/api/parallel-execution.md` (to be created)

## Appendix C: Configuration Options

```yaml
# .yokeflow.yaml additions
parallel:
  enabled: true
  max_concurrency: 3
  strategy: "by_epic"  # or "by_task", "smart"

learning:
  enabled: true
  expertise_max_lines: 1000
  self_improve_interval: "daily"

cost:
  budget_limit_usd: 100
  optimization_enabled: true
  default_model: "sonnet"
```
