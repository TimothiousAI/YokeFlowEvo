# /plan - Generate Implementation Plan

Generate a detailed implementation plan for a feature or task.

## Usage

```
/plan <feature description>
```

## Process

1. **Analyze Requirements** - Parse the feature description
2. **Consult Domain Experts** - Read relevant `expertise.yaml` files
3. **Design Approach** - Identify files to create/modify
4. **Generate Plan** - Output to `specs/<feature-name>.md`

## Output Format

```markdown
# Plan: <Feature Name>

## Task Description
<What we're building>

## Objectives
- [ ] Objective 1
- [ ] Objective 2

## Relevant Files
| File | Purpose | Action |
|------|---------|--------|

## Implementation Phases
### Phase 1: <Name>
- Task 1.1
- Task 1.2

## File Specifications
### File: <path>
**Purpose**: ...
**Requirements**: ...
**Patterns**: From expertise.yaml

## Testing Strategy
- Unit tests for X
- Integration tests for Y

## Validation Commands
```bash
# Commands to verify implementation
```
```
