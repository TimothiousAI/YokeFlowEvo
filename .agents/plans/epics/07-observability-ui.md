# Epic 07: Observability & UI Enhancements

**Priority:** P1 (Enhancement)
**Estimated Duration:** 3-4 days
**Dependencies:** Epic 01 (Foundation), Epic 04 (Parallel Executor)
**Phase:** 2

---

## Overview

Enhance the observability and UI to support parallel execution visualization. Includes swimlane views for parallel tasks, real-time progress dashboards, cost tracking UI, and WebSocket events for live updates.

---

## Tasks

### 7.1 Swimlane Progress Visualization

**Description:** Create a swimlane diagram showing parallel epic execution.

**File:** `web-ui/src/components/SwimlaneProgress.tsx`

**Component Structure:**

```typescript
interface Epic {
  id: number;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  tasks: Task[];
  worktree?: WorktreeInfo;
}

interface Task {
  id: number;
  title: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
}

interface WorktreeInfo {
  branch: string;
  status: 'active' | 'merged' | 'conflict';
}

interface SwimlaneProgressProps {
  projectId: string;
  epics: Epic[];
  batches: BatchInfo[];
}

export function SwimlaneProgress({ projectId, epics, batches }: SwimlaneProgressProps) {
  return (
    <div className="swimlane-container">
      {/* Timeline header showing batches */}
      <div className="batch-header">
        {batches.map((batch, index) => (
          <div key={batch.id} className="batch-column">
            <span className="batch-label">Batch {index + 1}</span>
            <span className="batch-status">{batch.status}</span>
          </div>
        ))}
      </div>

      {/* Swimlane rows for each epic */}
      {epics.map(epic => (
        <div key={epic.id} className="swimlane-row">
          <div className="lane-header">
            <EpicBadge epic={epic} />
            {epic.worktree && (
              <WorktreeBadge worktree={epic.worktree} />
            )}
          </div>

          <div className="lane-content">
            {epic.tasks.map(task => (
              <TaskCard
                key={task.id}
                task={task}
                batchIndex={findBatchIndex(task.id, batches)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

**CSS Styling:**

```css
.swimlane-container {
  display: flex;
  flex-direction: column;
  overflow-x: auto;
}

.batch-header {
  display: flex;
  border-bottom: 2px solid #e0e0e0;
  margin-left: 200px;
}

.batch-column {
  min-width: 150px;
  padding: 8px;
  text-align: center;
  border-right: 1px solid #e0e0e0;
}

.swimlane-row {
  display: flex;
  border-bottom: 1px solid #f0f0f0;
  min-height: 80px;
}

.lane-header {
  width: 200px;
  padding: 12px;
  background: #f8f9fa;
  border-right: 1px solid #e0e0e0;
}

.lane-content {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 8px;
  padding: 8px;
}

.task-card {
  padding: 8px 12px;
  border-radius: 6px;
  background: white;
  border: 1px solid #e0e0e0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.task-card.in_progress {
  border-color: #3b82f6;
  background: #eff6ff;
}

.task-card.completed {
  border-color: #10b981;
  background: #ecfdf5;
}

.task-card.failed {
  border-color: #ef4444;
  background: #fef2f2;
}
```

**Acceptance Criteria:**
- [ ] Renders swimlane diagram correctly
- [ ] Shows epic lanes with worktree info
- [ ] Tasks positioned by batch
- [ ] Status colors clear
- [ ] Horizontal scroll for many batches

---

### 7.2 Real-Time WebSocket Events

**Description:** Add WebSocket events for parallel execution updates.

**File:** `api/websocket.py` (new or extend existing)

**Event Types:**

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any

class EventType(Enum):
    # Batch events
    BATCH_STARTED = "batch_started"
    BATCH_COMPLETED = "batch_completed"
    BATCH_FAILED = "batch_failed"

    # Task events
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # Worktree events
    WORKTREE_CREATED = "worktree_created"
    WORKTREE_MERGED = "worktree_merged"
    WORKTREE_CONFLICT = "worktree_conflict"

    # Agent events
    AGENT_SPAWNED = "agent_spawned"
    AGENT_TERMINATED = "agent_terminated"
    AGENT_OUTPUT = "agent_output"

    # Cost events
    COST_UPDATE = "cost_update"
    BUDGET_WARNING = "budget_warning"

@dataclass
class ParallelEvent:
    """Event for parallel execution updates"""
    type: EventType
    project_id: str
    timestamp: str
    data: Dict[str, Any]

    def to_json(self) -> dict:
        return {
            "type": self.type.value,
            "project_id": self.project_id,
            "timestamp": self.timestamp,
            "data": self.data
        }

class ParallelEventEmitter:
    """Emits events for parallel execution"""

    def __init__(self, connection_manager):
        self.manager = connection_manager

    async def emit_batch_started(self, project_id: str, batch_number: int, task_ids: list):
        """Emit when a batch starts execution"""
        event = ParallelEvent(
            type=EventType.BATCH_STARTED,
            project_id=project_id,
            timestamp=datetime.now().isoformat(),
            data={
                "batch_number": batch_number,
                "task_ids": task_ids,
                "task_count": len(task_ids)
            }
        )
        await self.manager.broadcast_to_project(project_id, event.to_json())

    async def emit_task_progress(
        self,
        project_id: str,
        task_id: int,
        progress: int,
        message: str
    ):
        """Emit task progress update"""
        event = ParallelEvent(
            type=EventType.TASK_PROGRESS,
            project_id=project_id,
            timestamp=datetime.now().isoformat(),
            data={
                "task_id": task_id,
                "progress": progress,
                "message": message
            }
        )
        await self.manager.broadcast_to_project(project_id, event.to_json())

    async def emit_agent_output(
        self,
        project_id: str,
        task_id: int,
        output_type: str,
        content: str
    ):
        """Emit agent output (streaming)"""
        event = ParallelEvent(
            type=EventType.AGENT_OUTPUT,
            project_id=project_id,
            timestamp=datetime.now().isoformat(),
            data={
                "task_id": task_id,
                "output_type": output_type,  # 'stdout', 'stderr', 'tool_call', 'response'
                "content": content
            }
        )
        await self.manager.broadcast_to_project(project_id, event.to_json())
```

**Acceptance Criteria:**
- [ ] All event types defined
- [ ] Events broadcast correctly
- [ ] Project-scoped broadcasting
- [ ] Timestamps included

---

### 7.3 Parallel Progress Dashboard

**Description:** Create dashboard page for parallel execution monitoring.

**File:** `web-ui/src/pages/projects/[id]/parallel.tsx`

**Page Layout:**

```typescript
export default function ParallelDashboard() {
  const router = useRouter();
  const { id: projectId } = router.query;
  const [parallelStatus, setParallelStatus] = useState<ParallelStatus | null>(null);

  // WebSocket connection for real-time updates
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/projects/${projectId}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleParallelEvent(data);
    };

    return () => ws.close();
  }, [projectId]);

  return (
    <div className="parallel-dashboard">
      {/* Header with controls */}
      <div className="dashboard-header">
        <h1>Parallel Execution</h1>
        <div className="controls">
          <ParallelToggle enabled={parallelStatus?.enabled} />
          <ConcurrencySlider value={parallelStatus?.concurrency} max={5} />
          <EmergencyStop onStop={handleEmergencyStop} />
        </div>
      </div>

      {/* Status overview */}
      <div className="status-cards">
        <StatusCard
          title="Active Batches"
          value={parallelStatus?.activeBatches}
          icon={<LayersIcon />}
        />
        <StatusCard
          title="Running Agents"
          value={parallelStatus?.runningAgents}
          icon={<BotIcon />}
        />
        <StatusCard
          title="Active Worktrees"
          value={parallelStatus?.activeWorktrees}
          icon={<GitBranchIcon />}
        />
        <StatusCard
          title="Cost Today"
          value={`$${parallelStatus?.costToday?.toFixed(2)}`}
          icon={<DollarIcon />}
        />
      </div>

      {/* Swimlane visualization */}
      <SwimlaneProgress
        projectId={projectId}
        epics={parallelStatus?.epics || []}
        batches={parallelStatus?.batches || []}
      />

      {/* Active agent terminals */}
      <div className="agent-terminals">
        {parallelStatus?.runningAgents?.map(agent => (
          <AgentTerminal
            key={agent.taskId}
            taskId={agent.taskId}
            epicName={agent.epicName}
            output={agent.output}
          />
        ))}
      </div>

      {/* Worktree status */}
      <WorktreePanel worktrees={parallelStatus?.worktrees || []} />
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Real-time updates via WebSocket
- [ ] Swimlane visualization
- [ ] Agent output streaming
- [ ] Emergency stop button
- [ ] Concurrency controls

---

### 7.4 Cost Tracking Dashboard

**Description:** Add cost tracking visualization.

**File:** `web-ui/src/components/CostDashboard.tsx`

**Component:**

```typescript
interface CostData {
  totalCost: number;
  budgetLimit: number | null;
  byModel: Record<string, { cost: number; calls: number }>;
  byTaskType: Record<string, number>;
  dailyCosts: Array<{ date: string; cost: number }>;
  forecast: {
    remainingTasks: number;
    estimatedCost: number;
    confidence: number;
  };
}

export function CostDashboard({ projectId }: { projectId: string }) {
  const [costData, setCostData] = useState<CostData | null>(null);

  return (
    <div className="cost-dashboard">
      {/* Budget gauge */}
      <div className="budget-section">
        <h2>Budget Usage</h2>
        {costData?.budgetLimit ? (
          <BudgetGauge
            spent={costData.totalCost}
            limit={costData.budgetLimit}
          />
        ) : (
          <p className="no-limit">No budget limit set</p>
        )}
      </div>

      {/* Cost by model pie chart */}
      <div className="model-breakdown">
        <h2>Cost by Model</h2>
        <PieChart
          data={Object.entries(costData?.byModel || {}).map(([model, data]) => ({
            name: model,
            value: data.cost,
            calls: data.calls
          }))}
        />
      </div>

      {/* Daily cost trend */}
      <div className="daily-trend">
        <h2>Daily Costs</h2>
        <LineChart
          data={costData?.dailyCosts || []}
          xKey="date"
          yKey="cost"
        />
      </div>

      {/* Cost forecast */}
      <div className="forecast">
        <h2>Cost Forecast</h2>
        <ForecastCard
          remainingTasks={costData?.forecast.remainingTasks}
          estimatedCost={costData?.forecast.estimatedCost}
          confidence={costData?.forecast.confidence}
        />
      </div>

      {/* Cost by task type */}
      <div className="task-type-breakdown">
        <h2>Cost by Task Type</h2>
        <BarChart
          data={Object.entries(costData?.byTaskType || {}).map(([type, cost]) => ({
            name: type,
            cost
          }))}
        />
      </div>
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Budget gauge visualization
- [ ] Model breakdown chart
- [ ] Daily trend line chart
- [ ] Forecast display
- [ ] Task type breakdown

---

### 7.5 Agent Terminal Component

**Description:** Create terminal view for streaming agent output.

**File:** `web-ui/src/components/AgentTerminal.tsx`

**Component:**

```typescript
interface AgentTerminalProps {
  taskId: number;
  epicName: string;
  output: string[];
  onAbort?: () => void;
}

export function AgentTerminal({ taskId, epicName, output, onAbort }: AgentTerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [output]);

  return (
    <div className="agent-terminal">
      <div className="terminal-header">
        <div className="terminal-info">
          <span className="epic-badge">{epicName}</span>
          <span className="task-id">Task #{taskId}</span>
        </div>
        <div className="terminal-actions">
          <button onClick={onAbort} className="abort-btn">
            <StopIcon /> Abort
          </button>
        </div>
      </div>

      <div
        ref={terminalRef}
        className="terminal-content"
      >
        {output.map((line, index) => (
          <TerminalLine key={index} content={line} />
        ))}
        <span className="cursor blink">_</span>
      </div>
    </div>
  );
}

function TerminalLine({ content }: { content: string }) {
  // Parse line type (tool call, response, error, etc.)
  const lineType = parseLineType(content);

  return (
    <div className={`terminal-line ${lineType}`}>
      {lineType === 'tool_call' && <ToolIcon />}
      {lineType === 'error' && <ErrorIcon />}
      <span>{content}</span>
    </div>
  );
}
```

**CSS:**

```css
.agent-terminal {
  background: #1a1a2e;
  border-radius: 8px;
  overflow: hidden;
  font-family: 'Fira Code', monospace;
}

.terminal-header {
  background: #16213e;
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.terminal-content {
  height: 300px;
  overflow-y: auto;
  padding: 12px;
  font-size: 12px;
  line-height: 1.5;
  color: #e0e0e0;
}

.terminal-line {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}

.terminal-line.tool_call {
  color: #64b5f6;
}

.terminal-line.error {
  color: #ef5350;
}

.terminal-line.success {
  color: #66bb6a;
}

.cursor.blink {
  animation: blink 1s infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}
```

**Acceptance Criteria:**
- [ ] Streams output in real-time
- [ ] Auto-scrolls to bottom
- [ ] Color-codes line types
- [ ] Abort button works

---

### 7.6 Worktree Status Panel

**Description:** Show git worktree status for each epic.

**File:** `web-ui/src/components/WorktreePanel.tsx`

**Component:**

```typescript
interface Worktree {
  epicId: number;
  epicName: string;
  branch: string;
  status: 'active' | 'merged' | 'conflict';
  tasksCompleted: number;
  totalTasks: number;
  createdAt: string;
}

export function WorktreePanel({ worktrees }: { worktrees: Worktree[] }) {
  return (
    <div className="worktree-panel">
      <h2>Git Worktrees</h2>

      <div className="worktree-list">
        {worktrees.map(wt => (
          <div key={wt.epicId} className={`worktree-card ${wt.status}`}>
            <div className="worktree-header">
              <GitBranchIcon />
              <span className="branch-name">{wt.branch}</span>
              <StatusBadge status={wt.status} />
            </div>

            <div className="worktree-body">
              <span className="epic-name">{wt.epicName}</span>
              <ProgressBar
                value={wt.tasksCompleted}
                max={wt.totalTasks}
              />
              <span className="progress-label">
                {wt.tasksCompleted}/{wt.totalTasks} tasks
              </span>
            </div>

            <div className="worktree-actions">
              {wt.status === 'active' && (
                <button className="merge-btn">Merge</button>
              )}
              {wt.status === 'conflict' && (
                <button className="resolve-btn">Resolve</button>
              )}
              {wt.status === 'merged' && (
                <button className="cleanup-btn">Cleanup</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Shows all worktrees
- [ ] Status clearly visible
- [ ] Progress bars per epic
- [ ] Action buttons work

---

### 7.7 Enhanced Logging for Parallel Execution

**Description:** Extend observability module for parallel logs.

**File:** `core/observability.py` (extend)

**New Methods:**

```python
class ParallelLogger:
    """Extended logger for parallel execution"""

    def __init__(self, project_id: str, log_dir: Path):
        self.project_id = project_id
        self.log_dir = log_dir
        self.parallel_log = log_dir / "parallel_execution.jsonl"

    def log_batch_start(self, batch_number: int, task_ids: List[int]) -> None:
        """Log batch execution start"""
        self._write_event({
            "event": "batch_start",
            "batch_number": batch_number,
            "task_ids": task_ids,
            "timestamp": datetime.now().isoformat()
        })

    def log_agent_spawn(self, task_id: int, epic_id: int, worktree: str) -> None:
        """Log agent spawn event"""
        self._write_event({
            "event": "agent_spawn",
            "task_id": task_id,
            "epic_id": epic_id,
            "worktree": worktree,
            "timestamp": datetime.now().isoformat()
        })

    def log_agent_complete(
        self,
        task_id: int,
        success: bool,
        duration: float,
        tokens: Dict,
        cost: float
    ) -> None:
        """Log agent completion"""
        self._write_event({
            "event": "agent_complete",
            "task_id": task_id,
            "success": success,
            "duration_seconds": duration,
            "tokens": tokens,
            "cost_usd": cost,
            "timestamp": datetime.now().isoformat()
        })

    def log_merge_event(
        self,
        epic_id: int,
        branch: str,
        success: bool,
        conflicts: Optional[List[str]] = None
    ) -> None:
        """Log worktree merge event"""
        self._write_event({
            "event": "merge",
            "epic_id": epic_id,
            "branch": branch,
            "success": success,
            "conflicts": conflicts,
            "timestamp": datetime.now().isoformat()
        })

    def _write_event(self, event: Dict) -> None:
        """Write event to parallel log file"""
        with open(self.parallel_log, 'a') as f:
            f.write(json.dumps(event) + '\n')


def create_parallel_summary(project_id: str, log_dir: Path) -> Dict:
    """Create summary of parallel execution"""
    parallel_log = log_dir / "parallel_execution.jsonl"

    if not parallel_log.exists():
        return {}

    events = []
    with open(parallel_log) as f:
        for line in f:
            events.append(json.loads(line))

    # Analyze events
    batch_starts = [e for e in events if e['event'] == 'batch_start']
    agent_completes = [e for e in events if e['event'] == 'agent_complete']
    merges = [e for e in events if e['event'] == 'merge']

    return {
        "total_batches": len(batch_starts),
        "total_agents_spawned": len([e for e in events if e['event'] == 'agent_spawn']),
        "successful_tasks": len([e for e in agent_completes if e['success']]),
        "failed_tasks": len([e for e in agent_completes if not e['success']]),
        "total_duration": sum(e['duration_seconds'] for e in agent_completes),
        "total_cost": sum(e.get('cost_usd', 0) for e in agent_completes),
        "successful_merges": len([e for e in merges if e['success']]),
        "merge_conflicts": len([e for e in merges if not e['success']]),
    }
```

**Acceptance Criteria:**
- [ ] All events logged to JSONL
- [ ] Summary generation works
- [ ] Logs machine-readable
- [ ] Duration and cost tracked

---

## Testing Requirements

### Unit Tests

```python
class TestSwimlaneVisualization:
    def test_renders_correct_structure(self):
        """Renders all epics and tasks"""

    def test_task_positioning(self):
        """Tasks positioned in correct batch columns"""

class TestWebSocketEvents:
    def test_event_broadcast(self):
        """Events broadcast to correct project"""

    def test_event_serialization(self):
        """Events serialize correctly"""

class TestParallelLogger:
    def test_event_logging(self):
        """Events written to file"""

    def test_summary_generation(self):
        """Summary calculates correctly"""
```

### Integration Tests

```python
class TestDashboardIntegration:
    def test_real_time_updates(self):
        """Dashboard updates via WebSocket"""

    def test_cost_data_accuracy(self):
        """Cost dashboard shows correct data"""
```

---

## Dependencies

- Epic 01: Foundation (database views)
- Epic 04: Parallel Executor (emits events)

## Dependents

- None (end-user feature)

---

## Notes

- Consider performance of swimlane with many tasks
- WebSocket reconnection handling important
- May need pagination for large projects
- Consider dark mode support for terminals
