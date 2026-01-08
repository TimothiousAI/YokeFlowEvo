# /review - Risk-Tiered Code Review

Perform comprehensive code review with risk-based issue classification.

## Usage

```
/review                     # Review uncommitted changes
/review --staged            # Review staged changes only
/review --commit <sha>      # Review specific commit
/review --pr <number>       # Review pull request
```

## Process

1. **Gather Changes**
   - Get diff of changes (staged, uncommitted, or specified)
   - Identify all modified files
   - Load relevant domain expertise for each file

2. **Analyze Each File**
   - Check against domain patterns
   - Identify anti-patterns
   - Verify code style consistency
   - Check for security issues

3. **Classify Issues by Risk**
   - **BLOCKER**: Must fix before merge
   - **HIGH RISK**: Should fix, significant impact
   - **MEDIUM RISK**: Should fix, moderate impact
   - **LOW RISK**: Nice to fix, minor impact

4. **Generate Report**
   - Output to `reviews/<timestamp>-review.md`
   - Include verdict (PASS/FAIL)
   - List all issues with locations

## Risk Tier Definitions

### BLOCKER (Must Fix)
- Security vulnerabilities (SQL injection, XSS, etc.)
- Data loss potential
- Application crashes
- Missing database migrations
- Breaking API changes without versioning
- Credentials or secrets in code

### HIGH RISK (Should Fix)
- Performance issues (N+1 queries, blocking calls in async)
- Incomplete feature implementation
- Missing error handling for critical paths
- Race conditions
- Memory leaks

### MEDIUM RISK (Consider Fixing)
- Code duplication
- Missing tests for new functionality
- Technical debt introduction
- Inconsistent patterns
- Missing input validation

### LOW RISK (Nice to Have)
- Code style inconsistencies
- Missing or outdated comments
- Minor refactoring opportunities
- Unused imports
- Naming conventions

## Output Format

```markdown
# Code Review Report

**Date**: 2026-01-06 10:30:00
**Reviewer**: Claude (automated)
**Scope**: 5 files changed, +150 -30 lines

## Verdict: PASS / FAIL

## Summary
- Blockers: 0
- High Risk: 1
- Medium Risk: 3
- Low Risk: 5

## Issues

### BLOCKER
None found.

### HIGH RISK

#### [HR-1] Blocking call in async function
**File**: `core/execution_plan.py:45`
**Issue**: Using `requests.get()` in async function
**Impact**: Will block event loop, degrading performance
**Fix**: Use `httpx.AsyncClient` instead
```python
# Current (bad)
response = requests.get(url)

# Suggested (good)
async with httpx.AsyncClient() as client:
    response = await client.get(url)
```

### MEDIUM RISK

#### [MR-1] Missing test coverage
**File**: `core/execution_plan.py`
**Issue**: New `build_plan()` function has no tests
**Impact**: Regression risk
**Fix**: Add tests to `tests/test_execution_plan.py`

### LOW RISK

#### [LR-1] Inconsistent naming
**File**: `core/execution_plan.py:12`
**Issue**: Variable `ep` should be `execution_plan` for clarity
**Impact**: Readability

## Recommendations
1. Address HIGH RISK issue before merging
2. Consider adding tests for new functionality
3. Minor style fixes can be batched

## Files Reviewed
- core/execution_plan.py (modified)
- core/orchestrator.py (modified)
- api/main.py (modified)
- tests/test_execution_plan.py (new)
```

## Integration with /fix

After review, run `/fix reviews/<timestamp>-review.md` to automatically address issues.
