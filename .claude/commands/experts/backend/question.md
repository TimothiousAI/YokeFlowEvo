# Backend Expert Query Template

Use this expert when working on:
- FastAPI endpoints and routes
- Async Python patterns
- Pydantic models and validation
- WebSocket implementations
- Background task management
- API error handling

## Query Format

```
Domain: backend
Task: [describe what you're implementing]
Context: [relevant files or existing patterns]
Question: [specific question about implementation]
```

## Example Queries

### Adding a new endpoint
```
Domain: backend
Task: Add GET /api/projects/{id}/execution-plan endpoint
Context: Similar to existing /api/projects/{id}/progress endpoint
Question: Should this return the full execution plan or a summary?
```

### Async pattern question
```
Domain: backend
Task: Implement batch executor that spawns multiple agents
Context: Need to run agents in parallel without blocking
Question: Should I use asyncio.gather or TaskGroup for concurrent agent execution?
```

## Routing Rules

Route to this expert when:
1. File path contains `api/` or ends with `_api.py`
2. Task mentions: endpoint, route, REST, API, FastAPI, Pydantic
3. Working with WebSocket or real-time features
4. Implementing background tasks or async operations
