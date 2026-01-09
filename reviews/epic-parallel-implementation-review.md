# Code Review Report: Parallel-First Epic Design Implementation

**Date**: 2026-01-09  
**Scope**: 5 core files changed, ~300 lines added/modified  
**Reviewer**: Claude Code Reviewer Agent  
**Verdict**: **PASS WITH CONDITIONS** (2 HIGH RISK issues must be addressed)

## Executive Summary

| Risk Level | Count |
|------------|-------|
| BLOCKER    | 0     |
| HIGH       | 2     |
| MEDIUM     | 4     |
| LOW        | 3     |

This implementation adds valuable epic-level parallel execution support with a well-designed layer-centric approach that mirrors real-world team workflows. The core architecture is sound, but two HIGH RISK issues (SQL injection and missing cycle detection) must be fixed before merge.

## Changed Files

1. schema/postgresql/schema.sql - Added epic_type, depends_on_epics, domain columns
2. prompts/initializer_prompt_docker.md - Added Epic Design guidance (~100 lines)
3. core/database.py - Epic dependency methods (~60 lines)
4. core/execution_plan.py - Epic-based planning logic (~200 lines)
5. api/main.py - Execution plan endpoint enhancements (minimal)

**Lines Reviewed**: ~10,000 total  
**Net New Logic**: ~300 lines  
**Test Coverage**: 0% (no tests for new functionality)

---

## HIGH RISK Issues

### [HR-1] SQL Injection in update_epic()

**File**: core/database.py:1203-1240

**Issue**: Dynamic SQL with unvalidated column names from kwargs

**Vulnerable Code**:
```python
for key, value in kwargs.items():
    set_clauses.append(f"{key} = ${param_num}")  # Unvalidated key
```

**Attack**: update_epic(epic_id=1, **{"name'; DROP TABLE epics; --": "x"})

**Fix**: Add whitelist validation:
```python
ALLOWED_FIELDS = {
    'name', 'description', 'priority', 'status',
    'epic_type', 'domain', 'depends_on_epics'
}
invalid_keys = set(kwargs.keys()) - ALLOWED_FIELDS
if invalid_keys:
    raise ValueError(f"Invalid fields: {invalid_keys}")
```

---

### [HR-2] Missing Cycle Detection

**File**: core/execution_plan.py:734-786

**Issue**: Circular dependencies only logged, not prevented

**Problem**: Epic A depends on B, B depends on A = deadlock

**Impact**: Execution plan with incorrect ordering, batches never complete

**Fix**: Raise exception instead of logging:
```python
if len(sorted_epic_ids) != len(epics):
    remaining = [e for e in epics if e["id"] not in sorted_epic_ids]
    cycle_names = [e.get("name") for e in remaining]
    raise ValueError(
        f"Circular dependency: {', '.join(cycle_names)}"
    )
```

---

## MEDIUM RISK Issues

### [MR-1] Incomplete Error Handling in build_plan()
**File**: core/execution_plan.py:163-410  
**Issue**: No try-catch around database/analysis steps  
**Impact**: Partial execution plan on failure

### [MR-2] No Validation of epic_type/domain
**File**: core/database.py:1042-1090  
**Issue**: Invalid values cause DB constraint errors  
**Fix**: Validate against whitelists before insert

### [MR-3] N+1 Query in _update_task_predicted_files()
**File**: core/execution_plan.py:843-854  
**Issue**: Updates tasks one-by-one (100 tasks = 100 queries)  
**Fix**: Use executemany() for batch update

### [MR-4] No Migration Documentation
**File**: schema/postgresql/schema.sql  
**Issue**: Existing projects default to epic_type='parallel'  
**Impact**: Incorrect execution plans without re-initialization

---

## LOW RISK Issues

- [LR-1] Confusing "batch" vs "epic" terminology
- [LR-2] Undocumented file pattern regex rationale
- [LR-3] Generic progress callback error messages

---

## Positive Observations

1. **Excellent Design**: Layer-centric approach matches real teams
2. **Backward Compatible**: Task-based planning fallback maintained
3. **Clear Guidance**: Initializer prompt provides actionable steps
4. **Good DB Design**: Appropriate indexes, CHECK constraints, array columns
5. **Clean Code**: Well-separated epic-based vs task-based logic

---

## Testing Gaps

**Zero test coverage** for new functionality. Need:
- Unit tests for cycle detection
- Integration tests for epic-based planning
- Validation tests for epic_type/domain

---

## Recommendations

### BEFORE MERGE (REQUIRED)
1. Fix [HR-1] - Add whitelist validation to update_epic()
2. Fix [HR-2] - Raise exception on circular dependencies
3. Add basic tests for cycle detection and validation

### AFTER MERGE (HIGH PRIORITY)
1. Fix [MR-3] - Batch task updates
2. Fix [MR-1] - Add error handling
3. Fix [MR-4] - Document migration strategy
4. Fix [MR-2] - Validate epic_type/domain

---

## File-by-File Summary

**schema.sql**: Good, proper indexes/constraints  
**initializer_prompt.md**: Excellent, clear guidance  
**database.py**: HR-1 SQL injection, MR-2 missing validation  
**execution_plan.py**: HR-2 no cycle detection, MR-3 N+1 query  
**api/main.py**: Good, minimal changes

---

## Verdict Rationale

**PASS WITH CONDITIONS**:
- No blockers (no data loss, crashes, or critical security holes)
- Architecture is sound and well-designed
- 2 HIGH RISK issues are straightforward to fix
- Overall implementation quality is good

**Merge after addressing HR-1 and HR-2.**

---

**Reviewed by**: Claude Code Reviewer Agent (Sonnet 4.5)  
**Review Duration**: 30 minutes  
**Date**: 2026-01-09
