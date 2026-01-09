# Code Review Report

**Date**: 2026-01-09
**Reviewer**: Claude (automated)
**Scope**: 12 files changed, +842 -227 lines
**Feature**: Parallel Execution System Redesign

## Verdict: PASS

## Summary

| Risk Level | Count |
|------------|-------|
| Blockers   | 0     |
| High Risk  | 2     |
| Medium Risk| 4     |
| Low Risk   | 5     |

## Issues

### BLOCKER
None found.

---

### HIGH RISK

#### [HR-1] Missing dependency array values in useEffect
**File**: `web-ui/src/components/parallel/SessionDetailModal.tsx:101-105`
**Issue**: The `loadLogs` function is called inside useEffect but not included in the dependency array. This can cause stale closures.
**Impact**: Logs may not reload correctly when session changes, or may reference stale `session` values.
**Fix**: Add `loadLogs` to dependency array or use `useCallback`:
```typescript
// Current (problematic)
useEffect(() => {
  if (isOpen && activeTab === 'logs' && session?.sessionId) {
    loadLogs();
  }
}, [isOpen, activeTab, session?.sessionId]);

// Suggested fix - use useCallback
const loadLogs = useCallback(async () => {
  // ... implementation
}, [projectId, session?.taskId, session?.sessionId]);

useEffect(() => {
  if (isOpen && activeTab === 'logs' && session?.sessionId) {
    loadLogs();
  }
}, [isOpen, activeTab, session?.sessionId, loadLogs]);
```

#### [HR-2] Potential memory leak with setTimeout in useParallelState
**File**: `web-ui/src/components/parallel/hooks/useParallelState.ts:334-340`
**Issue**: The `setTimeout` for removing completed sessions after 3 seconds is not cleaned up if component unmounts.
**Impact**: Can cause React state update warnings on unmounted components, potential memory leaks.
**Fix**: Store timeout ID and clear on cleanup:
```typescript
// Current (problematic)
setTimeout(() => {
  setRunningSessions(prev => {
    const updated = new Map(prev);
    updated.delete(message.task_id);
    return updated;
  });
}, 3000);

// Suggested fix
const timeoutRef = useRef<Set<NodeJS.Timeout>>(new Set());

// In handler:
const timeoutId = setTimeout(() => {
  setRunningSessions(prev => {
    const updated = new Map(prev);
    updated.delete(message.task_id);
    return updated;
  });
  timeoutRef.current.delete(timeoutId);
}, 3000);
timeoutRef.current.add(timeoutId);

// Add cleanup effect:
useEffect(() => {
  return () => {
    timeoutRef.current.forEach(id => clearTimeout(id));
  };
}, []);
```

---

### MEDIUM RISK

#### [MR-1] Hash collision potential for session numbers
**File**: `core/parallel/parallel_executor.py:506`
**Issue**: Using `abs(hash((str(self.execution_run_id), task_id))) % (10**9)` for session numbers could theoretically cause collisions, though extremely unlikely in practice.
**Impact**: If two tasks generate the same session number, database conflicts could occur.
**Fix**: Consider using a more robust approach:
```python
# Alternative: Use UUID directly or combine timestamp
import hashlib
session_hash = hashlib.sha256(f"{self.execution_run_id}-{task_id}".encode()).hexdigest()[:8]
session_number = int(session_hash, 16) % (10**9)
```

#### [MR-2] Incomplete feature stubs in SessionDetailModal
**File**: `web-ui/src/components/parallel/SessionDetailModal.tsx:371-464`
**Issue**: History, Quality, and Costs tabs are stubbed with "Coming soon" placeholders but are still visible and clickable.
**Impact**: Users may expect these features to work. Creates technical debt.
**Recommendation**: Either:
1. Hide tabs until implemented
2. Add a clear "Not Yet Available" badge on tab
3. Track in TODO/roadmap

#### [MR-3] Logs lookup logic may not find correct session
**File**: `web-ui/src/components/parallel/SessionDetailModal.tsx:121-124`
**Issue**: Log file matching uses both `session_${session.taskId}` pattern and `session_number === session.taskId`. The relationship between taskId and session_number may not always match.
**Impact**: Users may see incorrect logs or "No logs available" when logs exist.
**Fix**: Review the log naming convention and ensure consistent matching:
```typescript
// Consider matching by session ID if available
const humanLog = logsList.find((l: any) =>
  l.session_id === session.sessionId ||  // Prefer exact match
  l.filename.includes(`session_${session.taskId}`) ||
  l.session_number === session.taskId
);
```

#### [MR-4] No error handling for worktree creation failures
**File**: `core/parallel/parallel_executor.py:338-343`
**Issue**: When worktree creation fails for an epic, execution continues but tasks for that epic will silently be skipped.
**Impact**: Users may not realize their tasks are being skipped due to worktree issues.
**Fix**: Emit an error event or mark tasks as failed:
```python
except Exception as e:
    logger.error(f"Failed to create worktree for epic {epic_id}: {e}")
    # Emit failure event for UI
    if self.progress_callback:
        for task in tasks:
            await self.progress_callback({
                "type": "task_error",
                "task_id": task.get('id'),
                "error": f"Worktree creation failed: {e}"
            })
    # Continue with other epics
```

---

### LOW RISK

#### [LR-1] Duplicated `formatToolName` function
**Files**:
- `web-ui/src/components/parallel/SessionCard.tsx:60-68`
- `web-ui/src/components/parallel/SessionDetailModal.tsx:55-62`
**Issue**: Same function defined in two places.
**Impact**: Maintenance overhead; changes must be made in two places.
**Fix**: Extract to shared utility:
```typescript
// lib/format.ts
export function formatToolName(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .trim()
    .toLowerCase()
    .replace(/^./, s => s.toUpperCase());
}
```

#### [LR-2] Duplicated `formatDuration` and `formatModel` functions
**Files**:
- `web-ui/src/components/parallel/SessionCard.tsx:26-41`
- `web-ui/src/components/parallel/SessionDetailModal.tsx:38-53`
**Issue**: Same formatting functions duplicated.
**Impact**: Code duplication.
**Fix**: Extract to shared utilities.

#### [LR-3] Duplicated `getPhaseColor` function
**Files**:
- `web-ui/src/components/parallel/SessionCard.tsx:43-58`
- `web-ui/src/components/parallel/SessionDetailModal.tsx:64-79`
**Issue**: Same styling function duplicated.
**Impact**: Code duplication; style changes require multiple edits.
**Fix**: Extract to shared component utilities.

#### [LR-4] Console.log statement left in code
**File**: `web-ui/src/components/parallel/BatchExecutionView.tsx:361`
**Issue**: Debug `console.log('Stop task:', taskId)` left in production code.
**Impact**: Clutters browser console; minor professionalism issue.
**Fix**: Remove or convert to proper logging.

#### [LR-5] Unused `start_time.isoformat()` attribute access
**File**: `core/parallel/parallel_executor.py:510`
**Issue**: `start_time` is a float (from `time.time()`), not a datetime object, so `.isoformat()` will fail.
**Impact**: Runtime error when emitting agent_start event.
**Fix**:
```python
# Current (broken)
"started_at": start_time.isoformat()

# Fixed
"started_at": datetime.fromtimestamp(start_time).isoformat()
```

---

## Positive Observations

1. **Clean Architecture**: The new execution model correctly separates epic-level parallelism from task-level sequencing.

2. **Good Logging**: Extensive logging throughout `parallel_executor.py` makes debugging straightforward.

3. **Consistent UI Patterns**: SessionDetailModal follows established patterns from other components.

4. **Type Safety**: TypeScript interfaces are well-defined in `useParallelState.ts`.

5. **Graceful Degradation**: Failed tasks within an epic don't block other tasks in that epic.

6. **Cancel Support**: Cancellation is checked before each task, allowing clean shutdown.

---

## Recommendations

1. **Fix HR-1 and LR-5 before merging** - These will cause runtime errors.

2. **Consider HR-2** - Memory leak potential should be addressed for long-running sessions.

3. **Extract duplicate utilities** - Create `web-ui/src/lib/format.ts` for shared formatting functions.

4. **Add tests for the new execution model** - The epic-parallel/task-sequential model is critical and should have unit tests.

5. **Document the execution model** - Add comments or docs explaining why epics run parallel but tasks are sequential.

---

## Files Reviewed

| File | Status | Notes |
|------|--------|-------|
| `core/parallel/parallel_executor.py` | Modified | Core execution model change - well implemented |
| `web-ui/src/components/parallel/SessionDetailModal.tsx` | New | Good structure, needs useCallback fixes |
| `web-ui/src/components/parallel/SessionCard.tsx` | Modified | Clickable cards work well |
| `web-ui/src/components/parallel/BatchExecutionView.tsx` | Modified | Modal integration correct |
| `web-ui/src/components/parallel/hooks/useParallelState.ts` | Modified | Good WebSocket handling |
| `api/main.py` | Modified | Not reviewed in detail |
| `core/database.py` | Modified | Not reviewed in detail |
| `core/execution_plan.py` | Modified | Not reviewed in detail |
| `core/orchestrator.py` | Modified | Not reviewed in detail |
| `core/parallel/worktree_manager.py` | Modified | Not reviewed in detail |
| `web-ui/src/app/projects/[id]/page.tsx` | Modified | Not reviewed in detail |
| `web-ui/src/lib/types.ts` | Modified | Type additions look correct |
| `web-ui/src/lib/websocket.ts` | Modified | Not reviewed in detail |

---

## Action Items

| Priority | Issue | Action | Status |
|----------|-------|--------|--------|
| **Critical** | LR-5 | Fix `start_time.isoformat()` - will cause runtime error | **FIXED** |
| **Low** | LR-4 | Remove console.log statement | **FIXED** |
| **High** | HR-1 | Add missing useEffect dependencies | Open |
| **High** | HR-2 | Add setTimeout cleanup on unmount | Open |
| **Medium** | MR-1-4 | Address during next iteration | Open |
| **Low** | LR-1-3 | Nice to fix, batch in cleanup PR | Open |

---

## Post-Review Fixes Applied

1. **LR-5 Fixed**: Changed `start_time.isoformat()` to `datetime.fromtimestamp(start_time).isoformat()` in `parallel_executor.py:540`

2. **LR-4 Fixed**: Removed `console.log('Stop task:', taskId)` and replaced with TODO comment in `BatchExecutionView.tsx:360-361`
