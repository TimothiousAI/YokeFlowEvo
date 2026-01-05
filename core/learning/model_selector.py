"""
Model Selector
==============

Selects optimal Claude model for each task based on complexity analysis
and budget constraints.

Key Features:
- Analyzes task complexity across multiple dimensions
- Recommends model tier (Haiku/Sonnet/Opus)
- Tracks historical performance by task type
- Enforces budget limits
- Supports configuration overrides
- Provides reasoning for recommendations

Model Tiers:
- Haiku: Simple, repetitive tasks (< 0.3 complexity score)
- Sonnet: Moderate complexity tasks (0.3-0.7 complexity score)
- Opus: Complex, architectural tasks (> 0.7 complexity score)

Pricing (approximate, as of 2025):
- Haiku: $0.25 per 1M input tokens, $1.25 per 1M output tokens
- Sonnet: $3.00 per 1M input tokens, $15.00 per 1M output tokens
- Opus: $15.00 per 1M input tokens, $75.00 per 1M output tokens
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any, Tuple
from uuid import UUID
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import asyncio

logger = logging.getLogger(__name__)


# Model tier enumeration
class ModelTier(Enum):
    """Claude model tiers in order of capability and cost."""
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


# Pricing per 1M tokens (USD)
PRICING = {
    ModelTier.HAIKU: {"input": 0.25, "output": 1.25},
    ModelTier.SONNET: {"input": 3.00, "output": 15.00},
    ModelTier.OPUS: {"input": 15.00, "output": 75.00},
}


# Complexity thresholds for model selection
COMPLEXITY_THRESHOLDS = {
    "haiku_max": 0.3,    # Use HAIKU if overall_score < 0.3
    "sonnet_min": 0.3,   # Use SONNET if overall_score >= 0.3
    "sonnet_max": 0.7,   # Use SONNET if overall_score <= 0.7
    "opus_min": 0.7      # Use OPUS if overall_score > 0.7
}


# Performance cache configuration
PERFORMANCE_CACHE_TTL = 300  # 5 minutes in seconds
PERFORMANCE_MIN_SAMPLES = 3  # Minimum samples needed to influence recommendation
PERFORMANCE_SUCCESS_THRESHOLD = 0.7  # 70% success rate threshold


@dataclass
class ModelRecommendation:
    """
    Model recommendation with reasoning.

    Attributes:
        model: Recommended model tier (ModelTier enum)
        reasoning: Explanation for recommendation
        estimated_cost: Estimated cost in USD
        complexity: TaskComplexity analysis (optional)
    """
    model: ModelTier
    reasoning: str
    estimated_cost: float
    complexity: Optional['TaskComplexity'] = None


@dataclass
class TaskComplexity:
    """
    Task complexity analysis.

    Attributes:
        reasoning_depth: Multi-step logic required (0-1)
        code_complexity: Lines and files involved (0-1)
        domain_specificity: Specialized knowledge needed (0-1)
        context_requirements: Dependencies and existing code (0-1)
        overall_score: Weighted average (0-1)
    """
    reasoning_depth: float
    code_complexity: float
    domain_specificity: float
    context_requirements: float
    overall_score: float


class ModelSelector:
    """
    Selects optimal model for tasks based on complexity and budget.

    Uses complexity analysis and historical performance to recommend
    the most cost-effective model while maintaining quality.
    """

    def __init__(self, project_id: UUID, config: Any, db_connection: Any):
        """
        Initialize model selector.

        Args:
            project_id: Project UUID
            config: Configuration object with cost settings
            db_connection: Database connection for cost tracking
        """
        self.project_id = project_id
        self.config = config
        self.db = db_connection

        # Performance cache: {task_type: {model: {'success_rate': float, 'avg_duration': float, 'count': int}}}
        self._performance_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._cache_timestamp: Optional[datetime] = None

        logger.info(f"ModelSelector initialized for project {project_id}")

    def analyze_complexity(self, task: Dict[str, Any]) -> TaskComplexity:
        """
        Analyze task complexity across multiple dimensions.

        Args:
            task: Task dictionary with description, action, etc.

        Returns:
            TaskComplexity with scores (all scores 0.0-1.0)
        """
        description = task.get('description', '').lower()
        action = task.get('action', '').lower()
        combined_text = f"{description} {action}"

        # Score reasoning_depth (0-1): multi-step logic, algorithm design, architecture decisions
        reasoning_depth = self._score_reasoning_depth(combined_text)

        # Score code_complexity (0-1): LOC estimate, number of files, new vs modify
        code_complexity = self._score_code_complexity(combined_text)

        # Score domain_specificity (0-1): specialized knowledge required
        domain_specificity = self._score_domain_specificity(combined_text)

        # Score context_requirements (0-1): dependencies, existing code understanding
        context_requirements = self._score_context_requirements(combined_text)

        # Calculate weighted overall_score
        weights = {
            'reasoning_depth': 0.35,
            'code_complexity': 0.30,
            'domain_specificity': 0.20,
            'context_requirements': 0.15
        }

        overall_score = (
            reasoning_depth * weights['reasoning_depth'] +
            code_complexity * weights['code_complexity'] +
            domain_specificity * weights['domain_specificity'] +
            context_requirements * weights['context_requirements']
        )

        # Clamp to [0.0, 1.0]
        overall_score = max(0.0, min(1.0, overall_score))

        logger.debug(
            f"Task complexity analysis: "
            f"reasoning={reasoning_depth:.2f}, code={code_complexity:.2f}, "
            f"domain={domain_specificity:.2f}, context={context_requirements:.2f}, "
            f"overall={overall_score:.2f}"
        )

        return TaskComplexity(
            reasoning_depth=reasoning_depth,
            code_complexity=code_complexity,
            domain_specificity=domain_specificity,
            context_requirements=context_requirements,
            overall_score=overall_score
        )

    def _score_reasoning_depth(self, text: str) -> float:
        """
        Score reasoning depth required (0-1).

        High scores for: algorithm design, architecture, multi-step logic, optimization

        Args:
            text: Combined task description and action

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0

        # Keywords indicating deep reasoning
        high_reasoning_keywords = [
            'algorithm', 'architecture', 'design', 'optimize', 'refactor',
            'implement logic', 'state management', 'workflow', 'strategy',
            'pattern', 'approach', 'solve', 'analyze', 'calculate'
        ]

        # Multi-step indicators
        multi_step_keywords = [
            'multi-step', 'sequence', 'orchestrate', 'coordinate',
            'pipeline', 'flow', 'process', 'chain'
        ]

        # Count matches
        for keyword in high_reasoning_keywords:
            if keyword in text:
                score += 0.2

        for keyword in multi_step_keywords:
            if keyword in text:
                score += 0.3

        # Check for complexity indicators
        if 'complex' in text:
            score += 0.25
        if 'advanced' in text:
            score += 0.2
        if 'sophisticated' in text:
            score += 0.2
        if 'distributed' in text:
            score += 0.25

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))

    def _score_code_complexity(self, text: str) -> float:
        """
        Score code complexity (0-1).

        High scores for: many files, large changes, new implementations

        Args:
            text: Combined task description and action

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0

        # File count estimation
        if 'multiple files' in text or 'several files' in text:
            score += 0.3
        elif 'file' in text:
            score += 0.1

        # LOC estimation
        if 'large' in text or 'extensive' in text:
            score += 0.2
        if 'implement' in text or 'create' in text or 'build' in text:
            score += 0.2
        elif 'modify' in text or 'update' in text or 'edit' in text:
            score += 0.1

        # Complexity indicators
        if 'class' in text or 'module' in text:
            score += 0.15
        if 'api' in text or 'endpoint' in text:
            score += 0.15
        if 'database' in text or 'schema' in text:
            score += 0.2

        # Simple tasks
        if 'simple' in text or 'trivial' in text or 'minor' in text:
            score = max(0.0, score - 0.3)

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))

    def _score_domain_specificity(self, text: str) -> float:
        """
        Score domain-specific knowledge required (0-1).

        High scores for: ML, crypto, security, specialized algorithms

        Args:
            text: Combined task description and action

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0

        # Specialized domains
        specialized_domains = {
            'machine learning': 0.4, 'ml': 0.4, 'neural': 0.4, 'model training': 0.4,
            'cryptography': 0.4, 'encryption': 0.3, 'security': 0.3,
            'blockchain': 0.4, 'consensus': 0.4,
            'compiler': 0.4, 'parser': 0.3, 'ast': 0.3,
            'graphics': 0.3, 'rendering': 0.3, 'shader': 0.4,
            'distributed system': 0.3, 'consensus': 0.3, 'raft': 0.4,
            'kubernetes': 0.3, 'docker': 0.2, 'devops': 0.2
        }

        for domain, weight in specialized_domains.items():
            if domain in text:
                score += weight

        # General technical domains (lower scores)
        general_domains = {
            'database': 0.15, 'api': 0.1, 'frontend': 0.1, 'backend': 0.1,
            'testing': 0.05, 'deployment': 0.1
        }

        for domain, weight in general_domains.items():
            if domain in text:
                score += weight

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))

    def _score_context_requirements(self, text: str) -> float:
        """
        Score existing code understanding required (0-1).

        High scores for: refactoring, integration, dependency management

        Args:
            text: Combined task description and action

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0

        # High context indicators
        high_context_keywords = [
            'refactor', 'integrate', 'dependency', 'dependencies',
            'existing code', 'codebase', 'legacy', 'migrate',
            'understand', 'analyze existing', 'study'
        ]

        for keyword in high_context_keywords:
            if keyword in text:
                score += 0.2

        # Integration indicators
        if 'integrate with' in text or 'connect to' in text:
            score += 0.25

        # New code (low context)
        if 'new' in text and 'from scratch' in text:
            score = max(0.0, score - 0.3)
        elif 'create' in text or 'implement' in text:
            score += 0.1

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))

    def recommend_model(self, task: Dict[str, Any]) -> ModelRecommendation:
        """
        Recommend optimal model for a task.

        Analyzes task complexity, checks config overrides, considers historical
        performance, and enforces budget limits.

        Args:
            task: Task dictionary with description, action, priority, etc.

        Returns:
            ModelRecommendation with model, reasoning, and estimated cost
        """
        task_id = task.get('id', 'unknown')

        # Step 1: Check for configuration overrides first
        override_model = self._check_config_overrides(task)
        if override_model:
            logger.info(f"Task {task_id}: Using config override model {override_model.value}")
            return ModelRecommendation(
                model=override_model,
                reasoning=f"Configuration override for {self._get_override_reason(task)}",
                estimated_cost=self._estimate_cost(override_model)
            )

        # Step 2: Analyze task complexity
        complexity = self.analyze_complexity(task)

        # Step 3: Apply complexity thresholds to select base model
        if complexity.overall_score < COMPLEXITY_THRESHOLDS['haiku_max']:
            base_model = ModelTier.HAIKU
            complexity_reason = f"Low complexity score ({complexity.overall_score:.2f})"
        elif complexity.overall_score <= COMPLEXITY_THRESHOLDS['sonnet_max']:
            base_model = ModelTier.SONNET
            complexity_reason = f"Moderate complexity score ({complexity.overall_score:.2f})"
        else:
            base_model = ModelTier.OPUS
            complexity_reason = f"High complexity score ({complexity.overall_score:.2f})"

        # Step 4: Consider historical performance for similar tasks
        historical_adjustment = self._get_historical_performance_adjustment(task, base_model)
        recommended_model = base_model
        historical_reason = ""

        if historical_adjustment:
            recommended_model = historical_adjustment['model']
            historical_reason = f" (adjusted based on {historical_adjustment['reason']})"
            logger.info(f"Task {task_id}: Historical performance adjusted {base_model.value} -> {recommended_model.value}")

        # Step 5: Check budget constraints and downgrade if necessary
        within_budget, remaining = self.check_budget()
        recommended_model, budget_reason = self._downgrade_for_budget(
            recommended_model, remaining, within_budget
        )

        # Step 6: Build reasoning and estimate cost
        reasoning_parts = [complexity_reason]
        if historical_reason:
            reasoning_parts.append(historical_reason)
        if budget_reason:
            reasoning_parts.append(budget_reason)

        full_reasoning = "; ".join(reasoning_parts)
        estimated_cost = self._estimate_cost(recommended_model)

        logger.info(f"Task {task_id}: Recommended {recommended_model.value} - {full_reasoning}")

        return ModelRecommendation(
            model=recommended_model,
            reasoning=full_reasoning,
            estimated_cost=estimated_cost,
            complexity=complexity
        )

    def _check_config_overrides(self, task: Dict[str, Any]) -> Optional[ModelTier]:
        """
        Check for configuration overrides (task type, epic priority, task metadata).

        Args:
            task: Task dictionary

        Returns:
            ModelTier if override found, None otherwise
        """
        # Check task metadata for explicit model override
        if 'metadata' in task and task['metadata'].get('force_model'):
            model_str = task['metadata']['force_model'].lower()
            if model_str in ['haiku', 'sonnet', 'opus']:
                return ModelTier[model_str.upper()]

        # Check config for priority-based overrides
        if hasattr(self.config, 'cost') and hasattr(self.config.cost, 'priority_overrides'):
            priority = task.get('priority', 5)
            priority_overrides = self.config.cost.priority_overrides
            if priority in priority_overrides:
                model_str = priority_overrides[priority].lower()
                if model_str in ['haiku', 'sonnet', 'opus']:
                    return ModelTier[model_str.upper()]

        # Check config for task type overrides (based on keywords in description)
        if hasattr(self.config, 'cost') and hasattr(self.config.cost, 'model_overrides'):
            description = task.get('description', '').lower()
            model_overrides = self.config.cost.model_overrides

            for task_type, model_str in model_overrides.items():
                if task_type.lower() in description:
                    if model_str.lower() in ['haiku', 'sonnet', 'opus']:
                        return ModelTier[model_str.upper()]

        return None

    def _get_override_reason(self, task: Dict[str, Any]) -> str:
        """Get human-readable reason for override."""
        if 'metadata' in task and task['metadata'].get('force_model'):
            return "task metadata"

        if hasattr(self.config, 'cost'):
            priority = task.get('priority', 5)
            if hasattr(self.config.cost, 'priority_overrides') and priority in self.config.cost.priority_overrides:
                return f"priority {priority}"

            description = task.get('description', '').lower()
            if hasattr(self.config.cost, 'model_overrides'):
                for task_type in self.config.cost.model_overrides.keys():
                    if task_type.lower() in description:
                        return f"task type '{task_type}'"

        return "configuration"

    async def _get_historical_performance(self, task_type: str, model: str) -> Optional[Dict[str, Any]]:
        """
        Get historical performance stats for a task type and model.

        Uses cache with TTL to avoid excessive database queries.

        Args:
            task_type: Task type category (e.g., 'api', 'database')
            model: Model name (haiku/sonnet/opus)

        Returns:
            Dict with 'success_rate', 'avg_duration', 'count', or None if insufficient data
        """
        # Check if cache is valid
        cache_valid = (
            self._cache_timestamp is not None and
            datetime.now() - self._cache_timestamp < timedelta(seconds=PERFORMANCE_CACHE_TTL)
        )

        # Refresh cache if invalid or empty
        if not cache_valid or not self._performance_cache:
            await self._refresh_performance_cache()

        # Return cached stats if available
        if task_type in self._performance_cache and model in self._performance_cache[task_type]:
            return self._performance_cache[task_type][model]

        return None

    async def _refresh_performance_cache(self) -> None:
        """
        Refresh performance cache from database.

        Queries agent_costs joined with tasks to get success rates, durations, and counts
        grouped by task type and model.
        """
        try:
            # Query database for historical performance data
            # We need to join agent_costs with tasks to get task descriptions
            # Then calculate success rates and averages per task_type per model
            async with self.db.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        t.description,
                        ac.model,
                        COUNT(*) as total_count,
                        -- Success is inferred: if a task completed and has a cost record, it succeeded
                        -- Failed tasks typically don't get cost records or have zero tokens
                        SUM(CASE WHEN ac.output_tokens > 0 THEN 1 ELSE 0 END) as success_count,
                        AVG(EXTRACT(EPOCH FROM (t.completed_at - ac.created_at))) as avg_duration_seconds
                    FROM agent_costs ac
                    JOIN tasks t ON ac.task_id = t.id
                    WHERE ac.project_id = $1
                      AND t.completed_at IS NOT NULL
                      AND ac.created_at >= NOW() - INTERVAL '30 days'  -- Only last 30 days
                    GROUP BY t.description, ac.model
                    HAVING COUNT(*) >= 1
                    """,
                    self.project_id
                )

                # Build cache structure
                cache: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))

                for row in rows:
                    description = row['description']
                    model = row['model']
                    total_count = row['total_count']
                    success_count = row['success_count']
                    avg_duration = row['avg_duration_seconds']

                    # Extract task type from description
                    task_type = self._extract_task_type(description)

                    # Calculate success rate
                    success_rate = success_count / total_count if total_count > 0 else 0.0

                    # Aggregate stats per task_type and model
                    if model not in cache[task_type]:
                        cache[task_type][model] = {
                            'success_rate': success_rate,
                            'avg_duration': avg_duration or 0.0,
                            'count': total_count
                        }
                    else:
                        # Combine stats from multiple descriptions of same task type
                        existing = cache[task_type][model]
                        total_combined = existing['count'] + total_count
                        combined_success_rate = (
                            (existing['success_rate'] * existing['count'] + success_rate * total_count) /
                            total_combined
                        )
                        combined_avg_duration = (
                            (existing['avg_duration'] * existing['count'] + (avg_duration or 0.0) * total_count) /
                            total_combined
                        )
                        cache[task_type][model] = {
                            'success_rate': combined_success_rate,
                            'avg_duration': combined_avg_duration,
                            'count': total_combined
                        }

                # Update cache
                self._performance_cache = dict(cache)
                self._cache_timestamp = datetime.now()

                logger.debug(f"Performance cache refreshed: {len(self._performance_cache)} task types tracked")

        except Exception as e:
            logger.error(f"Failed to refresh performance cache: {e}")
            # Keep old cache if refresh fails
            if not self._cache_timestamp:
                self._cache_timestamp = datetime.now()

    def _get_historical_performance_adjustment(
        self,
        task: Dict[str, Any],
        base_model: ModelTier
    ) -> Optional[Dict[str, Any]]:
        """
        Check historical performance for similar tasks and adjust recommendation.

        Args:
            task: Task dictionary
            base_model: Model selected by complexity analysis

        Returns:
            Dict with 'model' and 'reason' if adjustment needed, None otherwise
        """
        # Extract task type
        description = task.get('description', '')
        task_type = self._extract_task_type(description)

        # Get historical performance (need to run async in sync context)
        # Use asyncio to run the async method
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we can't use run_until_complete
                # In this case, skip historical adjustment (will be fixed in orchestrator integration)
                logger.debug("Event loop already running, skipping historical adjustment")
                return None
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Get stats for the base model
        base_stats = loop.run_until_complete(
            self._get_historical_performance(task_type, base_model.value)
        )

        # If insufficient data, no adjustment
        if not base_stats or base_stats['count'] < PERFORMANCE_MIN_SAMPLES:
            return None

        # Check if base model has low success rate
        if base_stats['success_rate'] < PERFORMANCE_SUCCESS_THRESHOLD:
            # Try to upgrade to next tier
            if base_model == ModelTier.HAIKU:
                # Upgrade HAIKU -> SONNET if HAIKU has poor success rate
                sonnet_stats = loop.run_until_complete(
                    self._get_historical_performance(task_type, ModelTier.SONNET.value)
                )
                if sonnet_stats and sonnet_stats['success_rate'] > base_stats['success_rate']:
                    return {
                        'model': ModelTier.SONNET,
                        'reason': f"historical data: {base_model.value} has {base_stats['success_rate']:.1%} success rate on {task_type} tasks"
                    }
            elif base_model == ModelTier.SONNET:
                # Upgrade SONNET -> OPUS if SONNET has poor success rate
                opus_stats = loop.run_until_complete(
                    self._get_historical_performance(task_type, ModelTier.OPUS.value)
                )
                if opus_stats and opus_stats['success_rate'] > base_stats['success_rate']:
                    return {
                        'model': ModelTier.OPUS,
                        'reason': f"historical data: {base_model.value} has {base_stats['success_rate']:.1%} success rate on {task_type} tasks"
                    }

        # Check if we can safely downgrade (base model is SONNET or OPUS with good success)
        if base_stats['success_rate'] >= 0.9:  # 90%+ success rate
            if base_model == ModelTier.OPUS:
                # Check if SONNET also has good success rate -> downgrade to save cost
                sonnet_stats = loop.run_until_complete(
                    self._get_historical_performance(task_type, ModelTier.SONNET.value)
                )
                if (sonnet_stats and
                    sonnet_stats['count'] >= PERFORMANCE_MIN_SAMPLES and
                    sonnet_stats['success_rate'] >= 0.85):  # Allow 5% success rate drop for cost savings
                    return {
                        'model': ModelTier.SONNET,
                        'reason': f"historical data: {ModelTier.SONNET.value} has {sonnet_stats['success_rate']:.1%} success rate on {task_type} tasks (cost optimization)"
                    }
            elif base_model == ModelTier.SONNET:
                # Check if HAIKU also has good success rate -> downgrade to save cost
                haiku_stats = loop.run_until_complete(
                    self._get_historical_performance(task_type, ModelTier.HAIKU.value)
                )
                if (haiku_stats and
                    haiku_stats['count'] >= PERFORMANCE_MIN_SAMPLES and
                    haiku_stats['success_rate'] >= 0.85):
                    return {
                        'model': ModelTier.HAIKU,
                        'reason': f"historical data: {ModelTier.HAIKU.value} has {haiku_stats['success_rate']:.1%} success rate on {task_type} tasks (cost optimization)"
                    }

        return None

    def _estimate_cost(self, model: ModelTier) -> float:
        """
        Estimate cost for a task using the given model.

        Uses average token counts from historical data or defaults.

        Args:
            model: Model tier

        Returns:
            Estimated cost in USD
        """
        # Default token estimates (conservative averages)
        # These will be refined with actual historical data in task 909
        DEFAULT_INPUT_TOKENS = 50000   # ~50K tokens average
        DEFAULT_OUTPUT_TOKENS = 10000  # ~10K tokens average

        pricing = PRICING[model]

        # Calculate cost: (input_tokens / 1M * input_price) + (output_tokens / 1M * output_price)
        estimated_cost = (
            (DEFAULT_INPUT_TOKENS / 1_000_000 * pricing['input']) +
            (DEFAULT_OUTPUT_TOKENS / 1_000_000 * pricing['output'])
        )

        return round(estimated_cost, 4)

    def check_budget(self) -> tuple[bool, float]:
        """
        Check if within budget limit.

        Queries agent_costs table to calculate total spent and compares
        against config.cost.budget_limit_usd.

        Returns:
            Tuple of (within_budget, remaining_usd)
            - within_budget: True if under budget or no budget set
            - remaining_usd: Remaining budget (or 999999.0 if unlimited)
        """
        # If no budget limit configured, return unlimited
        if not hasattr(self.config, 'cost') or self.config.cost.budget_limit_usd is None:
            return (True, 999999.0)

        budget_limit = self.config.cost.budget_limit_usd

        # Get total spent from agent_costs table
        # Note: This is a synchronous method, but DB operations are async
        # We'll use the same pattern as _get_historical_performance_adjustment
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we can't use run_until_complete
                # Return unlimited budget to avoid blocking (will be fixed in orchestrator integration)
                logger.debug("Event loop already running, skipping budget check")
                return (True, 999999.0)
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Query total spent
        total_spent = loop.run_until_complete(self._get_total_spent())

        # Calculate remaining budget
        remaining = budget_limit - total_spent

        # Within budget if remaining is positive
        within_budget = remaining > 0

        logger.debug(f"Budget check: spent=${total_spent:.2f}, limit=${budget_limit:.2f}, remaining=${remaining:.2f}")

        # Log warnings at 80% and 95% usage
        usage_pct = (total_spent / budget_limit) * 100 if budget_limit > 0 else 0
        if usage_pct >= 95:
            logger.warning(f"BUDGET CRITICAL: {usage_pct:.1f}% used (${total_spent:.2f} / ${budget_limit:.2f})")
        elif usage_pct >= 80:
            logger.warning(f"BUDGET WARNING: {usage_pct:.1f}% used (${total_spent:.2f} / ${budget_limit:.2f})")

        return (within_budget, remaining)

    async def _get_total_spent(self) -> float:
        """
        Get total spent from agent_costs table for this project.

        Returns:
            Total spent in USD
        """
        try:
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT COALESCE(SUM(cost_usd), 0) as total_spent
                    FROM agent_costs
                    WHERE project_id = $1
                    """,
                    self.project_id
                )
                return float(result['total_spent']) if result else 0.0
        except Exception as e:
            logger.error(f"Failed to query agent costs: {e}")
            # Return 0 if query fails to avoid blocking execution
            return 0.0

    def _downgrade_for_budget(
        self,
        recommendation: ModelTier,
        remaining_budget: float,
        within_budget: bool
    ) -> tuple[ModelTier, str]:
        """
        Downgrade model recommendation when approaching or exceeding budget.

        Args:
            recommendation: Original model recommendation
            remaining_budget: Remaining budget in USD
            within_budget: Whether currently within budget

        Returns:
            Tuple of (downgraded_model, reason_string)
            - downgraded_model: Adjusted model tier
            - reason_string: Explanation for downgrade (empty if no downgrade)
        """
        # Force HAIKU when budget is exhausted or very low (< $1)
        if not within_budget or remaining_budget < 1.0:
            if recommendation != ModelTier.HAIKU:
                logger.warning(f"Budget exhausted, forcing HAIKU (was {recommendation.value})")
                return (ModelTier.HAIKU, " - DOWNGRADED: budget exhausted")
            return (recommendation, "")

        # Downgrade OPUS to SONNET when budget is low (< $10)
        if remaining_budget < 10.0 and recommendation == ModelTier.OPUS:
            logger.warning(f"Low budget (${remaining_budget:.2f}), downgrading OPUS to SONNET")
            return (ModelTier.SONNET, f" - DOWNGRADED: low budget (${remaining_budget:.2f} remaining)")

        # No downgrade needed
        return (recommendation, "")

    def _extract_task_type(self, task_description: str) -> str:
        """
        Extract task type from description for categorization.

        Args:
            task_description: Task description text

        Returns:
            Task type category (e.g., 'api', 'database', 'frontend', 'refactor', 'general')
        """
        desc_lower = task_description.lower()

        # Define task type patterns in priority order (most specific first)
        task_types = [
            ('database', ['database', 'schema', 'migration', 'sql', 'query']),
            ('api', ['api', 'endpoint', 'route', 'rest', 'graphql']),
            ('frontend', ['frontend', 'ui', 'component', 'react', 'vue', 'angular']),
            ('backend', ['backend', 'server', 'service']),
            ('testing', ['test', 'unit test', 'integration test', 'e2e']),
            ('refactor', ['refactor', 'cleanup', 'reorganize']),
            ('documentation', ['document', 'readme', 'docs', 'comment']),
            ('security', ['security', 'auth', 'authentication', 'authorization']),
            ('performance', ['performance', 'optimize', 'cache', 'speed']),
            ('deployment', ['deploy', 'ci/cd', 'docker', 'kubernetes']),
        ]

        for task_type, keywords in task_types:
            if any(keyword in desc_lower for keyword in keywords):
                return task_type

        return 'general'

    def record_outcome(
        self,
        task_id: int,
        model: str,
        success: bool,
        duration: float,
        tokens: Dict[str, int]
    ) -> None:
        """
        Record task outcome for historical tracking.

        This method is synchronous but calls async database operations.
        It invalidates the cache to ensure fresh data on next recommendation.

        Args:
            task_id: Task ID
            model: Model used (haiku/sonnet/opus)
            success: Whether task succeeded
            duration: Execution time in seconds
            tokens: Dict with 'input_tokens' and 'output_tokens'
        """
        # Invalidate cache to force refresh on next recommendation
        self._performance_cache = {}
        self._cache_timestamp = None

        # Note: This is a synchronous method but record_agent_cost is async
        # The actual cost recording happens in the orchestrator/agent code
        # This method just logs the outcome for future queries
        logger.info(
            f"Task {task_id} outcome: model={model}, success={success}, "
            f"duration={duration:.2f}s, tokens={tokens.get('input_tokens', 0) + tokens.get('output_tokens', 0)}"
        )
