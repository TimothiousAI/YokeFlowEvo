# /orchestrate - Full Multi-Phase Workflow

Execute complete plan → build → review → fix workflow with parallel execution.

## Usage

```
/orchestrate <feature-description>
/orchestrate --plan specs/existing-plan.md
/orchestrate --resume <session-id>
```

## Phases

### Phase 1: Planning
1. Spawn **planner-agent** (Opus)
2. Analyze requirements and codebase
3. Generate detailed spec in `specs/<feature>.md`
4. Identify parallel batches

### Phase 2: Building
1. For each batch:
   - Create worktrees for all tasks
   - Spawn **build-agent** per worktree (Sonnet)
   - Wait for batch completion
   - Merge and validate

### Phase 3: Review
1. Spawn **reviewer-agent** (Sonnet)
2. Review all changes made
3. Generate risk-tiered report
4. Output to `reviews/<timestamp>.md`

### Phase 4: Fix (if needed)
1. If review has BLOCKER or HIGH issues:
   - Parse review report
   - Apply fixes in priority order
   - Re-run affected tests
2. Output to `fix-reports/<timestamp>.md`

### Phase 5: Finalize
1. Run full test suite
2. Generate final report
3. Commit with detailed message
4. Cleanup worktrees

## Workflow Diagram

```
/orchestrate "Add execution plan feature"
        │
        ▼
┌─────────────────┐
│  PHASE 1: PLAN  │ ← planner-agent (Opus)
│  Generate spec  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PHASE 2: BUILD  │ ← build-agents (Sonnet) × N
│ Parallel exec   │
│ Merge validate  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PHASE 3: REVIEW │ ← reviewer-agent (Sonnet)
│ Risk assessment │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Issues? │
    └────┬────┘
    Yes  │  No
    ▼    │
┌───────┐│
│ FIX   ││
│ phase ││
└───┬───┘│
    │    │
    ▼    ▼
┌─────────────────┐
│ PHASE 5: FINAL  │
│ Tests, commit   │
└─────────────────┘
```

## Output Format

```markdown
## Orchestration Report

**Feature**: Add execution plan building
**Started**: 2026-01-06 10:00:00
**Completed**: 2026-01-06 11:30:00
**Status**: SUCCESS

### Phase 1: Planning
**Agent**: planner-agent
**Duration**: 8m 30s
**Output**: specs/execution-plan-builder.md
**Batches Identified**: 3

### Phase 2: Building
**Total Batches**: 3
**Total Tasks**: 8
**Duration**: 45m 20s

| Batch | Tasks | Duration | Merge Status |
|-------|-------|----------|--------------|
| 1 | 3 | 12m | SUCCESS |
| 2 | 3 | 18m | SUCCESS |
| 3 | 2 | 15m | SUCCESS |

### Phase 3: Review
**Agent**: reviewer-agent
**Duration**: 5m 15s
**Output**: reviews/2026-01-06-1100.md
**Verdict**: PASS (0 blockers, 1 high, 3 medium)

### Phase 4: Fix
**Triggered**: Yes (1 HIGH issue)
**Duration**: 8m 45s
**Fixed**: 1/1 high, 2/3 medium
**Output**: fix-reports/2026-01-06-1108.md

### Phase 5: Finalize
**Tests**: 67 passed, 0 failed
**Commit**: abc123f "feat: Add execution plan building"

### Summary
- Planning: 8m 30s
- Building: 45m 20s (parallel efficiency: 35%)
- Review: 5m 15s
- Fix: 8m 45s
- Total: 1h 7m 50s
- Sequential estimate: ~2h 15m
- Time saved: ~1h 7m
```

## Resume Capability

If orchestration is interrupted:

```
/orchestrate --resume orch-2026-01-06-1000
```

Resumes from last completed phase using saved state in `.claude/orchestration-state/`.

## Configuration

In `.claude/settings.json`:

```json
{
  "orchestration": {
    "auto_fix_threshold": "high",    // Fix HIGH and above automatically
    "require_review_pass": true,     // Must pass review before finalize
    "max_fix_iterations": 3,         // Max fix attempts
    "parallel_efficiency_target": 0.3 // 30% time savings goal
  }
}
```
