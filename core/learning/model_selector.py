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
from typing import Dict, Optional, Any
from uuid import UUID
from enum import Enum
import logging

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
        budget_reason = ""

        if not within_budget or remaining < 1.0:  # Less than $1 remaining
            # Force HAIKU when budget is exhausted or very low
            if recommended_model != ModelTier.HAIKU:
                logger.warning(f"Task {task_id}: Budget exhausted, forcing HAIKU (was {recommended_model.value})")
                recommended_model = ModelTier.HAIKU
                budget_reason = " - DOWNGRADED: budget exhausted"
        elif remaining < 10.0 and recommended_model == ModelTier.OPUS:
            # Downgrade OPUS to SONNET when budget is low
            logger.warning(f"Task {task_id}: Low budget (${remaining:.2f}), downgrading OPUS to SONNET")
            recommended_model = ModelTier.SONNET
            budget_reason = f" - DOWNGRADED: low budget (${remaining:.2f} remaining)"

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
        # For now, return None - will be implemented in task 909
        # This method will query agent_costs table to find:
        # - Success/failure rates per model for similar task types
        # - Average duration and cost per model
        # - Recent trends in model performance

        # Example logic (to be implemented):
        # - If HAIKU has <70% success rate on similar tasks -> upgrade to SONNET
        # - If SONNET completes similar tasks faster than OPUS -> keep SONNET
        # - If model consistently times out -> upgrade to more capable model

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

        Returns:
            Tuple of (within_budget, remaining_usd)
        """
        # Stub - will be fully implemented in task 910
        # For now, return unlimited budget to allow testing
        # Task 910 will implement actual budget tracking from agent_costs table
        return (True, 999999.0)

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

        Args:
            task_id: Task ID
            model: Model used
            success: Whether task succeeded
            duration: Execution time in seconds
            tokens: Dict with input_tokens and output_tokens
        """
        # Stub - will be implemented in Epic 95
        logger.warning("ModelSelector.record_outcome() not yet implemented")
