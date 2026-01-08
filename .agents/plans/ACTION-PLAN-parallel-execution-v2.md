# Action Plan: Parallel Execution System v2

## Executive Summary

This plan addresses 4 critical gaps between the PRD vision and current implementation:

1. **Parallel execution is manual** (should be automatic after initialization)
2. **Expertise storage pattern mismatch** (DB-only vs file-based like ADWS)
3. **Generated projects lack skills/expertise** (should bootstrap Claude SDK structure)
4. **No visual execution management** (need kanban/swimlane UI like Automaker)

---

## Gap Analysis

### Current State vs PRD Requirements

| Aspect | PRD Phase 3 Requirement | Current Implementation |
|--------|------------------------|------------------------|
| Parallel Mode | DEFAULT mode after init | Manual `/parallel/start` trigger |
| Execution Plan | Built during Session 0 | Not implemented |
| Worktree Lifecycle | Auto-create → execute → merge → cleanup | Manual worktree management |
| Expertise Storage | File-based `.claude/` structure | Database JSONB only |
| Generated Projects | Bootstrap with skills/expertise | No Claude SDK structure |
| Visual Management | Kanban swimlanes per worktree | Basic progress dashboard |

### Reference Implementations Reviewed

**ADWS Repo** (`.claude/` structure):
```
.claude/
├── skills/{skill-name}/
│   └── SKILL.md              # Native Claude SDK skill
├── commands/experts/{domain}/
│   ├── expertise.yaml        # Domain knowledge + patterns
│   ├── question.md           # How to query this expert
│   └── self-improve.md       # Self-improvement triggers
```

**Automaker Repo** (Worktree + Kanban):
```
apps/ui/src/components/views/board-view/
├── kanban-board.tsx          # @dnd-kit drag-drop columns
├── worktree-panel/           # Worktree visualization
│   ├── worktree-panel.tsx
│   └── worktree-status.tsx
apps/server/src/lib/
└── worktree-metadata.ts      # .automaker/worktrees/ storage
```

---

## Implementation Plan

### Phase 1: Execution Plan Engine (Session 0 Enhancement)

**Objective**: Build execution plan during initialization that determines parallel batches.

#### Task 1.1: Dependency Graph Builder
- Extend `DependencyResolver` to output serializable graph
- Store in `projects.metadata.execution_plan` JSONB field
- Format:
  ```json
  {
    "batches": [
      {"batch_id": 1, "task_ids": ["uuid1", "uuid2"], "can_parallel": true},
      {"batch_id": 2, "task_ids": ["uuid3"], "can_parallel": false, "depends_on": [1]}
    ],
    "worktree_assignments": {
      "uuid1": "worktree-batch1-epic1",
      "uuid2": "worktree-batch1-epic2"
    }
  }
  ```

#### Task 1.2: File Conflict Analyzer
- Parse task descriptions for likely file modifications
- Use epic context to predict file overlap
- Mark conflicting tasks for sequential execution
- Store in `tasks.metadata.predicted_files[]`

#### Task 1.3: Worktree Pre-Planning
- Calculate optimal worktree count (max 4 based on PRD)
- Pre-assign tasks to worktrees based on epic boundaries
- Validate no predicted file conflicts within same batch

#### Task 1.4: Execution Plan API
- `POST /projects/{id}/build-execution-plan` - Trigger plan building
- `GET /projects/{id}/execution-plan` - Retrieve current plan
- Auto-trigger after Session 0 completes successfully

### Phase 2: Automatic Parallel Orchestration

**Objective**: Make parallel mode the default execution path.

#### Task 2.1: Orchestrator Mode Selection
- Modify `Orchestrator.start_project()` to check execution plan
- If `execution_plan.batches[0].can_parallel` → parallel mode
- If single-threaded batch → sequential mode
- No manual trigger required

#### Task 2.2: Batch Executor
- New `BatchExecutor` class manages parallel batch lifecycle:
  1. Create worktrees for batch tasks
  2. Spawn agents per worktree
  3. Monitor completion
  4. Trigger merge validation
  5. Advance to next batch

#### Task 2.3: Merge Validation Pipeline
- After batch completion, before next batch:
  1. Run `git merge --no-commit` from each worktree
  2. If conflicts: spawn review agent to resolve
  3. Run test suite on merged result
  4. If pass: commit merge, cleanup worktrees
  5. If fail: flag for human review

#### Task 2.4: Progress Tracking Enhancement
- Add `batch_id` and `worktree_id` to session records
- Track parallel vs sequential execution time
- Calculate efficiency gains

### Phase 3: Expertise File System (ADWS Pattern)

**Objective**: Hybrid expertise storage - files for portability, DB for querying.

#### Task 3.1: File-Based Expertise Export
- New `ExpertiseExporter` class
- Writes database expertise to `.claude/commands/experts/{domain}/`:
  ```
  expertise.yaml    # From expertise.patterns + metrics
  question.md       # Generated query template
  self-improve.md   # Trigger conditions
  ```
- Runs after each session with new learnings

#### Task 3.2: Expertise Sync Service
- On project load: import from files → DB
- On expertise update: DB → files
- Git-friendly (expertise becomes part of codebase)

#### Task 3.3: Native Skills Generation
- When expertise crosses threshold (confidence > 0.8, usage > 10):
  - Generate `.claude/skills/{domain}-expert/SKILL.md`
  - Include frontmatter (name, description)
  - Embed relevant patterns as skill instructions

#### Task 3.4: Domain Router Update
- Modify `ExpertiseManager.route_to_expert()` to:
  1. Check `.claude/skills/` for native skills first
  2. Fall back to DB-stored expertise
  3. Log routing decisions for learning

### Phase 4: Generated Project Bootstrapping

**Objective**: Generated projects have Claude SDK structure from day 1.

#### Task 4.1: Project Template Structure
- Create template in `templates/claude-sdk-project/`:
  ```
  .claude/
  ├── settings.json           # Project-specific settings
  ├── skills/
  │   └── .gitkeep
  ├── commands/
  │   └── experts/
  │       └── .gitkeep
  └── CLAUDE.md               # Generated from app_spec
  ```

#### Task 4.2: Init Script Enhancement
- Modify initializer to copy template structure
- Generate initial `CLAUDE.md` from app_spec analysis
- Pre-create domain expert stubs based on detected domains

#### Task 4.3: Coding Agent Expertise Hooks
- After each task completion:
  1. Analyze code changes for patterns
  2. Update domain expertise files
  3. Commit expertise updates with code

#### Task 4.4: Sub-Agent Delegation
- Coding agent reads `.claude/commands/experts/` for domains
- Routes complex tasks to domain-specific expertise
- Each domain expert operates in context of its `expertise.yaml`

### Phase 5: Kanban/Swimlane UI (Automaker Pattern)

**Objective**: Visual parallel execution management with drag-drop.

#### Task 5.1: Kanban Board Component
- Port Automaker's `kanban-board.tsx` pattern
- Columns: Backlog | In Progress | Review | Done
- Cards show task + assigned worktree
- Use `@dnd-kit` for drag-drop

#### Task 5.2: Worktree Swimlanes
- Horizontal swimlanes per active worktree
- Show: branch name, current task, agent status, last commit
- Visual indicator for merge readiness

#### Task 5.3: Execution Plan Visualization
- Timeline/Gantt view of batch execution plan
- Show dependencies between batches
- Predicted vs actual completion overlay

#### Task 5.4: Real-Time Updates
- WebSocket events for:
  - Task status changes
  - Worktree creation/deletion
  - Merge conflicts detected
  - Batch transitions
- Update kanban without page refresh

#### Task 5.5: Manual Override Controls
- Drag task between worktrees (re-assign)
- Force sequential execution toggle
- Pause/resume batch execution
- Manually trigger merge validation

---

## Dependencies Between Phases

```
Phase 1 (Execution Plan)
    ↓
Phase 2 (Auto Parallel) ←──→ Phase 5 (Kanban UI)
    ↓                              ↓
Phase 3 (Expertise Files)    [Visual feedback loop]
    ↓
Phase 4 (Project Bootstrap)
```

- Phase 1 must complete before Phase 2 (need plan to execute)
- Phase 5 can start parallel with Phase 2 (UI for existing data)
- Phase 3 and 4 are additive (can be developed independently)

---

## Database Schema Changes

```sql
-- Add execution plan to projects
ALTER TABLE projects
ADD COLUMN execution_plan JSONB;

-- Add batch tracking to sessions
ALTER TABLE sessions
ADD COLUMN batch_id INTEGER,
ADD COLUMN worktree_id VARCHAR(100);

-- Add predicted files to tasks
ALTER TABLE tasks
ADD COLUMN predicted_files TEXT[];

-- New table for worktree lifecycle
CREATE TABLE worktrees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    branch_name VARCHAR(200) NOT NULL,
    batch_id INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    merged_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);
```

---

## API Endpoints (New/Modified)

```
# Execution Plan
POST   /projects/{id}/build-execution-plan
GET    /projects/{id}/execution-plan
PATCH  /projects/{id}/execution-plan  # Manual adjustments

# Worktrees
GET    /projects/{id}/worktrees
POST   /projects/{id}/worktrees       # Manual creation
DELETE /worktrees/{id}                # Cleanup
POST   /worktrees/{id}/merge          # Trigger merge

# Batch Execution
POST   /projects/{id}/batches/{batch}/start
GET    /projects/{id}/batches/{batch}/status
POST   /projects/{id}/batches/{batch}/pause

# Expertise Files
POST   /projects/{id}/expertise/export
POST   /projects/{id}/expertise/sync
GET    /projects/{id}/expertise/files
```

---

## File Structure Changes

```
yokeflow/
├── core/
│   ├── execution_plan.py      # NEW: Execution plan builder
│   ├── batch_executor.py      # NEW: Parallel batch management
│   ├── merge_validator.py     # NEW: Pre-merge validation
│   └── expertise_exporter.py  # NEW: DB → file export
├── templates/
│   └── claude-sdk-project/    # NEW: Bootstrap template
│       └── .claude/...
├── web-ui/src/components/
│   ├── KanbanBoard.tsx        # NEW: Drag-drop board
│   ├── WorktreeSwimlane.tsx   # NEW: Per-worktree lane
│   └── ExecutionTimeline.tsx  # NEW: Batch visualization
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Merge conflicts in parallel tasks | High | File conflict analyzer + review agent |
| Worktree resource exhaustion | Medium | Cap at 4 worktrees, queue excess |
| Expertise file drift from DB | Medium | Bidirectional sync, conflict detection |
| UI complexity overwhelming users | Medium | Progressive disclosure, simple defaults |

---

## Success Metrics

1. **Parallel Efficiency**: >30% reduction in total project time
2. **Merge Success Rate**: >90% auto-merge without conflicts
3. **Expertise Reuse**: >50% of tasks benefit from prior learnings
4. **UI Adoption**: Users interact with kanban >3x per project

---

## Estimated Effort

| Phase | Complexity | New Files | Modified Files |
|-------|------------|-----------|----------------|
| 1. Execution Plan | High | 2 | 4 |
| 2. Auto Parallel | High | 3 | 5 |
| 3. Expertise Files | Medium | 2 | 3 |
| 4. Project Bootstrap | Medium | 1 | 2 |
| 5. Kanban UI | High | 4 | 2 |

**Total**: 12 new files, 16 modified files

---

## Next Steps (After Approval)

1. Create epics/tasks in database for tracking
2. Start with Phase 1 (foundation for everything else)
3. Phase 2 + Phase 5 can proceed in parallel
4. Phase 3 + Phase 4 follow after core parallel system works
