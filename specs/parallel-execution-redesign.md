# Plan: Parallel Execution System Redesign

## Task Description

Redesign the parallel execution system to follow the correct mental model:
- **Epics run in parallel** (different code areas, different worktrees)
- **Tasks within an epic run sequentially** (build on each other)
- **Each running agent has full session visibility** via a detail modal

This mimics how real development teams work: frontend team, backend team, database team all work in parallel, but within each team tasks are sequential.

## Objectives

- [ ] Fix backend executor so tasks within an epic run sequentially
- [ ] Build SessionDetailModal component with full session tabs
- [ ] Update BatchExecutionView with click-to-open-modal flow
- [ ] Ensure WebSocket events route correctly to each agent's UI

## Relevant Files

| File | Purpose | Action |
|------|---------|--------|
| `core/parallel/parallel_executor.py` | Orchestrates parallel execution | Modify |
| `core/execution_plan.py` | Builds execution plan | Review (already correct) |
| `web-ui/src/components/parallel/SessionCard.tsx` | Agent summary card | Modify |
| `web-ui/src/components/parallel/SessionDetailModal.tsx` | Full session view | Create |
| `web-ui/src/components/parallel/BatchExecutionView.tsx` | Main container | Modify |
| `web-ui/src/components/parallel/hooks/useParallelState.ts` | State management | Modify |
| `web-ui/src/components/CurrentSession.tsx` | Reference for session UI | Reference |

## Implementation Phases

### Phase 1: Backend Execution Model Fix

Fix `parallel_executor.py` to run tasks sequentially within each epic/worktree.

**Current (Wrong):**
```python
# All tasks in batch run in parallel
task_coroutines = [self._execute_task(t, wt) for t in tasks]
await asyncio.gather(*task_coroutines)
```

**Correct:**
```python
# Group tasks by epic/worktree
# Run epics in parallel, tasks within epic sequentially
epic_coroutines = [self._execute_epic_tasks(epic_id, tasks, worktree) for epic_id, tasks in tasks_by_epic.items()]
await asyncio.gather(*epic_coroutines)

async def _execute_epic_tasks(self, epic_id, tasks, worktree):
    """Run tasks sequentially within a single epic/worktree."""
    for task in sorted(tasks, key=lambda t: t.get('priority', 999)):
        await self.run_task_agent(task, worktree)
```

### Phase 2: SessionDetailModal Component

Create a modal that shows full session details for a selected agent.

**Tabs:**
1. **Current** - Streaming output, current tool, recent activity
2. **History** - Completed tasks in this epic
3. **Logs** - Session logs (reuse SessionLogsViewer)
4. **Screenshots** - Browser screenshots (reuse ScreenshotsGallery)
5. **Quality** - Quality metrics for this agent
6. **Costs** - Cost breakdown for this agent

### Phase 3: UI Integration

Wire up SessionCard click → SessionDetailModal open flow.

---

## File Specifications

### File: `core/parallel/parallel_executor.py`

**Purpose**: Orchestrate parallel execution across epics

**Requirements**:
- Group tasks by epic_id
- Create one worktree per epic
- Run epics in parallel (via asyncio.gather on epic groups)
- Run tasks SEQUENTIALLY within each epic
- Emit WebSocket events with epic_id context

**Key Changes**:

```python
async def execute_batch(self, batch_number: int, task_ids: List[int]) -> List[ExecutionResult]:
    """Execute a batch with parallel epics, sequential tasks within epic."""

    # Group tasks by epic
    tasks_by_epic: Dict[int, List[dict]] = {}
    for task_id in task_ids:
        task = await self.db.get_task_with_tests(task_id, self.project_id)
        epic_id = task['epic_id']
        if epic_id not in tasks_by_epic:
            tasks_by_epic[epic_id] = []
        tasks_by_epic[epic_id].append(task)

    # Create worktrees for each epic
    worktree_paths: Dict[int, str] = {}
    for epic_id, tasks in tasks_by_epic.items():
        epic_name = tasks[0].get('epic_name', f'Epic {epic_id}')
        worktree_info = await self.worktree_manager.create_worktree(epic_id, epic_name)
        worktree_paths[epic_id] = worktree_info.path

    # Execute epics in parallel, tasks within epic sequentially
    async def execute_epic_sequentially(epic_id: int, tasks: List[dict]) -> List[ExecutionResult]:
        """Run all tasks for one epic sequentially in its worktree."""
        results = []
        worktree = worktree_paths[epic_id]

        # Sort by priority within epic
        sorted_tasks = sorted(tasks, key=lambda t: t.get('priority', 999))

        for task in sorted_tasks:
            # Use semaphore for global concurrency limit
            async with self.semaphore:
                result = await self.run_task_agent(task, worktree)
                results.append(result)

                # If task failed, optionally stop epic execution
                if not result.success:
                    logger.warning(f"Task {task['id']} failed, continuing with next task in epic")

        return results

    # Run all epics in parallel
    epic_coroutines = [
        execute_epic_sequentially(epic_id, tasks)
        for epic_id, tasks in tasks_by_epic.items()
    ]

    all_results_nested = await asyncio.gather(*epic_coroutines, return_exceptions=True)

    # Flatten results
    all_results = []
    for result in all_results_nested:
        if isinstance(result, Exception):
            logger.error(f"Epic execution failed: {result}")
        else:
            all_results.extend(result)

    return all_results
```

**Patterns to Follow**: From `orchestration/expertise.yaml`
- `worktree_isolation` pattern
- `graceful_shutdown` pattern
- `session_lifecycle` pattern

---

### File: `web-ui/src/components/parallel/SessionDetailModal.tsx`

**Purpose**: Full session details modal for a selected parallel agent

**Requirements**:
- Modal overlay with close button
- Navigation arrows to switch between agents
- Tabs: Current, History, Logs, Screenshots, Quality, Costs
- Real-time streaming updates for current tab
- Reuse existing components where possible

**Props**:
```typescript
interface SessionDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  session: SessionInfo;
  allSessions: SessionInfo[];  // For navigation
  onNavigate: (taskId: number) => void;
  projectId: string;
  // Streaming data
  toolUses: ToolUse[];
  currentTool: string | null;
  // Tab data
  logs?: string;
  screenshots?: Screenshot[];
  costs?: CostInfo;
}
```

**Component Structure**:
```tsx
export function SessionDetailModal({
  isOpen,
  onClose,
  session,
  allSessions,
  onNavigate,
  projectId,
  toolUses,
  currentTool,
}: SessionDetailModalProps) {
  const [activeTab, setActiveTab] = useState<'current' | 'history' | 'logs' | 'screenshots' | 'quality' | 'costs'>('current');

  // Find prev/next sessions for navigation
  const currentIndex = allSessions.findIndex(s => s.taskId === session.taskId);
  const prevSession = currentIndex > 0 ? allSessions[currentIndex - 1] : null;
  const nextSession = currentIndex < allSessions.length - 1 ? allSessions[currentIndex + 1] : null;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-4">
            {/* Navigation arrows */}
            <button onClick={() => prevSession && onNavigate(prevSession.taskId)} disabled={!prevSession}>
              <ChevronLeft />
            </button>
            <h2>{session.epicName} - Task #{session.taskId}</h2>
            <button onClick={() => nextSession && onNavigate(nextSession.taskId)} disabled={!nextSession}>
              <ChevronRight />
            </button>
          </div>
          <button onClick={onClose}><X /></button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-700">
          {['current', 'history', 'logs', 'screenshots', 'quality', 'costs'].map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} className={...}>
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="p-4 overflow-y-auto max-h-[calc(90vh-140px)]">
          {activeTab === 'current' && (
            <CurrentTabContent session={session} toolUses={toolUses} currentTool={currentTool} />
          )}
          {activeTab === 'logs' && (
            <SessionLogsViewer projectId={projectId} sessionId={session.sessionId} />
          )}
          {/* ... other tabs */}
        </div>
      </div>
    </div>
  );
}
```

**Patterns to Follow**: From `frontend/expertise.yaml`
- `client_component` pattern (needs useState, onClick)
- `shadcn_component` pattern for styling

---

### File: `web-ui/src/components/parallel/SessionCard.tsx`

**Purpose**: Summary card for each running agent

**Requirements**:
- Add onClick handler to open detail modal
- Show visual indicator that card is clickable
- Keep existing streaming output display

**Changes**:
```typescript
interface SessionCardProps {
  session: SessionInfo;
  isRunning: boolean;
  onViewDetails?: () => void;  // Already exists
  onStop?: () => void;
  className?: string;
}

// Add hover state and click handling
<div
  className={cn(
    'relative rounded-lg border bg-gray-800/50 ...',
    'cursor-pointer hover:border-blue-500/50 transition-colors',
    ...
  )}
  onClick={onViewDetails}  // Make whole card clickable
>
```

---

### File: `web-ui/src/components/parallel/BatchExecutionView.tsx`

**Purpose**: Main container for parallel execution UI

**Requirements**:
- Add state for selected session (for modal)
- Render SessionDetailModal when session selected
- Pass click handler to SessionCards

**Changes**:
```typescript
export function BatchExecutionView({ ... }) {
  // Existing state...

  // New: Modal state
  const [selectedSession, setSelectedSession] = useState<SessionInfo | null>(null);

  // Handler for session card click
  const handleViewSessionDetails = (taskId: number) => {
    const session = runningSessions.find(s => s.taskId === taskId);
    if (session) {
      setSelectedSession(session);
    }
  };

  return (
    <div className={cn('space-y-4', className)}>
      {/* Existing content... */}

      {/* Session Detail Modal */}
      <SessionDetailModal
        isOpen={selectedSession !== null}
        onClose={() => setSelectedSession(null)}
        session={selectedSession}
        allSessions={runningSessions}
        onNavigate={(taskId) => {
          const session = runningSessions.find(s => s.taskId === taskId);
          if (session) setSelectedSession(session);
        }}
        projectId={projectId}
        toolUses={selectedSession?.toolUses || []}
        currentTool={selectedSession?.currentTool || null}
      />
    </div>
  );
}
```

---

### File: `web-ui/src/components/parallel/hooks/useParallelState.ts`

**Purpose**: State management for parallel execution

**Requirements**:
- Track streaming data per session (already done)
- Expose data needed for modal
- No major changes needed (already tracks toolUses, currentTool per session)

---

## Testing Strategy

### Backend Tests
- Unit test: `test_execute_epic_sequentially` - verify tasks run in order
- Unit test: `test_parallel_epics` - verify different epics run concurrently
- Integration test: Run batch with 2 epics, 3 tasks each, verify execution order

### Frontend Tests
- Component test: SessionDetailModal renders with all tabs
- Component test: SessionCard opens modal on click
- Component test: Modal navigation between sessions works
- E2E test: Start parallel execution, click session card, verify modal content

### Validation Commands
```bash
# Backend
pytest tests/test_parallel_executor.py -v
python -m mypy core/parallel/parallel_executor.py

# Frontend
cd web-ui && npm run build
cd web-ui && npm run lint
```

---

## Acceptance Criteria

- [ ] Tasks within same epic run sequentially (verify via logs showing task order)
- [ ] Different epics run in parallel (verify via timestamps showing overlap)
- [ ] Clicking SessionCard opens SessionDetailModal
- [ ] Modal shows all 6 tabs: Current, History, Logs, Screenshots, Quality, Costs
- [ ] Modal navigation arrows switch between running agents
- [ ] Real-time streaming updates appear in modal's Current tab
- [ ] Build passes with no TypeScript errors

---

## Visual Reference

**BatchExecutionView with Modal:**
```
┌─────────────────────────────────────────────────────────────────┐
│ PARALLEL EXECUTION                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Backend API  │  │ Frontend UI  │  │ Database     │          │
│  │ [Click me]   │  │ [Click me]   │  │ [Click me]   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ┌───────────────────────────────────────────────────┐   │   │
│  │ │ Backend API Agent                    [←] [→] [✕]  │   │   │
│  │ │ Epic: Backend │ Task 2/3                          │   │   │
│  │ ├───────────────────────────────────────────────────┤   │   │
│  │ │ [Current] [History] [Logs] [Screenshots] ...     │   │   │
│  │ ├───────────────────────────────────────────────────┤   │   │
│  │ │                                                   │   │   │
│  │ │  Task: Create REST API endpoints                  │   │   │
│  │ │                                                   │   │   │
│  │ │  Current Tool: Edit                               │   │   │
│  │ │  File: api/routes/users.py                        │   │   │
│  │ │                                                   │   │   │
│  │ │  Recent Activity:                                 │   │   │
│  │ │  ✓ Read api/main.py                              │   │   │
│  │ │  ✓ Glob **/*.py                                  │   │   │
│  │ │  ⚡ Edit api/routes/users.py                     │   │   │
│  │ │                                                   │   │   │
│  │ └───────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Order

1. **Phase 1**: Fix `parallel_executor.py` (backend model)
2. **Phase 2**: Create `SessionDetailModal.tsx` (new component)
3. **Phase 3**: Update `SessionCard.tsx` (add click handler)
4. **Phase 4**: Update `BatchExecutionView.tsx` (wire up modal)
5. **Phase 5**: Test and verify

---

## Dependencies

- No new npm packages required
- Reuses existing components: SessionLogsViewer, ScreenshotsGallery
- Reuses existing Tailwind + Lucide icons
