---
name: debug-issue
description: Debug and fix issues in YokeFlow codebase
---

# Debug Issue Skill

Use this skill when debugging problems in YokeFlow.

## Debug Process

1. **Reproduce the Issue**
   - Get exact error message
   - Identify which component failed
   - Check logs in `generations/{project}/logs/`

2. **Identify Domain**
   - API error (500, 404) → Backend
   - UI not updating → Frontend
   - Query failed → Database
   - Agent not starting → Orchestration
   - Tool not found → MCP

3. **Common Issues by Domain**

### Backend
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| 500 error | Unhandled exception | Add try/except |
| Timeout | Blocking call in async | Use async version |
| Connection refused | DB pool exhausted | Check pool limits |

### Frontend
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Hydration error | Server/client mismatch | Check useEffect |
| Stale data | SWR cache | Call mutate() |
| Type error | Missing interface | Define types |

### Database
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Connection error | Pool not initialized | await db.connect() |
| Query timeout | Missing index | Add index |
| JSON error | Invalid JSONB | Use json.dumps() |

### Orchestration
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Agent won't start | MCP server not built | npm run build |
| Session stuck | Signal handler issue | Check SIGTERM |
| Worktree conflict | Dirty working tree | git status |

4. **Fix and Verify**
   - Apply minimal fix
   - Run related tests
   - Verify in UI/API

5. **Document Learning**
   - If new issue pattern, add to expertise anti-patterns
