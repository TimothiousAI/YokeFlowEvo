# Implementation Plan: Phase 5 - Kanban/Swimlane UI

## Task Description

Implement visual parallel execution management with Kanban board, worktree swimlanes, execution timeline, and real-time updates. Enable manual control of parallel execution through the UI.

## Objectives

- [ ] Create KanbanBoard component with drag-drop support
- [ ] Enhance WorktreeSwimlane with live status
- [ ] Create ExecutionTimeline/Gantt visualization
- [ ] Add WebSocket real-time updates
- [ ] Add API endpoints for parallel execution control
- [ ] Integrate components into project detail page

## Dependencies

**NPM Package Required**:
```bash
cd web-ui && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

## Relevant Files

| File | Purpose | Action |
|------|---------|--------|
| `web-ui/src/components/KanbanBoard.tsx` | Kanban board with drag-drop | Create |
| `web-ui/src/components/ExecutionTimeline.tsx` | Timeline/Gantt visualization | Create |
| `web-ui/src/components/ParallelControlPanel.tsx` | Control panel for parallel exec | Create |
| `web-ui/src/components/WorktreeCard.tsx` | Worktree status card | Create |
| `web-ui/src/components/ParallelSwimlane.tsx` | Enhance with controls | Modify |
| `web-ui/src/components/ParallelProgress.tsx` | Add control buttons | Modify |
| `web-ui/src/lib/api.ts` | Add parallel API methods | Modify |
| `api/main.py` | Add worktree/batch endpoints | Modify |

## File Specifications

---

### File: web-ui/src/components/KanbanBoard.tsx

**Purpose**: Kanban board for task management with drag-drop support.

**Features**:
- Columns: Backlog | In Progress | Review | Done
- Task cards show: task ID, description, epic, worktree assignment
- Drag tasks between columns (changes status)
- Visual indicators for parallel execution
- Filter by epic or worktree

**Dependencies**: `@dnd-kit/core`, `@dnd-kit/sortable`

**Interface**:
```typescript
interface KanbanBoardProps {
  tasks: Task[];
  epics: Epic[];
  worktrees?: Worktree[];
  onTaskMove?: (taskId: number, newStatus: string) => void;
  onTaskAssign?: (taskId: number, worktreeId: string) => void;
  className?: string;
}

type KanbanColumn = 'backlog' | 'in_progress' | 'review' | 'done';
```

---

### File: web-ui/src/components/ExecutionTimeline.tsx

**Purpose**: Timeline/Gantt view of batch execution plan.

**Features**:
- Horizontal timeline with batch blocks
- Show batch dependencies (arrows)
- Highlight current batch
- Show predicted vs actual completion
- Hover for task details

**Interface**:
```typescript
interface ExecutionTimelineProps {
  executionPlan: ExecutionPlan;
  currentBatch?: number;
  completedTasks?: number[];
  className?: string;
}

interface ExecutionPlan {
  batches: Batch[];
  worktree_assignments: Record<string, string>;
}

interface Batch {
  batch_id: number;
  task_ids: number[];
  can_parallel: boolean;
  depends_on?: number[];
}
```

---

### File: web-ui/src/components/ParallelControlPanel.tsx

**Purpose**: Control panel for managing parallel execution.

**Features**:
- Start/Stop parallel execution buttons
- Pause/Resume current batch
- Force sequential toggle
- Manual merge trigger
- Execution mode indicator (parallel/sequential)

**Interface**:
```typescript
interface ParallelControlPanelProps {
  projectId: string;
  executionMode: 'idle' | 'sequential' | 'parallel' | 'parallel_running' | 'paused';
  currentBatch?: number;
  onStart?: () => void;
  onStop?: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onMerge?: () => void;
  className?: string;
}
```

---

### File: web-ui/src/components/WorktreeCard.tsx

**Purpose**: Card showing worktree status.

**Features**:
- Branch name and status
- Current task being worked on
- Agent status (running/idle)
- Last commit timestamp
- Merge readiness indicator

**Interface**:
```typescript
interface WorktreeCardProps {
  worktree: Worktree;
  currentTask?: Task;
  agentStatus?: 'running' | 'idle' | 'error';
  className?: string;
}

interface Worktree {
  id: string;
  branch_name: string;
  batch_id: number;
  status: 'pending' | 'active' | 'merged' | 'conflict';
  created_at: string;
  merged_at?: string;
}
```

---

### File: web-ui/src/lib/api.ts (Additions)

**New API Methods**:
```typescript
// Parallel execution control
export async function startParallelExecution(projectId: string): Promise<void>
export async function stopParallelExecution(projectId: string): Promise<void>
export async function pauseExecution(projectId: string): Promise<void>
export async function resumeExecution(projectId: string): Promise<void>

// Execution plan
export async function getExecutionPlan(projectId: string): Promise<ExecutionPlan>
export async function rebuildExecutionPlan(projectId: string): Promise<ExecutionPlan>

// Worktrees
export async function getWorktrees(projectId: string): Promise<Worktree[]>
export async function triggerMerge(worktreeId: string): Promise<MergeResult>

// Task reassignment
export async function reassignTask(taskId: number, worktreeId: string): Promise<void>
export async function updateTaskStatus(taskId: number, status: string): Promise<void>
```

---

### File: api/main.py (New Endpoints)

**Worktree Endpoints**:
```python
@app.get("/api/projects/{project_id}/worktrees")
async def get_worktrees(project_id: UUID) -> List[WorktreeResponse]

@app.post("/api/worktrees/{worktree_id}/merge")
async def trigger_merge(worktree_id: UUID) -> MergeResult

@app.delete("/api/worktrees/{worktree_id}")
async def delete_worktree(worktree_id: UUID) -> None
```

**Execution Control**:
```python
@app.post("/api/projects/{project_id}/execution/pause")
async def pause_execution(project_id: UUID) -> None

@app.post("/api/projects/{project_id}/execution/resume")
async def resume_execution(project_id: UUID) -> None

@app.patch("/api/tasks/{task_id}/status")
async def update_task_status(task_id: int, status: str) -> Task

@app.patch("/api/tasks/{task_id}/worktree")
async def assign_task_worktree(task_id: int, worktree_id: str) -> Task
```

**WebSocket Events** (enhance existing):
```python
# Emit these events via WebSocket:
- task_status_changed: { task_id, old_status, new_status }
- worktree_created: { worktree_id, branch_name, batch_id }
- worktree_merged: { worktree_id, branch_name }
- worktree_conflict: { worktree_id, branch_name, files }
- batch_started: { batch_id, task_count }
- batch_completed: { batch_id, duration }
- execution_paused: { project_id }
- execution_resumed: { project_id }
```

---

## Implementation Phases

### Phase 5.1: Foundation (No Dependencies)
1. Install @dnd-kit packages
2. Create WorktreeCard component
3. Create ExecutionTimeline component
4. Add API type definitions

### Phase 5.2: Kanban Board
1. Create KanbanBoard component with columns
2. Implement drag-drop with @dnd-kit
3. Add task cards with status colors
4. Connect to API for status updates

### Phase 5.3: Control Panel
1. Create ParallelControlPanel component
2. Add API endpoints for execution control
3. Integrate with existing ParallelProgress

### Phase 5.4: WebSocket Updates
1. Add new WebSocket event types
2. Subscribe to events in components
3. Update UI in real-time

### Phase 5.5: Integration
1. Add parallel tab to project detail page
2. Combine all components in dashboard view
3. Add routing for /projects/[id]/parallel

---

## Existing Components to Enhance

### ParallelSwimlane.tsx
- Add worktree labels to lanes
- Add hover tooltips with task details
- Add click handler to open task detail

### ParallelProgress.tsx
- Add pause/resume buttons
- Add stop button
- Show execution mode

---

## Testing Requirements

1. **Component tests**:
   - KanbanBoard renders all columns
   - Drag-drop updates task status
   - ExecutionTimeline shows batches correctly
   - ParallelControlPanel buttons work

2. **Integration tests**:
   - WebSocket events update UI
   - API calls succeed
   - State synchronizes correctly

---

## Success Criteria

- [ ] Kanban board displays tasks in correct columns
- [ ] Drag-drop changes task status
- [ ] Timeline shows execution plan accurately
- [ ] Control panel can start/stop/pause execution
- [ ] WebSocket updates UI in real-time
- [ ] Worktree status visible in swimlanes
