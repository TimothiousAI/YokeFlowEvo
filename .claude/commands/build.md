# /build - Execute Implementation Plan

Implement features from a plan specification, optionally in parallel.

## Usage

```
/build <plan-file>
/build specs/execution-plan-builder.md
/build --parallel specs/feature.md
```

## Process

1. **Load Plan**
   - Read plan spec from `specs/<name>.md`
   - Parse file specifications and phases
   - Identify dependencies between files

2. **Gather Context**
   - Read all related files mentioned in plan
   - Load relevant domain expertise
   - Understand existing code patterns

3. **Determine Execution Mode**
   - **Sequential**: Files with dependencies
   - **Parallel**: Independent files in same phase

4. **For Each File Specification**
   - Create comprehensive context for build-agent
   - Include: purpose, requirements, related files, patterns, examples
   - Launch agent (parallel if no dependencies)

5. **Verify Each Implementation**
   - Run specified validation commands
   - Check type safety
   - Verify tests pass

6. **Report Completion**
   - Output to `build-reports/<plan-name>-<timestamp>.md`
   - List all files created/modified
   - Note any issues encountered

## Parallel Execution Pattern

When `--parallel` flag is used:

```
Phase 1: Analyze all files for dependencies
Phase 2: Group into batches (independent files together)
Phase 3: Launch entire batch in single message with multiple Task calls
Phase 4: Wait for all to complete before next batch
```

## File Specification Format (Input)

Each file in the plan should have:

```markdown
### File: path/to/file.py

**Purpose**: Single sentence describing what this file does

**Requirements**:
- Detailed requirement 1
- Detailed requirement 2 with specifics

**Related Files**:
- `other/file.py` - How it relates (imports, extends, etc.)

**Code Style & Patterns**:
- Follow async/await pattern from backend expertise
- Use Pydantic models for validation

**Dependencies**:
- asyncpg for database
- fastapi for routing

**Example Code**:
```python
# Reference implementation or pattern to follow
async def example():
    pass
```

**Integration Points**:
- Called by: orchestrator.py
- Calls: database.py methods

**Verification**:
```bash
pytest tests/test_file.py -v
python -m mypy path/to/file.py
```
```

## Output Format

```markdown
# Build Report: <Plan Name>

**Started**: 2026-01-06 10:00:00
**Completed**: 2026-01-06 10:15:00
**Status**: SUCCESS / PARTIAL / FAILED

## Files Processed

| File | Status | Notes |
|------|--------|-------|
| path/to/file1.py | Created | All tests pass |
| path/to/file2.py | Modified | Type check warnings |

## Verification Results

- pytest: 15 passed, 0 failed
- mypy: 0 errors, 2 warnings
- Integration: All endpoints responding

## Issues Encountered
- None / List of issues

## Next Steps
- Run /review to validate changes
```
