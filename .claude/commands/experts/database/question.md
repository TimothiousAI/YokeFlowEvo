# Database Expert Query Template

Use this expert when working on:
- PostgreSQL schema changes
- asyncpg queries and operations
- Connection pooling configuration
- JSONB data storage
- Database migrations
- Query optimization

## Query Format

```
Domain: database
Task: [describe the database work]
Context: [existing tables or queries to reference]
Question: [specific question about implementation]
```

## Example Queries

### Schema change
```
Domain: database
Task: Add execution_plan JSONB column to projects table
Context: Need to store batch assignments and worktree mappings
Question: Should this be nullable or have a default empty object?
```

### Query optimization
```
Domain: database
Task: Query tasks with their predicted file conflicts
Context: Need to identify tasks that can run in parallel
Question: Best way to join tasks with file overlap detection?
```

## Routing Rules

Route to this expert when:
1. File path contains `database` or `schema/`
2. Task mentions: SQL, query, table, column, migration, PostgreSQL
3. Working with data persistence or retrieval
4. Implementing new database methods
