# Self-Learning System

**YokeFlow v1.3.0+** includes a self-learning system that accumulates expertise from completed sessions and uses it to improve future task execution. The system also intelligently selects the most cost-effective Claude model for each task based on complexity analysis.

## Table of Contents

- [Overview](#overview)
- [Expertise Domains](#expertise-domains)
- [Learning Extraction](#learning-extraction)
- [Expertise Management](#expertise-management)
- [Model Selection](#model-selection)
- [Configuration](#configuration)
- [Best Practices](#best-practices)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Overview

The self-learning system consists of two main components:

### 1. ExpertiseManager

Accumulates domain-specific knowledge from completed sessions:
- Extracts patterns, techniques, and learnings from session logs
- Classifies tasks into domains (database, api, frontend, testing, security, deployment, general)
- Validates and prunes stale expertise
- Enforces line limits to prevent token bloat (MAX_EXPERTISE_LINES = 1000)
- Formats expertise for prompt injection

### 2. ModelSelector

Selects optimal Claude model for each task:
- Analyzes task complexity across multiple dimensions
- Recommends model tier (Haiku/Sonnet/Opus)
- Tracks historical performance by task type
- Enforces budget limits
- Provides reasoning for recommendations

### How It Works

```
┌─────────────────────────────────────────────────────────┐
│                  Task Execution                          │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│             ExpertiseManager                             │
│  - Classifies task into domain (api/frontend/etc.)      │
│  - Loads relevant expertise from database                │
│  - Injects expertise into agent prompt                   │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│              ModelSelector                               │
│  - Analyzes task complexity (4 dimensions)               │
│  - Recommends model tier (Haiku/Sonnet/Opus)            │
│  - Checks budget constraints                             │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│              Agent Execution                             │
│  - Uses recommended model                                │
│  - Has access to domain expertise                        │
│  - Executes task                                         │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│           Learning Extraction                            │
│  - Extracts patterns from successful execution           │
│  - Records failures and lessons learned                  │
│  - Updates expertise database                            │
└─────────────────────────────────────────────────────────┘
```

---

## Expertise Domains

Tasks are automatically classified into 7 domains:

| Domain | Description | Example Tasks |
|--------|-------------|---------------|
| **database** | Schema, migrations, queries | "Create user table", "Add index on email column" |
| **api** | REST endpoints, routes, handlers | "Implement /users endpoint", "Add authentication middleware" |
| **frontend** | UI components, React, CSS | "Create login form component", "Style dashboard layout" |
| **testing** | Unit tests, integration tests | "Test user authentication", "Add API endpoint tests" |
| **security** | Authentication, authorization | "Implement JWT tokens", "Add CORS headers" |
| **deployment** | Docker, CI/CD, configuration | "Create Dockerfile", "Setup GitHub Actions" |
| **general** | Catch-all for other tasks | "Update README", "Refactor code" |

### Classification Algorithm

ExpertiseManager uses keyword matching and file pattern analysis:

**Keywords:**
```python
DOMAIN_KEYWORDS = {
    'database': ['schema', 'migration', 'query', 'table', 'index', 'sql', ...],
    'api': ['endpoint', 'route', 'rest', 'request', 'response', 'http', ...],
    'frontend': ['component', 'react', 'css', 'ui', 'render', 'state', ...],
    # ... etc.
}
```

**File Patterns:**
```python
DOMAIN_FILE_PATTERNS = {
    'database': ['.sql', 'migration', 'schema'],
    'api': ['route', 'handler', 'controller', 'endpoint', 'api'],
    'frontend': ['.tsx', '.jsx', '.css', '.scss', '.html', 'component'],
    # ... etc.
}
```

**Classification Process:**
1. Extract keywords from task description and action
2. Match against DOMAIN_KEYWORDS (case-insensitive)
3. Check file patterns in task action
4. Calculate score for each domain
5. Select highest-scoring domain (or 'general' if no strong match)

---

## Learning Extraction

After each session, ExpertiseManager extracts learnings from session logs and execution results.

### What Gets Extracted

**1. Core Files:**
- Files that were created or modified
- Critical dependencies
- Configuration files

**2. Patterns:**
- Code patterns that worked well
- Reusable snippets
- Architecture patterns

**3. Techniques:**
- Multi-step procedures
- Best practices discovered
- Debugging techniques

**4. Learnings:**
- Failures and how they were resolved
- Successes and what made them work
- Edge cases and gotchas

### Expertise Structure

Expertise is stored as JSONB in PostgreSQL:

```json
{
  "core_files": [
    "api/main.py",
    "core/database.py",
    "schema/001_initial.sql"
  ],
  "patterns": [
    {
      "name": "Async database connection",
      "code": "async with DatabaseManager() as db:\n    result = await db.query(...)",
      "when_to_use": "All database operations in async functions"
    },
    {
      "name": "FastAPI endpoint structure",
      "code": "@app.get('/api/endpoint')\nasync def endpoint(db: Database = Depends(get_db)):\n    ...",
      "when_to_use": "Creating new API endpoints with database access"
    }
  ],
  "techniques": [
    {
      "name": "Database migration workflow",
      "steps": [
        "Create SQL file in schema/postgresql/",
        "Use sequential numbering (001_, 002_, etc.)",
        "Run init_database.py to apply",
        "Verify with psql"
      ]
    }
  ],
  "learnings": [
    {
      "type": "failure",
      "lesson": "Always use async/await with database operations, sync calls cause deadlocks",
      "date": "2026-01-05",
      "context": "Session 5 - Database connection errors"
    },
    {
      "type": "success",
      "lesson": "Using connection pooling with DatabaseManager reduces latency by 50%",
      "date": "2026-01-05",
      "context": "Session 8 - Performance optimization"
    }
  ]
}
```

### Extraction Triggers

Learning extraction happens automatically:

1. **After each session**: Extract patterns from successful task completions
2. **On failure**: Record failure context and resolution steps
3. **Manual validation**: Prune stale or incorrect expertise

---

## Expertise Management

### Line Limit Enforcement

To prevent token bloat, expertise files have a **1000-line limit**:

```python
MAX_EXPERTISE_LINES = 1000
```

When limit is exceeded:
1. Old learnings are pruned first (oldest dates)
2. Less useful patterns are removed (low usage count)
3. Techniques are consolidated (merge similar steps)
4. Critical core files are preserved

### Validation and Pruning

ExpertiseManager validates expertise periodically:

```python
# Validate expertise for a domain
await expertise_manager.validate_expertise(domain='api')

# Prune stale entries (>90 days old with no usage)
await expertise_manager.prune_stale_expertise(domain='api', max_age_days=90)
```

**Validation checks:**
- ✅ Core files still exist in project
- ✅ Patterns are still syntactically valid
- ✅ Learnings are still relevant (not obsoleted by newer learnings)
- ✅ Total line count is under MAX_EXPERTISE_LINES

### Versioning

Expertise files are versioned automatically:

```python
# Each save increments version
expertise.version = 1  # Initial version
await expertise_manager.save_expertise(domain='api', content=data)
# expertise.version = 2 after save
```

This allows:
- Rollback to previous versions if needed
- Track expertise evolution over time
- Detect when expertise becomes stale

---

## Model Selection

ModelSelector analyzes task complexity and recommends the most cost-effective Claude model.

### Model Tiers

| Tier | Model | Input Cost | Output Cost | Best For |
|------|-------|------------|-------------|----------|
| **Haiku** | `claude-haiku-4-5` | $0.25/1M tokens | $1.25/1M tokens | Simple, repetitive tasks |
| **Sonnet** | `claude-sonnet-4-5` | $3.00/1M tokens | $15.00/1M tokens | Moderate complexity |
| **Opus** | `claude-opus-4-5` | $15.00/1M tokens | $75.00/1M tokens | Complex, architectural tasks |

### Complexity Analysis

ModelSelector scores tasks across 4 dimensions (0.0-1.0 scale):

**1. Reasoning Depth:**
- Multi-step logic required?
- Algorithm design needed?
- Architectural decisions?

**Keywords:** "algorithm", "architecture", "design pattern", "refactor", "optimize"

**2. Code Complexity:**
- How many lines of code?
- How many files involved?
- How much existing code to understand?

**Indicators:** "create multiple", "integrate with", "refactor entire", "modify 10+"

**3. Domain Specificity:**
- Specialized knowledge required?
- Complex domain logic?
- Industry-specific requirements?

**Keywords:** "authentication", "encryption", "machine learning", "database optimization"

**4. Context Requirements:**
- Dependencies on other tasks?
- Existing codebase knowledge needed?
- Complex state management?

**Keywords:** "integrate", "depends on", "build on", "extend existing"

### Complexity Thresholds

```python
COMPLEXITY_THRESHOLDS = {
    "haiku_max": 0.3,    # Use Haiku if overall_score < 0.3
    "sonnet_min": 0.3,   # Use Sonnet if 0.3 <= overall_score <= 0.7
    "sonnet_max": 0.7,
    "opus_min": 0.7      # Use Opus if overall_score > 0.7
}
```

### Example Recommendations

**Simple task (Haiku):**
```
Task: "Update README with installation instructions"
Complexity: 0.15
Reasoning: "Simple documentation update, no code complexity, general domain"
Model: Haiku (~$0.002 estimated cost)
```

**Moderate task (Sonnet):**
```
Task: "Implement /users API endpoint with CRUD operations"
Complexity: 0.52
Reasoning: "Standard REST endpoint, moderate code complexity, requires database integration"
Model: Sonnet (~$0.015 estimated cost)
```

**Complex task (Opus):**
```
Task: "Design and implement authentication system with JWT, refresh tokens, and RBAC"
Complexity: 0.85
Reasoning: "Complex security domain, multi-step architecture, requires deep understanding"
Model: Opus (~$0.080 estimated cost)
```

### Budget Constraints

ModelSelector enforces budget limits (coming in v1.4.0):

```python
# Set budget limit in configuration
config.cost_optimization.budget_limit = 50.00  # $50 USD

# ModelSelector will:
# 1. Track cumulative cost
# 2. Downgrade to cheaper models when budget is low
# 3. Warn when budget is exceeded
```

---

## Configuration

### Environment Variables

No additional environment variables required. Self-learning uses existing database connection.

### YAML Configuration

```yaml
# .yokeflow.yaml
self_learning:
  enabled: true
  max_expertise_lines: 1000
  validation_interval_days: 30
  prune_stale_after_days: 90

cost_optimization:
  enabled: true
  budget_limit: null  # null = unlimited, or set USD amount
  force_model: null   # null = automatic, or 'haiku'/'sonnet'/'opus'
  complexity_override: {}  # Override thresholds if needed
```

### Programmatic Configuration

```python
from core.learning import ExpertiseManager, ModelSelector

# Initialize expertise manager
expertise_mgr = ExpertiseManager(
    project_id=project_uuid,
    db_connection=db
)

# Initialize model selector
model_selector = ModelSelector(
    project_id=project_uuid,
    config=config,
    db_connection=db
)

# Get expertise for task
task_domain = expertise_mgr.classify_task(task)
expertise = await expertise_mgr.get_expertise(task_domain)

# Get model recommendation
recommendation = model_selector.recommend_model(task)
print(f"Use {recommendation.model.value}: {recommendation.reasoning}")
```

---

## Best Practices

### 1. Domain Classification

✅ **DO:**
- Use clear, descriptive task names
- Include domain keywords in task descriptions
- Specify file paths in task actions

❌ **DON'T:**
- Use vague task descriptions like "Fix bug"
- Mix multiple domains in single task
- Omit context from task actions

### 2. Expertise Accumulation

✅ **DO:**
- Let expertise accumulate naturally over multiple sessions
- Validate expertise monthly
- Prune stale learnings after 90 days
- Review expertise before important tasks

❌ **DON'T:**
- Manually edit expertise JSONB (use manager methods)
- Disable line limit enforcement (causes token bloat)
- Delete all expertise frequently (loses valuable learnings)

### 3. Model Selection

✅ **DO:**
- Trust ModelSelector's recommendations
- Review cost estimates before large batches
- Use Opus for critical architectural tasks
- Use Haiku for simple, repetitive tasks

❌ **DON'T:**
- Force Haiku for all tasks to save money (quality suffers)
- Force Opus for all tasks (wastes money on simple tasks)
- Ignore complexity scores (they're calibrated for optimal cost/quality)

### 4. Budget Management

✅ **DO:**
- Set realistic budget limits based on project size
- Monitor cumulative costs in real-time
- Review ModelSelector decisions in session logs
- Adjust complexity thresholds if needed

❌ **DON'T:**
- Set budget too low (forces poor model choices)
- Ignore budget warnings
- Skip cost analysis on large projects

---

## Examples

### Example 1: Expertise Injection

```python
# Task: "Create user authentication endpoint"
task = {
    'id': 123,
    'description': 'Create user authentication endpoint',
    'action': 'Implement POST /api/auth/login with JWT tokens',
    'epic_id': 5
}

# 1. Classify domain
expertise_mgr = ExpertiseManager(project_id, db)
domain = expertise_mgr.classify_task(task)
# Result: 'security' (keywords: 'authentication', 'JWT')

# 2. Load expertise
expertise = await expertise_mgr.get_expertise('security')
# Returns: ExpertiseFile with security patterns, JWT examples, auth best practices

# 3. Format for prompt
expertise_text = expertise_mgr.format_expertise_for_prompt(expertise)
# Returns formatted markdown with patterns, techniques, learnings

# 4. Inject into agent prompt
agent_prompt = f"""
You are implementing: {task['description']}

Domain-specific expertise:
{expertise_text}

Task action:
{task['action']}
"""
```

### Example 2: Model Recommendation

```python
# Task: "Refactor authentication system"
task = {
    'id': 456,
    'description': 'Refactor authentication system to use refresh tokens',
    'action': '''
    Modify existing auth endpoints to support refresh tokens:
    - Update /api/auth/login to return both access and refresh tokens
    - Create /api/auth/refresh endpoint
    - Add token rotation logic
    - Update database schema with refresh_tokens table
    - Integrate with existing user sessions
    ''',
    'epic_id': 5
}

# Analyze complexity
model_selector = ModelSelector(project_id, config, db)
complexity = model_selector.analyze_complexity(task)
# Result:
# TaskComplexity(
#     reasoning_depth=0.8,      # Refactoring requires deep understanding
#     code_complexity=0.7,       # Multiple files and endpoints
#     domain_specificity=0.9,    # Security domain, specialized knowledge
#     context_requirements=0.8,  # Must integrate with existing auth
#     overall_score=0.8          # Weighted average
# )

# Get recommendation
recommendation = model_selector.recommend_model(task)
# Result:
# ModelRecommendation(
#     model=ModelTier.OPUS,
#     reasoning="Complex security refactoring with high domain specificity",
#     estimated_cost=0.085,
#     complexity=complexity
# )
```

### Example 3: Expertise Content

Real example of expertise JSONB for the 'api' domain:

```json
{
  "core_files": [
    "api/main.py",
    "api/routes/users.py",
    "api/routes/auth.py",
    "core/database.py"
  ],
  "patterns": [
    {
      "name": "FastAPI endpoint with database",
      "code": "@app.get('/api/users/{user_id}')\nasync def get_user(\n    user_id: int,\n    db: Database = Depends(get_db)\n):\n    user = await db.get_user(user_id)\n    if not user:\n        raise HTTPException(status_code=404)\n    return user",
      "when_to_use": "Creating REST endpoints that query database"
    },
    {
      "name": "Error handling pattern",
      "code": "try:\n    result = await db.operation()\nexcept IntegrityError as e:\n    raise HTTPException(status_code=409, detail=str(e))\nexcept Exception as e:\n    logger.error(f'Unexpected error: {e}')\n    raise HTTPException(status_code=500)",
      "when_to_use": "Database operations that may fail with constraints"
    }
  ],
  "techniques": [
    {
      "name": "Adding new API endpoint",
      "steps": [
        "1. Create route function in api/routes/",
        "2. Add Depends(get_db) for database access",
        "3. Use Pydantic models for request/response validation",
        "4. Add error handling with HTTPException",
        "5. Register route in api/main.py",
        "6. Test with curl or Postman"
      ]
    }
  ],
  "learnings": [
    {
      "type": "failure",
      "lesson": "Always validate UUID format in path parameters or you get 422 errors",
      "date": "2026-01-04",
      "context": "Session 12 - User endpoint returned 422 for invalid UUIDs"
    },
    {
      "type": "success",
      "lesson": "Using BackgroundTasks for async operations keeps API responses fast",
      "date": "2026-01-05",
      "context": "Session 15 - Email sending moved to background task"
    }
  ]
}
```

---

## Troubleshooting

### Issue: Task Classified into Wrong Domain

**Symptoms:**
- Task gets wrong expertise injected
- Agent lacks relevant context

**Solution:**
1. Add domain keywords to task description
2. Specify file paths in task action
3. Manually override classification (advanced):
   ```python
   # In agent code
   domain = 'security'  # Force security domain
   expertise = await expertise_mgr.get_expertise(domain)
   ```

### Issue: Expertise File Exceeds Line Limit

**Symptoms:**
- Error: "Expertise file exceeds MAX_EXPERTISE_LINES"
- Expertise not saved

**Solution:**
```python
# Validate and auto-prune
await expertise_mgr.validate_expertise('api')
await expertise_mgr.prune_stale_expertise('api', max_age_days=60)

# Or manually trim:
expertise = await expertise_mgr.get_expertise('api')
# Remove oldest learnings
expertise.content['learnings'] = expertise.content['learnings'][-50:]
await expertise_mgr.save_expertise('api', expertise.content)
```

### Issue: Model Recommendation Seems Wrong

**Symptoms:**
- Haiku assigned to complex task
- Opus assigned to simple task

**Solution:**
1. Review complexity analysis:
   ```python
   complexity = model_selector.analyze_complexity(task)
   print(f"Reasoning: {complexity.reasoning_depth}")
   print(f"Code: {complexity.code_complexity}")
   print(f"Domain: {complexity.domain_specificity}")
   print(f"Context: {complexity.context_requirements}")
   print(f"Overall: {complexity.overall_score}")
   ```

2. Override if needed:
   ```yaml
   # .yokeflow.yaml
   cost_optimization:
     force_model: 'opus'  # Force specific model
   ```

3. Adjust thresholds (advanced):
   ```yaml
   cost_optimization:
     complexity_override:
       haiku_max: 0.2  # More conservative
       opus_min: 0.8   # Only use Opus for very complex tasks
   ```

### Issue: Expertise Not Being Used

**Symptoms:**
- Agent repeats mistakes
- No improvement over sessions

**Solution:**
1. Verify expertise exists:
   ```python
   expertise = await expertise_mgr.get_expertise('api')
   print(f"Version: {expertise.version}, Lines: {expertise.line_count}")
   ```

2. Check prompt injection:
   ```python
   # In agent prompt code
   expertise_text = expertise_mgr.format_expertise_for_prompt(expertise)
   # Verify expertise_text is in agent's prompt
   ```

3. Review learning extraction:
   ```python
   # After session
   await expertise_mgr.extract_learnings(session_id, domain='api')
   # Check session logs for extraction errors
   ```

---

## See Also

- [parallel-execution.md](parallel-execution.md) - Parallel execution with self-learning integration
- [cost-optimization.md](cost-optimization.md) - Detailed cost optimization guide
- [developer-guide.md](developer-guide.md) - Technical implementation details
- [review-system.md](review-system.md) - Quality review system
