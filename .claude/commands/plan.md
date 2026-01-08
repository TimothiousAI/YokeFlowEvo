# /plan - Generate Implementation Plan

Generate a detailed implementation plan for a feature or task.

## Usage

```
/plan <feature description>
/plan --file <task_file.md>
```

## Process

1. **Analyze Requirements**
   - Parse the feature description or task file
   - Identify core objectives and constraints
   - Determine affected domains (backend, frontend, database, etc.)

2. **Consult Domain Experts**
   - Read `.claude/commands/experts/{domain}/expertise.yaml` for each affected domain
   - Identify relevant patterns and anti-patterns
   - Note existing code conventions

3. **Design Approach**
   - Identify all files that need modification or creation
   - Determine dependencies between changes
   - Plan parallel vs sequential execution

4. **Generate Plan Spec**
   - Output to `specs/<feature-name>.md`
   - Include all sections below

## Output Format

```markdown
# Plan: <Feature Name>

## Task Description
<What we're building and why>

## Objectives
- [ ] Objective 1
- [ ] Objective 2

## Relevant Files
| File | Purpose | Action |
|------|---------|--------|
| path/to/file.py | Description | Create/Modify |

## Implementation Phases

### Phase 1: <Name>
- Task 1.1: Description
- Task 1.2: Description

### Phase 2: <Name>
- Task 2.1: Description (depends on 1.1)

## File Specifications

### File: <path/to/file.py>
**Purpose**: What this file does
**Requirements**:
- Requirement 1
- Requirement 2
**Related Files**: `other/file.py` (imports from)
**Patterns to Follow**: From `{domain}/expertise.yaml`

## Testing Strategy
- Unit tests for X
- Integration tests for Y
- Browser verification for Z

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Validation Commands
```bash
pytest tests/test_feature.py
python -m mypy path/to/file.py
```
```

## Example

```
/plan Add execution plan building to Session 0
```

Generates `specs/execution-plan-builder.md` with full implementation details.
