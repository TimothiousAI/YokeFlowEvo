# /fix - Fix Issues from Review

Automatically fix issues identified in a code review report.

## Usage

```
/fix <review-report>
/fix reviews/2026-01-06-review.md
/fix --priority blocker,high    # Only fix critical issues
/fix --dry-run                   # Show what would be fixed
```

## Process

1. **Load Review Report**
   - Parse review markdown from `reviews/<file>.md`
   - Extract all issues with locations and suggested fixes
   - Prioritize by risk tier

2. **Plan Fixes**
   - Group issues by file
   - Order by: BLOCKER → HIGH → MEDIUM → LOW
   - Identify dependencies between fixes

3. **Apply Fixes**
   - For each issue:
     - Read current file state
     - Apply suggested fix
     - Verify fix doesn't break other code
   - Run validation after each file

4. **Verify All Fixes**
   - Run test suite
   - Run type checker
   - Verify no new issues introduced

5. **Generate Report**
   - Output to `fix-reports/<timestamp>-fix.md`
   - List all applied fixes
   - Note any that couldn't be applied

## Fix Priority

Default order (all tiers):
1. BLOCKER - Always fix first
2. HIGH RISK - Fix next
3. MEDIUM RISK - Fix if time permits
4. LOW RISK - Fix if requested

Use `--priority` to limit scope:
```
/fix report.md --priority blocker        # Only blockers
/fix report.md --priority blocker,high   # Blockers and high risk
```

## Output Format

```markdown
# Fix Report

**Date**: 2026-01-06 11:00:00
**Source Review**: reviews/2026-01-06-review.md
**Status**: COMPLETE / PARTIAL

## Fixes Applied

### [HR-1] Blocking call in async function
**File**: `core/execution_plan.py:45`
**Status**: FIXED
**Change**:
```diff
- response = requests.get(url)
+ async with httpx.AsyncClient() as client:
+     response = await client.get(url)
```

### [MR-1] Missing test coverage
**File**: `tests/test_execution_plan.py`
**Status**: FIXED
**Change**: Added 3 new test cases

### [LR-1] Inconsistent naming
**File**: `core/execution_plan.py:12`
**Status**: SKIPPED (low priority)

## Verification Results

- pytest: 18 passed, 0 failed
- mypy: 0 errors
- New issues: 0

## Summary
- Total issues: 9
- Fixed: 4
- Skipped: 5 (low priority)

## Next Steps
- Run /review to verify no new issues
- Commit changes with descriptive message
```

## Dry Run Mode

Use `--dry-run` to preview fixes without applying:

```
/fix report.md --dry-run
```

Shows what would be changed without modifying files.
