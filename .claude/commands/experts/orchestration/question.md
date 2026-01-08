# Orchestration Expert Query Template

Use this expert when working on:
- Session lifecycle management
- Agent spawning and monitoring
- Parallel execution coordination
- Git worktree management
- Batch processing logic
- Signal handling and graceful shutdown

## Query Format

```
Domain: orchestration
Task: [describe the orchestration work]
Context: [existing orchestrator or agent code]
Question: [specific question about implementation]
```

## Example Queries

### Parallel execution
```
Domain: orchestration
Task: Implement BatchExecutor that runs tasks in parallel worktrees
Context: Need to coordinate multiple Claude agents
Question: How to handle if one agent fails while others are running?
```

### Session management
```
Domain: orchestration
Task: Add execution plan building after Session 0
Context: Current flow: init session -> coding sessions
Question: Where in orchestrator to trigger plan building?
```

## Routing Rules

Route to this expert when:
1. File path contains `orchestrator`, `agent`, or `parallel/`
2. Task mentions: session, agent, parallel, batch, worktree
3. Working with subprocess or signal handling
4. Implementing execution coordination
