# /parallel - Launch Parallel Sub-Agents

Launch multiple agents simultaneously for parallel task execution.

## Usage

```
/parallel <plan-file>              # Execute plan in parallel batches
/parallel --agents <n> <task>      # Launch N agents for same task type
/parallel --batch <batch-num>      # Execute specific batch from plan
```

## Process

1. **Load Execution Plan**
   - Read plan from `specs/<name>.md` or database
   - Identify batches and their tasks
   - Verify dependencies are satisfied

2. **Create Worktrees**
   - For each task in batch, create isolated worktree
   - Branch naming: `feature/<project>-<batch>-<task>`
   - Maximum 4 concurrent worktrees (configurable)

3. **Launch Agents**
   - All agents in a batch launch simultaneously
   - Each agent gets full context specification
   - Use appropriate agent type (build-agent, scout-agent, etc.)

4. **Monitor Completion**
   - Track status of each agent
   - Log progress to swimlane visualization
   - Handle failures gracefully

5. **Batch Completion**
   - Wait for ALL agents in batch to complete
   - Trigger merge validation
   - Advance to next batch only after merge succeeds

## Parallel Execution Pattern

```
Batch 1: [Task A, Task B, Task C] -- All start simultaneously
         ↓ (wait for all)
Merge Validation: Test merged code
         ↓ (if pass)
Batch 2: [Task D, Task E] -- Start after Batch 1 complete
         ↓ (wait for all)
Merge Validation: Test merged code
         ↓
Continue...
```

## Worktree Management

```bash
# Create worktree for task
git worktree add .worktrees/batch1-task-a -b feature/proj-b1-a

# Agent works in isolated directory
cd .worktrees/batch1-task-a
# ... implementation ...

# After completion, merge back
git checkout main
git merge feature/proj-b1-a --no-ff

# Cleanup
git worktree remove .worktrees/batch1-task-a
git branch -d feature/proj-b1-a
```

## Agent Dispatch

Each agent receives a comprehensive specification:

```markdown
## Task Specification

**Task ID**: <uuid>
**Worktree**: .worktrees/batch1-task-a
**Branch**: feature/proj-b1-a

### File: path/to/file.py

**Purpose**: <what this file does>

**Requirements**:
- Requirement 1
- Requirement 2

**Related Files**:
- other/file.py (import patterns)

**Patterns**:
- Use async/await
- Follow backend expertise

**Validation**:
```bash
pytest tests/test_file.py
```
```

## Output Format

```markdown
## Parallel Execution Report

**Plan**: specs/feature-x.md
**Started**: 2026-01-06 10:00:00
**Completed**: 2026-01-06 10:30:00

### Batch 1 (Parallel)
| Task | Worktree | Agent | Status | Duration |
|------|----------|-------|--------|----------|
| Create schema | batch1-schema | build-agent | SUCCESS | 2m 15s |
| Create models | batch1-models | build-agent | SUCCESS | 3m 42s |
| Add migration | batch1-migration | build-agent | SUCCESS | 1m 30s |

**Merge Status**: SUCCESS
**Tests After Merge**: 45 passed

### Batch 2 (Parallel)
| Task | Worktree | Agent | Status | Duration |
|------|----------|-------|--------|----------|
| API endpoints | batch2-api | build-agent | SUCCESS | 5m 10s |
| Service layer | batch2-service | build-agent | SUCCESS | 4m 55s |

**Merge Status**: SUCCESS
**Tests After Merge**: 52 passed

### Summary
- Total batches: 2
- Total tasks: 5
- Total time: 30m (vs 45m sequential = 33% faster)
- All merges successful
```

## Error Handling

### Agent Failure
- Log failure with details
- Continue other agents in batch
- Report partial completion
- Allow manual intervention

### Merge Conflict
- Spawn merge-agent to resolve
- If unresolvable, pause execution
- Report conflict details
- Wait for human decision

### Test Failure After Merge
- Do NOT proceed to next batch
- Report failing tests
- Spawn reviewer-agent to diagnose
- Allow fix and retry
