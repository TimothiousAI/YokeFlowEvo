# /build - Execute Implementation Plan

Implement features from a plan specification.

## Usage

```
/build <plan-file>
/build specs/feature.md
```

## Process

1. **Load Plan** - Read spec from `specs/<name>.md`
2. **Gather Context** - Read related files and expertise
3. **Execute** - Implement each file specification
4. **Verify** - Run validation commands
5. **Report** - Output to `build-reports/`

## For Each File

The build agent receives:
- Purpose and requirements
- Related files for context
- Patterns from expertise.yaml
- Validation commands

## Output Format

```markdown
# Build Report: <Plan Name>

**Status**: SUCCESS / PARTIAL / FAILED

## Files Processed
| File | Status | Notes |
|------|--------|-------|

## Verification Results
- Tests: X passed, Y failed
- Type check: Results

## Issues Encountered
- Issue details or "None"
```
