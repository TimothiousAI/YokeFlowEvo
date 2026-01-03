# Epic 06: Cost Optimization & Model Selection

**Priority:** P1 (Enhancement)
**Estimated Duration:** 2-3 days
**Dependencies:** Epic 01 (Foundation), Epic 05 (Self-Learning)
**Phase:** 2

---

## Overview

Implement intelligent model selection and cost tracking to optimize API costs while maintaining quality. The system analyzes task complexity and historical performance to choose the most cost-effective model for each task.

---

## Background: Model Economics

**Model Pricing (per 1M tokens as of 2024):**
| Model | Input | Output | Relative Cost |
|-------|-------|--------|---------------|
| Opus | $15 | $75 | 1.0x (baseline) |
| Sonnet | $3 | $15 | 0.2x |
| Haiku | $0.25 | $1.25 | 0.017x |

**Cost Optimization Opportunity:**
- 80% of tasks can use Sonnet effectively
- 15% require Opus for complex reasoning
- 5% could use Haiku (simple edits, documentation)

---

## Tasks

### 6.1 ModelSelector Core Implementation

**Description:** Implement the model selection engine.

**File:** `core/learning/model_selector.py`

**Class Structure:**

```python
from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum

class ModelTier(Enum):
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"

@dataclass
class ModelRecommendation:
    """Model selection recommendation"""
    model: ModelTier
    confidence: float  # 0.0 to 1.0
    reason: str
    estimated_cost: float
    alternative: Optional[ModelTier] = None

@dataclass
class TaskComplexity:
    """Task complexity analysis"""
    reasoning_depth: int  # 1-5
    code_complexity: int  # 1-5
    domain_specificity: int  # 1-5
    context_requirements: int  # 1-5
    overall_score: float  # Weighted average

class ModelSelector:
    """
    Selects optimal model based on task complexity and cost constraints.

    Uses historical performance data to learn which models work best
    for different task types.
    """

    # Model pricing per 1M tokens
    PRICING = {
        ModelTier.HAIKU: {"input": 0.25, "output": 1.25},
        ModelTier.SONNET: {"input": 3.0, "output": 15.0},
        ModelTier.OPUS: {"input": 15.0, "output": 75.0},
    }

    # Default thresholds (can be tuned)
    COMPLEXITY_THRESHOLDS = {
        ModelTier.HAIKU: (0.0, 2.0),   # Simple tasks
        ModelTier.SONNET: (2.0, 4.0),  # Medium complexity
        ModelTier.OPUS: (4.0, 5.0),    # High complexity
    }

    def __init__(self, project_id: str, config: Dict):
        self.project_id = project_id
        self.config = config
        self.budget_limit = config.get('budget_limit_usd')
        self.spent_usd = 0.0
        self._performance_cache: Dict[str, Dict] = {}

    async def initialize(self) -> None:
        """Load historical performance data"""

    async def select_model(
        self,
        task: Dict,
        force_model: Optional[ModelTier] = None
    ) -> ModelRecommendation:
        """Select optimal model for a task"""

    def analyze_complexity(self, task: Dict) -> TaskComplexity:
        """Analyze task complexity"""

    async def record_outcome(
        self,
        task_id: int,
        model: ModelTier,
        success: bool,
        tokens_used: Dict,
        duration: float
    ) -> None:
        """Record task outcome for learning"""

    def estimate_cost(self, model: ModelTier, estimated_tokens: int) -> float:
        """Estimate cost for a task"""

    async def get_budget_status(self) -> Dict:
        """Get current budget usage"""
```

**Acceptance Criteria:**
- [ ] Selects appropriate model based on complexity
- [ ] Respects budget constraints
- [ ] Learns from outcomes
- [ ] Provides clear recommendations

---

### 6.2 Task Complexity Analysis

**Description:** Implement task complexity scoring.

**Analysis Factors:**

```python
def analyze_complexity(self, task: Dict) -> TaskComplexity:
    """
    Analyze task complexity across multiple dimensions.

    Returns scores from 1-5 for each dimension.
    """
    description = task.get('description', '')
    epic = task.get('epic', {})
    metadata = task.get('metadata', {})

    # Reasoning depth - does task require multi-step reasoning?
    reasoning_keywords = [
        'design', 'architect', 'refactor', 'optimize',
        'complex', 'integration', 'security', 'performance'
    ]
    reasoning_depth = self._score_keywords(description, reasoning_keywords)

    # Code complexity - how much code will be written/modified?
    if 'lines_estimate' in metadata:
        lines = metadata['lines_estimate']
        code_complexity = min(5, lines // 100 + 1)
    else:
        code_keywords = ['implement', 'create', 'build', 'develop']
        code_complexity = self._score_keywords(description, code_keywords)

    # Domain specificity - does it need specialized knowledge?
    domain_keywords = {
        'database': ['sql', 'query', 'index', 'transaction', 'migration'],
        'security': ['auth', 'encrypt', 'token', 'permission', 'csrf'],
        'frontend': ['component', 'render', 'state', 'css', 'responsive'],
        'devops': ['deploy', 'container', 'ci/cd', 'kubernetes', 'docker'],
    }
    domain_scores = []
    for domain, keywords in domain_keywords.items():
        if any(kw in description.lower() for kw in keywords):
            domain_scores.append(3)
    domain_specificity = max(domain_scores) if domain_scores else 2

    # Context requirements - how much context is needed?
    context_keywords = [
        'across', 'all', 'entire', 'throughout', 'integrate',
        'coordinate', 'multiple', 'various'
    ]
    context_requirements = self._score_keywords(description, context_keywords)

    # Weighted overall score
    overall_score = (
        reasoning_depth * 0.35 +
        code_complexity * 0.25 +
        domain_specificity * 0.25 +
        context_requirements * 0.15
    )

    return TaskComplexity(
        reasoning_depth=reasoning_depth,
        code_complexity=code_complexity,
        domain_specificity=domain_specificity,
        context_requirements=context_requirements,
        overall_score=overall_score
    )

def _score_keywords(self, text: str, keywords: List[str]) -> int:
    """Score text based on keyword presence (1-5)"""
    text_lower = text.lower()
    matches = sum(1 for kw in keywords if kw in text_lower)
    if matches == 0:
        return 1
    elif matches <= 2:
        return 2
    elif matches <= 4:
        return 3
    elif matches <= 6:
        return 4
    else:
        return 5
```

**Acceptance Criteria:**
- [ ] Scores tasks consistently
- [ ] Covers multiple dimensions
- [ ] Weights configurable
- [ ] Fast execution

---

### 6.3 Historical Performance Learning

**Description:** Learn from task outcomes to improve model selection.

**Implementation:**

```python
async def record_outcome(
    self,
    task_id: int,
    model: ModelTier,
    success: bool,
    tokens_used: Dict,
    duration: float
) -> None:
    """
    Record task outcome for learning.

    Updates performance statistics that inform future selections.
    """
    task = await self._get_task(task_id)
    complexity = self.analyze_complexity(task)

    # Calculate actual cost
    cost = self._calculate_cost(model, tokens_used)

    # Record in database
    async with DatabaseManager() as db:
        await db.record_agent_cost(
            project_id=self.project_id,
            session_id=task.get('session_id'),
            task_id=task_id,
            model=model.value,
            input_tokens=tokens_used.get('input', 0),
            output_tokens=tokens_used.get('output', 0),
            operation_type=self._categorize_task(task)
        )

    # Update performance cache
    task_type = self._categorize_task(task)
    if task_type not in self._performance_cache:
        self._performance_cache[task_type] = {
            ModelTier.HAIKU: {'success': 0, 'fail': 0, 'cost': 0},
            ModelTier.SONNET: {'success': 0, 'fail': 0, 'cost': 0},
            ModelTier.OPUS: {'success': 0, 'fail': 0, 'cost': 0},
        }

    stats = self._performance_cache[task_type][model]
    if success:
        stats['success'] += 1
    else:
        stats['fail'] += 1
    stats['cost'] += cost

    # Update spent budget
    self.spent_usd += cost

async def get_model_performance(self, task_type: str) -> Dict:
    """Get performance statistics for a task type"""
    if task_type not in self._performance_cache:
        # Load from database
        async with DatabaseManager() as db:
            costs = await db.get_cost_by_task_type(self.project_id)
            # Populate cache...

    return self._performance_cache.get(task_type, {})
```

**Acceptance Criteria:**
- [ ] Records all outcomes
- [ ] Calculates costs accurately
- [ ] Caches for performance
- [ ] Syncs with database

---

### 6.4 Budget Management

**Description:** Implement budget tracking and enforcement.

**Implementation:**

```python
async def check_budget(self, estimated_cost: float) -> Tuple[bool, str]:
    """
    Check if budget allows the estimated cost.

    Returns (allowed, message).
    """
    if self.budget_limit is None:
        return True, "No budget limit configured"

    remaining = self.budget_limit - self.spent_usd

    if estimated_cost > remaining:
        return False, f"Budget exceeded: ${self.spent_usd:.2f}/${self.budget_limit:.2f}"

    if estimated_cost > remaining * 0.8:
        return True, f"Warning: Approaching budget limit (${remaining:.2f} remaining)"

    return True, f"Budget OK: ${remaining:.2f} remaining"

async def get_budget_status(self) -> Dict:
    """Get detailed budget status"""
    return {
        'limit_usd': self.budget_limit,
        'spent_usd': self.spent_usd,
        'remaining_usd': self.budget_limit - self.spent_usd if self.budget_limit else None,
        'percentage_used': (self.spent_usd / self.budget_limit * 100) if self.budget_limit else 0,
        'breakdown_by_model': await self._get_cost_by_model(),
        'breakdown_by_task_type': await self._get_cost_by_task_type(),
    }

async def _enforce_budget_constraint(self, recommendation: ModelRecommendation) -> ModelRecommendation:
    """Downgrade model if budget is tight"""
    allowed, message = await self.check_budget(recommendation.estimated_cost)

    if not allowed:
        # Try cheaper alternatives
        if recommendation.model == ModelTier.OPUS:
            # Try Sonnet
            sonnet_cost = self.estimate_cost(ModelTier.SONNET, self._estimate_tokens(task))
            if sonnet_cost <= self.budget_limit - self.spent_usd:
                return ModelRecommendation(
                    model=ModelTier.SONNET,
                    confidence=recommendation.confidence * 0.8,
                    reason=f"Downgraded from Opus due to budget: {message}",
                    estimated_cost=sonnet_cost,
                    alternative=ModelTier.OPUS
                )

        # Last resort - Haiku
        haiku_cost = self.estimate_cost(ModelTier.HAIKU, self._estimate_tokens(task))
        return ModelRecommendation(
            model=ModelTier.HAIKU,
            confidence=0.5,
            reason=f"Using Haiku due to budget constraints: {message}",
            estimated_cost=haiku_cost,
            alternative=recommendation.model
        )

    return recommendation
```

**Acceptance Criteria:**
- [ ] Tracks spending accurately
- [ ] Enforces budget limits
- [ ] Downgrades gracefully
- [ ] Provides clear warnings

---

### 6.5 Configuration Overrides

**Description:** Allow per-task-type model overrides.

**Configuration:**

```yaml
# .yokeflow.yaml
cost:
  enabled: true
  budget_limit_usd: 50.0
  optimization_enabled: true

  # Default model for all tasks
  default_model: "sonnet"

  # Override by task type
  model_overrides:
    architecture: "opus"      # Design tasks need Opus
    security: "opus"          # Security-critical tasks
    documentation: "haiku"    # Simple documentation
    test_creation: "sonnet"   # Tests need good quality
    bug_fix: "sonnet"         # Standard fixes

  # Override by epic priority
  priority_overrides:
    critical: "opus"
    high: "sonnet"
    medium: "sonnet"
    low: "haiku"
```

**Implementation:**

```python
def _apply_overrides(
    self,
    task: Dict,
    recommendation: ModelRecommendation
) -> ModelRecommendation:
    """Apply configuration overrides"""

    # Check task type override
    task_type = self._categorize_task(task)
    if task_type in self.config.get('model_overrides', {}):
        override_model = ModelTier(self.config['model_overrides'][task_type])
        return ModelRecommendation(
            model=override_model,
            confidence=1.0,
            reason=f"Configuration override for task type: {task_type}",
            estimated_cost=self.estimate_cost(override_model, self._estimate_tokens(task))
        )

    # Check priority override
    epic_priority = task.get('epic', {}).get('priority', 'medium')
    if epic_priority in self.config.get('priority_overrides', {}):
        override_model = ModelTier(self.config['priority_overrides'][epic_priority])
        return ModelRecommendation(
            model=override_model,
            confidence=1.0,
            reason=f"Configuration override for priority: {epic_priority}",
            estimated_cost=self.estimate_cost(override_model, self._estimate_tokens(task))
        )

    return recommendation
```

**Acceptance Criteria:**
- [ ] Task type overrides work
- [ ] Priority overrides work
- [ ] Overrides take precedence
- [ ] Configuration validates

---

### 6.6 Cost Tracking API

**Description:** Add API endpoints for cost monitoring.

**Endpoints:**

```python
@app.get("/api/projects/{project_id}/costs")
async def get_project_costs(project_id: str):
    """Get cost breakdown for a project"""
    return {
        "total_cost_usd": 12.45,
        "budget_limit_usd": 50.0,
        "percentage_used": 24.9,
        "by_model": {
            "opus": {"cost": 8.20, "calls": 5},
            "sonnet": {"cost": 4.15, "calls": 42},
            "haiku": {"cost": 0.10, "calls": 15}
        },
        "by_task_type": {
            "implementation": 7.50,
            "testing": 3.20,
            "documentation": 0.45,
            "bug_fix": 1.30
        },
        "by_date": [
            {"date": "2024-01-15", "cost": 5.20},
            {"date": "2024-01-16", "cost": 7.25}
        ]
    }

@app.get("/api/projects/{project_id}/costs/forecast")
async def get_cost_forecast(project_id: str):
    """Forecast remaining project cost"""
    return {
        "completed_tasks": 47,
        "remaining_tasks": 23,
        "avg_cost_per_task": 0.26,
        "estimated_remaining_cost": 5.98,
        "estimated_total_cost": 18.43,
        "confidence": 0.85
    }

@app.get("/api/projects/{project_id}/model-stats")
async def get_model_statistics(project_id: str):
    """Get model performance statistics"""
    return {
        "opus": {
            "tasks_completed": 5,
            "success_rate": 1.0,
            "avg_tokens": 15000,
            "avg_cost": 1.64
        },
        "sonnet": {
            "tasks_completed": 42,
            "success_rate": 0.95,
            "avg_tokens": 8000,
            "avg_cost": 0.10
        }
    }
```

**Acceptance Criteria:**
- [ ] Cost endpoints return accurate data
- [ ] Forecast uses historical data
- [ ] Model stats track performance
- [ ] Data persists across sessions

---

## Testing Requirements

### Unit Tests

```python
class TestModelSelector:
    def test_complexity_scoring(self):
        """Scores task complexity correctly"""

    def test_model_selection_simple_task(self):
        """Selects Haiku for simple tasks"""

    def test_model_selection_complex_task(self):
        """Selects Opus for complex tasks"""

    def test_budget_enforcement(self):
        """Respects budget limits"""

    def test_configuration_override(self):
        """Overrides take precedence"""

    def test_outcome_recording(self):
        """Records outcomes correctly"""

    def test_performance_learning(self):
        """Learns from historical data"""
```

### Integration Tests

```python
class TestCostIntegration:
    def test_end_to_end_cost_tracking(self):
        """Full task execution with cost tracking"""

    def test_budget_limit_downgrade(self):
        """Downgrades model when approaching limit"""

    def test_api_cost_endpoints(self):
        """API returns correct cost data"""
```

---

## Dependencies

- Epic 01: Foundation (agent_costs table)
- Epic 05: Self-Learning (expertise informs complexity)

## Dependents

- Epic 04: Parallel Executor (uses model selection)

---

## Notes

- Consider token counting before API call for better estimates
- May need to handle rate limits per model
- Pricing may change - make it configurable
- Consider caching model recommendations for similar tasks
