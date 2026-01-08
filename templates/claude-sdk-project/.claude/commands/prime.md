# /prime - Context Priming

Load project context for effective development.

## Usage

```
/prime
```

## What This Does

Reads essential files to understand:
1. **CLAUDE.md** - Project overview and guidelines
2. **Domain expertise** - Patterns and anti-patterns
3. **Current state** - Active tasks and progress

## After Priming

You should understand:
- Project purpose and architecture
- Available domains and their expertise
- How to use /plan, /build, /review, /fix
- Where to find and update patterns

## Development Workflow

1. **Before coding**: Consult domain expertise
2. **For features**: /plan → /build → /review
3. **After implementation**: Update expertise.yaml with new patterns

## Key Directories

- `.claude/commands/experts/` - Domain knowledge
- `.claude/agents/` - Sub-agent definitions
- `specs/` - Implementation plans
- `reviews/` - Code review reports
