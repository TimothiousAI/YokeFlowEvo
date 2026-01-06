# Cost Optimization Guide

YokeFlow's intelligent model selection system helps you balance cost and quality by automatically choosing the most cost-effective Claude model for each task based on complexity analysis.

## Table of Contents

- [Overview](#overview)
- [Model Tiers and Pricing](#model-tiers-and-pricing)
- [Complexity Analysis Algorithm](#complexity-analysis-algorithm)
- [Budget Management](#budget-management)
- [Configuration](#configuration)
- [Cost Estimation](#cost-estimation)
- [Cost Reduction Strategies](#cost-reduction-strategies)
- [Examples](#examples)
- [Best Practices](#best-practices)

---

## Overview

### How Cost Optimization Works

YokeFlow's **ModelSelector** analyzes each task and recommends the optimal Claude model:

1. **Complexity Analysis**: Scores task across 4 dimensions (reasoning, code, domain, context)
2. **Model Recommendation**: Maps complexity score to model tier (Haiku/Sonnet/Opus)
3. **Budget Checking**: Ensures recommendation fits within budget constraints
4. **Historical Learning**: Adjusts based on past performance data

**Result**: Tasks get the right model for the job - not too cheap (quality suffers), not too expensive (waste money).

### Benefits

- **40-60% cost reduction** compared to using Opus for all tasks
- **No quality loss** - complex tasks still get powerful models
- **Automatic optimization** - no manual model selection needed
- **Budget protection** - enforces spending limits

---

## Model Tiers and Pricing

### Claude Model Comparison

| Model | Tier | Input Cost | Output Cost | Best For | Speed |
|-------|------|------------|-------------|----------|-------|
| **claude-haiku-4-5** | Entry | $0.25/1M tokens | $1.25/1M tokens | Simple, repetitive tasks | Fastest |
| **claude-sonnet-4-5** | Mid | $3.00/1M tokens | $15.00/1M tokens | Standard development | Fast |
| **claude-opus-4-5** | Premium | $15.00/1M tokens | $75.00/1M tokens | Complex architecture | Slower |

**Pricing as of January 2025** (subject to change - check Anthropic pricing page for latest)

### Cost Comparison Example

**Scenario**: 100-task project with mixed complexity

**All Opus (no optimization):**
- 100 tasks × ~10K tokens × $0.015/1K = **$15.00**

**Smart Selection (ModelSelector):**
- 60 simple tasks (Haiku): 60 × 10K × $0.00025/1K = **$0.15**
- 30 moderate tasks (Sonnet): 30 × 10K × $0.003/1K = **$0.90**
- 10 complex tasks (Opus): 10 × 10K × $0.015/1K = **$1.50**
- **Total: $2.55** (83% savings!)

### When Each Model Makes Sense

**Haiku** (complexity < 0.3):
- ✅ Documentation updates
- ✅ Simple CRUD operations
- ✅ Boilerplate code generation
- ✅ Formatting and style fixes
- ✅ Configuration file updates

**Sonnet** (complexity 0.3-0.7):
- ✅ Standard API endpoints
- ✅ UI components
- ✅ Database queries
- ✅ Integration code
- ✅ Most business logic

**Opus** (complexity > 0.7):
- ✅ System architecture design
- ✅ Complex algorithms
- ✅ Security implementations
- ✅ Performance optimization
- ✅ Refactoring large codebases

---

## Complexity Analysis Algorithm

ModelSelector scores tasks across **4 dimensions** (each 0.0-1.0):

### 1. Reasoning Depth (Weight: 30%)

**What it measures**: How much multi-step thinking and architectural decision-making is required.

**High reasoning keywords**:
- "design", "architecture", "algorithm", "optimize", "refactor"
- "strategy", "pattern", "approach", "evaluate", "analyze"

**Scoring examples**:
```
"Update README" → 0.1 (no reasoning needed)
"Implement login endpoint" → 0.4 (some logic required)
"Design authentication system architecture" → 0.9 (deep reasoning)
```

### 2. Code Complexity (Weight: 25%)

**What it measures**: How much code is involved and how many files need to be understood.

**High complexity indicators**:
- "multiple files", "entire codebase", "refactor all"
- "integrate with", "modify 10+", "create complex"
- File counts: "5+ components", "all endpoints"

**Scoring examples**:
```
"Add console.log" → 0.1 (single line)
"Create user model" → 0.3 (one file, moderate)
"Refactor entire API layer" → 0.8 (many files)
```

### 3. Domain Specificity (Weight: 25%)

**What it measures**: How much specialized knowledge is required.

**High specificity domains**:
- Security/authentication (JWT, OAuth, encryption)
- Performance optimization (profiling, caching, algorithms)
- Machine learning (models, training, inference)
- Complex database operations (indexing, query optimization)

**Scoring examples**:
```
"Create button component" → 0.2 (general UI)
"Add database index" → 0.5 (moderate DB knowledge)
"Implement AES-256 encryption with key rotation" → 0.9 (specialized)
```

### 4. Context Requirements (Weight: 20%)

**What it measures**: How much existing code and state needs to be understood.

**High context indicators**:
- "integrate with existing", "extend current", "build on"
- "depends on", "compatible with", "refactor existing"
- Cross-epic dependencies

**Scoring examples**:
```
"Create new standalone script" → 0.1 (no context)
"Add field to existing model" → 0.4 (some context)
"Integrate new auth with existing user system" → 0.8 (high context)
```

### Overall Score Calculation

```python
overall_score = (
    reasoning_depth * 0.30 +
    code_complexity * 0.25 +
    domain_specificity * 0.25 +
    context_requirements * 0.20
)

# Map to model tier
if overall_score < 0.3:
    model = Haiku
elif overall_score <= 0.7:
    model = Sonnet
else:
    model = Opus
```

### Complexity Thresholds

Default thresholds (configurable):

```python
COMPLEXITY_THRESHOLDS = {
    "haiku_max": 0.3,    # Haiku: overall_score < 0.3
    "sonnet_min": 0.3,   # Sonnet: 0.3 <= overall_score <= 0.7
    "sonnet_max": 0.7,
    "opus_min": 0.7      # Opus: overall_score > 0.7
}
```

---

## Budget Management

### Setting Budget Limits

**Coming in v1.4.0** - Currently in development:

```yaml
# .yokeflow.yaml
cost_optimization:
  enabled: true
  budget_limit: 50.00  # USD per project
  budget_period: 'total'  # or 'daily', 'weekly', 'monthly'
  budget_warning_threshold: 0.8  # Warn at 80% of budget
```

### How Budget Enforcement Works

When budget limits are enabled:

1. **Pre-task check**: ModelSelector checks cumulative cost before each task
2. **Downgrade if needed**: If budget is low, may recommend cheaper model even for complex tasks
3. **Warning notifications**: Alert at 80% of budget
4. **Hard stop**: Execution stops when budget is exceeded (unless override enabled)

### Budget Tracking

```python
# Get current budget status
from core.learning import ModelSelector

model_selector = ModelSelector(project_id, config, db)
budget_status = await model_selector.get_budget_status()

print(f"Spent: ${budget_status['spent']:.2f}")
print(f"Limit: ${budget_status['limit']:.2f}")
print(f"Remaining: ${budget_status['remaining']:.2f}")
print(f"Percentage: {budget_status['percentage']:.1f}%")
```

### Budget Alerts

Configure alerts for budget thresholds:

```yaml
cost_optimization:
  budget_alerts:
    - threshold: 0.5  # 50%
      action: 'log'
    - threshold: 0.8  # 80%
      action: 'warn'
    - threshold: 1.0  # 100%
      action: 'stop'
```

---

## Configuration

### YAML Configuration

```yaml
# .yokeflow.yaml
cost_optimization:
  # Enable/disable cost optimization
  enabled: true

  # Budget management (v1.4.0+)
  budget_limit: null  # null = unlimited, or USD amount
  budget_period: 'total'  # total, daily, weekly, monthly

  # Force specific model (overrides complexity analysis)
  force_model: null  # null = automatic, or 'haiku', 'sonnet', 'opus'

  # Complexity threshold overrides
  complexity_override:
    haiku_max: 0.3    # Adjust if you want more/fewer Haiku assignments
    sonnet_max: 0.7   # Adjust if you want more/fewer Sonnet assignments
    opus_min: 0.7     # Adjust if you want more/fewer Opus assignments

  # Model override by domain
  domain_models:
    testing: 'haiku'      # Always use Haiku for tests
    deployment: 'haiku'   # Always use Haiku for deployment tasks
    security: 'opus'      # Always use Opus for security tasks

  # Historical performance weighting
  use_performance_data: true
  performance_weight: 0.2  # How much to adjust based on past performance
```

### Environment Variables

No special environment variables required. Cost optimization uses standard database connection.

### Programmatic Configuration

```python
from core.learning import ModelSelector
from core.config import Config

# Load configuration
config = Config.load()

# Override programmatically
config.cost_optimization.enabled = True
config.cost_optimization.force_model = 'sonnet'  # Force all tasks to Sonnet

# Initialize selector with custom config
model_selector = ModelSelector(project_id, config, db)
```

---

## Cost Estimation

### Estimating Project Costs

**Before starting a project**, estimate total cost:

```python
from core.database_connection import DatabaseManager
from core.learning import ModelSelector

async def estimate_project_cost(project_id):
    """Estimate total cost for all pending tasks."""
    async with DatabaseManager() as db:
        # Get all tasks
        tasks = await db.list_tasks(project_id, only_pending=True)

        # Analyze each task
        model_selector = ModelSelector(project_id, config, db)
        total_cost = 0.0

        for task in tasks:
            recommendation = model_selector.recommend_model(task)
            total_cost += recommendation.estimated_cost
            print(f"Task {task['id']}: {recommendation.model.value} (${recommendation.estimated_cost:.3f})")

        print(f"\nTotal estimated cost: ${total_cost:.2f}")
        return total_cost

# Run estimation
await estimate_project_cost(project_uuid)
```

**Example output**:
```
Task 1: haiku ($0.002)
Task 2: haiku ($0.002)
Task 3: sonnet ($0.015)
Task 4: opus ($0.085)
...
Total estimated cost: $12.45
```

### Token Estimation

Estimate token usage for better cost predictions:

```python
def estimate_tokens(task):
    """Rough token estimation for a task."""
    # Input tokens: prompt + context + expertise
    base_prompt = 5000  # Base coding prompt
    task_description = len(task['description']) * 0.3  # ~0.3 tokens per char
    task_action = len(task['action']) * 0.3
    expertise = 2000  # Domain expertise injection

    input_tokens = base_prompt + task_description + task_action + expertise

    # Output tokens: code + explanation (rough estimate)
    output_tokens = input_tokens * 0.5  # Output is usually ~50% of input

    return {
        'input': int(input_tokens),
        'output': int(output_tokens),
        'total': int(input_tokens + output_tokens)
    }

# Calculate cost for specific model
def calculate_cost(tokens, model_tier):
    """Calculate cost given tokens and model tier."""
    pricing = PRICING[model_tier]
    input_cost = (tokens['input'] / 1_000_000) * pricing['input']
    output_cost = (tokens['output'] / 1_000_000) * pricing['output']
    return input_cost + output_cost
```

---

## Cost Reduction Strategies

### 1. Task Design Strategies

**Break down complex tasks into simpler subtasks**:
```
❌ "Implement complete authentication system"
   → Opus ($0.085)

✅ "Create database schema for users"
   → Haiku ($0.002)
✅ "Implement JWT token generation"
   → Sonnet ($0.015)
✅ "Create login endpoint"
   → Sonnet ($0.015)
✅ "Design refresh token strategy"
   → Opus ($0.085)

Savings: $0.085 → $0.117 (but better quality on simple tasks!)
```

**Use clear, specific task descriptions**:
```
❌ "Fix auth"  (complexity: unknown → defaults to Sonnet)
✅ "Update login button CSS to match design" (complexity: 0.15 → Haiku)
```

### 2. Configuration Tuning

**Adjust thresholds to prefer cheaper models**:
```yaml
cost_optimization:
  complexity_override:
    haiku_max: 0.4    # ↑ More Haiku assignments
    sonnet_max: 0.8   # ↑ More Sonnet assignments
    opus_min: 0.8     # ↑ Fewer Opus assignments
```

**Force Haiku for safe domains**:
```yaml
cost_optimization:
  domain_models:
    testing: 'haiku'      # Tests are usually simple
    deployment: 'haiku'   # Config updates are simple
    general: 'haiku'      # Documentation is simple
```

### 3. Parallel Execution for Volume Discounts

**Run simple tasks in parallel with Haiku**:
```bash
# 100 simple tasks in parallel (10 agents)
# Sequential: 100 × 3min = 300min
# Parallel: 10 batches × 3min = 30min
# Cost: Same (100 × Haiku), but 10x faster!

python scripts/run_self_enhancement.py --coding --parallel --max-concurrency 10
```

### 4. Expertise Accumulation

**Let expertise build up to reduce context needs**:
- First session: Opus for architecture (high complexity)
- Later sessions: Sonnet/Haiku (expertise provides context)
- Result: 40-60% cost reduction after 5-10 sessions

### 5. Manual Overrides for Known Simple Tasks

**Force Haiku for specific task types**:
```python
# In task creation
if 'documentation' in task_description.lower():
    model_override = 'haiku'
elif 'README' in task_description:
    model_override = 'haiku'
elif 'comment' in task_description.lower():
    model_override = 'haiku'
```

### 6. Review and Iterate

**Monitor cost patterns**:
```python
# Analyze model selection decisions
async def analyze_model_decisions(project_id):
    async with DatabaseManager() as db:
        sessions = await db.list_sessions(project_id)

        model_counts = {'haiku': 0, 'sonnet': 0, 'opus': 0}
        model_costs = {'haiku': 0.0, 'sonnet': 0.0, 'opus': 0.0}

        for session in sessions:
            model = session['model']
            cost = session['total_cost']
            model_counts[model] += 1
            model_costs[model] += cost

        print("Model Distribution:")
        for model in ['haiku', 'sonnet', 'opus']:
            count = model_counts[model]
            cost = model_costs[model]
            avg = cost / count if count > 0 else 0
            print(f"  {model.capitalize()}: {count} tasks, ${cost:.2f} total, ${avg:.3f} avg")

await analyze_model_decisions(project_uuid)
```

**Example output**:
```
Model Distribution:
  Haiku: 45 tasks, $2.10 total, $0.047 avg
  Sonnet: 38 tasks, $8.50 total, $0.224 avg
  Opus: 12 tasks, $12.80 total, $1.067 avg

Total: $23.40 (vs $50+ if all Opus)
```

---

## Examples

### Example 1: Cost-Effective Task Breakdown

**Original task (expensive)**:
```
Task: "Build complete user management system"
Complexity: 0.82
Model: Opus
Estimated Cost: $0.950
```

**Refactored tasks (cheaper)**:
```
Task 1: "Create users table schema"
  Complexity: 0.25 → Haiku ($0.002)

Task 2: "Create User SQLAlchemy model"
  Complexity: 0.35 → Sonnet ($0.018)

Task 3: "Implement CRUD endpoints for users"
  Complexity: 0.45 → Sonnet ($0.022)

Task 4: "Add user role-based permissions"
  Complexity: 0.72 → Opus ($0.085)

Task 5: "Create user management UI components"
  Complexity: 0.38 → Sonnet ($0.020)

Total: $0.147 (84% savings!)
```

### Example 2: Domain-Based Optimization

```yaml
# Optimize by domain
cost_optimization:
  domain_models:
    testing: 'haiku'      # All tests use Haiku
    deployment: 'haiku'   # All deployment uses Haiku
    frontend: 'sonnet'    # All UI uses Sonnet (rarely needs Opus)
    api: null             # API uses automatic selection
    security: null        # Security uses automatic (may need Opus)
```

**Results**:
```
Testing tasks (20):   20 × Haiku = $0.40
Deployment tasks (8): 8 × Haiku = $0.16
Frontend tasks (30):  30 × Sonnet = $4.50
API tasks (25):       15 Haiku + 8 Sonnet + 2 Opus = $2.35
Security tasks (7):   2 Sonnet + 5 Opus = $4.28

Total: $11.69 (vs $28+ with all automatic Opus assignments)
```

### Example 3: Budget-Constrained Development

```yaml
# Strict budget mode
cost_optimization:
  budget_limit: 20.00
  budget_alerts:
    - threshold: 0.8
      action: 'downgrade_models'  # Start using cheaper models
    - threshold: 1.0
      action: 'stop'

  # Aggressive Haiku preference
  complexity_override:
    haiku_max: 0.5    # Use Haiku up to 0.5 complexity
    opus_min: 0.9     # Only use Opus for 0.9+ complexity
```

**Behavior**:
- First 80 tasks: Normal model selection
- At $16.00 (80% budget): Start preferring Haiku/Sonnet
- At $20.00 (100% budget): Stop execution, alert user

---

## Best Practices

### 1. Start with Defaults

✅ **DO**: Use default settings for first project
✅ **DO**: Monitor model distribution after 50+ tasks
✅ **DO**: Adjust thresholds based on results

❌ **DON'T**: Immediately force all Haiku (quality suffers)
❌ **DON'T**: Set budget too low (forces poor decisions)

### 2. Trust the Complexity Analysis

✅ **DO**: Let ModelSelector make recommendations
✅ **DO**: Review reasoning in session logs
✅ **DO**: Override only for specific domains

❌ **DON'T**: Manually force models for every task
❌ **DON'T**: Ignore complexity scores (they're calibrated)

### 3. Design Tasks for Optimal Costing

✅ **DO**: Break complex tasks into simpler subtasks
✅ **DO**: Use clear, specific descriptions
✅ **DO**: Separate architectural design (Opus) from implementation (Sonnet/Haiku)

❌ **DON'T**: Create giant "do everything" tasks
❌ **DON'T**: Use vague descriptions (causes overestimation)

### 4. Monitor and Iterate

✅ **DO**: Review cost reports after each epic
✅ **DO**: Analyze model distribution patterns
✅ **DO**: Adjust thresholds based on your specific project

❌ **DON'T**: Set and forget
❌ **DON'T**: Ignore cost warnings

### 5. Balance Cost and Quality

✅ **DO**: Use Opus for critical architecture decisions
✅ **DO**: Use Haiku for simple, safe tasks
✅ **DO**: Remember: time is money too (faster = cheaper overall)

❌ **DON'T**: Sacrifice quality to save $0.10
❌ **DON'T**: Over-optimize (diminishing returns)

---

## See Also

- [self-learning.md](self-learning.md) - Expertise system and model selection
- [parallel-execution.md](parallel-execution.md) - Parallel execution for faster development
- [configuration.md](configuration.md) - General configuration options
- [developer-guide.md](developer-guide.md) - Technical implementation details
