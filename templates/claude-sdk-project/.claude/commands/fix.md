# /fix - Fix Issues from Review

Automatically fix issues identified in a code review report.

## Usage

```
/fix <review-report>
/fix reviews/2026-01-07-review.md
/fix --priority blocker,high    # Only fix critical issues
```

## Process

1. **Load Review** - Parse review markdown
2. **Plan Fixes** - Order by risk tier (BLOCKER → LOW)
3. **Apply Fixes** - For each issue, apply suggested fix
4. **Verify** - Run tests after each file
5. **Report** - Output to `fix-reports/`

## Fix Priority

Default order:
1. BLOCKER - Always fix first
2. HIGH RISK - Fix next
3. MEDIUM RISK - If time permits
4. LOW RISK - If requested

## Output Format

```markdown
# Fix Report

**Source Review**: <review file>
**Status**: COMPLETE / PARTIAL

## Fixes Applied
### [Issue ID] <Title>
**File**: `path:line`
**Status**: FIXED / SKIPPED
**Change**: <diff or description>

## Verification Results
- Tests: X passed
- New issues: 0

## Summary
- Fixed: X
- Skipped: Y
```
