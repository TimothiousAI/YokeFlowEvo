---
name: implement-feature
description: Implement a new feature in YokeFlow following established patterns
---

# Implement Feature Skill

Use this skill when implementing new features in YokeFlow.

## Process

1. **Identify Domain**
   - Backend (API endpoints, async operations)
   - Frontend (UI components, pages)
   - Database (schema, queries)
   - Orchestration (agent management)
   - MCP (tool definitions)
   - Testing (pytest tests)

2. **Consult Domain Expertise**
   - Read `.claude/commands/experts/{domain}/expertise.yaml`
   - Follow established patterns
   - Avoid documented anti-patterns

3. **Implementation Steps**
   - Start with database schema if needed
   - Implement core logic
   - Add API endpoints
   - Create UI components
   - Write tests

4. **Update Expertise**
   - If new pattern discovered, add to expertise.yaml
   - Increment usage_count
   - Update last_updated timestamp

## Key Files by Domain

| Domain | Key Files |
|--------|-----------|
| Backend | `api/main.py`, `core/*.py` |
| Frontend | `web-ui/src/` |
| Database | `core/database.py`, `schema/` |
| Orchestration | `core/orchestrator.py`, `core/agent.py` |
| MCP | `mcp-task-manager/src/` |
| Testing | `tests/` |

## Quality Checklist

- [ ] Follows async patterns (no blocking calls)
- [ ] Uses parameterized queries (no SQL injection)
- [ ] Has error handling
- [ ] Includes tests
- [ ] Updates expertise if new pattern
