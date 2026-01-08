---
name: review-code
description: Review code changes against YokeFlow patterns and best practices
---

# Code Review Skill

Use this skill when reviewing code changes in YokeFlow.

## Review Checklist

### Backend (Python/FastAPI)
- [ ] All endpoints are `async def`
- [ ] Uses `HTTPException` for errors
- [ ] Parameterized queries (no string interpolation in SQL)
- [ ] Connection pool used via context manager
- [ ] Proper error handling

### Frontend (Next.js/React)
- [ ] Server Components by default
- [ ] `'use client'` only when needed
- [ ] TypeScript types defined
- [ ] SWR for client-side fetching
- [ ] Tailwind classes used correctly

### Database
- [ ] Uses `$1, $2` placeholders
- [ ] Transaction context for multi-statement ops
- [ ] RETURNING clause for inserts/updates
- [ ] JSONB for flexible metadata

### Testing
- [ ] `@pytest.mark.asyncio` on async tests
- [ ] Fixtures for setup/teardown
- [ ] Mocks for external services
- [ ] Independent tests (no pollution)

## Anti-Pattern Detection

Flag if you see:
- `requests.get` in async code (use httpx)
- SQL string formatting (use parameters)
- Missing await on coroutines
- `subprocess.run` in async context
- `'use client'` on every component

## Output Format

```
## Code Review Summary

### Issues Found
- [CRITICAL] Description
- [WARNING] Description

### Suggestions
- Consider using X pattern instead of Y

### Expertise Updates
- New pattern discovered: X (add to {domain}/expertise.yaml)
```
