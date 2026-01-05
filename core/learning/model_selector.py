"""
Model Selector

Intelligent model selection based on task complexity, historical performance,
and budget constraints.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Available model tiers."""
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


# Pricing per 1M tokens (input/output) in USD
PRICING = {
    ModelTier.HAIKU: {'input': 0.25, 'output': 1.25},
    ModelTier.SONNET: {'input': 3.0, 'output': 15.0},
    ModelTier.OPUS: {'input': 15.0, 'output': 75.0},
}

# Complexity thresholds for model selection
COMPLEXITY_THRESHOLDS = {
    ModelTier.HAIKU: 0.3,   # Use for complexity < 0.3
    ModelTier.SONNET: 0.7,  # Use for complexity 0.3 - 0.7
    ModelTier.OPUS: 1.0,    # Use for complexity > 0.7
}


@dataclass
class TaskComplexity:
    """Complexity analysis of a task."""
    reasoning_depth: float  # 0-1: Multi-step logic, algorithm design
    code_complexity: float  # 0-1: LOC estimate, file count
    domain_specificity: float  # 0-1: Specialized knowledge required
    context_requirements: float  # 0-1: Dependencies, existing code understanding
    overall_score: float  # Weighted average


@dataclass
class ModelRecommendation:
    """Model recommendation with reasoning."""
    model: ModelTier
    reasoning: str
    estimated_cost: float  # USD


class ModelSelector:
    """
    Selects optimal model based on task complexity and constraints.

    Considers:
    - Task complexity analysis
    - Historical performance per model
    - Budget constraints
    - Configuration overrides
    """

    def __init__(self, project_id: int, config: Optional[Dict] = None):
        """
        Initialize the model selector.

        Args:
            project_id: The project ID
            config: Optional configuration dict with budget and overrides
        """
        self.project_id = project_id
        self.config = config or {}
        self._performance_cache: Dict[str, Dict] = {}

    def analyze_complexity(self, task: Dict) -> TaskComplexity:
        """
        Analyze the complexity of a task.

        Args:
            task: The task dictionary

        Returns:
            TaskComplexity analysis
        """
        # TODO: Implement complexity analysis
        raise NotImplementedError("ModelSelector.analyze_complexity() not yet implemented")

    def recommend_model(self, task: Dict) -> ModelRecommendation:
        """
        Recommend a model for a task.

        Args:
            task: The task dictionary

        Returns:
            ModelRecommendation with model, reasoning, and cost estimate
        """
        # TODO: Implement model recommendation
        raise NotImplementedError("ModelSelector.recommend_model() not yet implemented")

    def record_outcome(
        self,
        task_id: int,
        model: ModelTier,
        success: bool,
        duration: float,
        tokens: Dict[str, int]
    ) -> None:
        """
        Record the outcome of a task execution for learning.

        Args:
            task_id: The task ID
            model: The model used
            success: Whether the task succeeded
            duration: Execution duration in seconds
            tokens: Dict with 'input' and 'output' token counts
        """
        # TODO: Implement outcome recording
        raise NotImplementedError("ModelSelector.record_outcome() not yet implemented")

    def check_budget(self) -> tuple[bool, float]:
        """
        Check if we're within budget.

        Returns:
            Tuple of (within_budget, remaining_usd)
        """
        # TODO: Implement budget checking
        raise NotImplementedError("ModelSelector.check_budget() not yet implemented")

    def _get_historical_performance(
        self,
        task_type: str,
        model: ModelTier
    ) -> Optional[Dict]:
        """
        Get historical performance data for a task type and model.

        Args:
            task_type: The type of task
            model: The model tier

        Returns:
            Performance data dict or None
        """
        # TODO: Implement historical performance retrieval
        raise NotImplementedError("ModelSelector._get_historical_performance() not yet implemented")

    def _apply_overrides(
        self,
        task: Dict,
        recommendation: ModelRecommendation
    ) -> ModelRecommendation:
        """
        Apply configuration overrides to a recommendation.

        Args:
            task: The task dictionary
            recommendation: The initial recommendation

        Returns:
            Possibly modified recommendation
        """
        # Check for task type override
        task_type = task.get('type', 'general')
        model_overrides = self.config.get('model_overrides', {})

        if task_type in model_overrides:
            override_model = ModelTier(model_overrides[task_type])
            return ModelRecommendation(
                model=override_model,
                reasoning=f"Override: {task_type} tasks use {override_model.value}",
                estimated_cost=recommendation.estimated_cost  # Recalculate if needed
            )

        # Check for priority override
        priority = task.get('priority', 999)
        priority_overrides = self.config.get('priority_overrides', {})

        for threshold, override_model in sorted(priority_overrides.items()):
            if priority <= int(threshold):
                return ModelRecommendation(
                    model=ModelTier(override_model),
                    reasoning=f"Override: Priority {priority} tasks use {override_model}",
                    estimated_cost=recommendation.estimated_cost
                )

        return recommendation

    def _downgrade_for_budget(
        self,
        recommendation: ModelRecommendation
    ) -> ModelRecommendation:
        """
        Downgrade model recommendation if approaching budget limit.

        Args:
            recommendation: The initial recommendation

        Returns:
            Possibly downgraded recommendation
        """
        within_budget, remaining = self.check_budget()

        if not within_budget:
            return ModelRecommendation(
                model=ModelTier.HAIKU,
                reasoning="Budget exceeded - forcing HAIKU",
                estimated_cost=0.0
            )

        budget_limit = self.config.get('budget_limit_usd', float('inf'))
        if budget_limit == float('inf'):
            return recommendation

        spent = budget_limit - remaining
        usage_pct = spent / budget_limit if budget_limit > 0 else 0

        if usage_pct > 0.95:
            return ModelRecommendation(
                model=ModelTier.HAIKU,
                reasoning=f"Budget at {usage_pct:.0%} - using HAIKU",
                estimated_cost=recommendation.estimated_cost * 0.1
            )
        elif usage_pct > 0.80 and recommendation.model == ModelTier.OPUS:
            return ModelRecommendation(
                model=ModelTier.SONNET,
                reasoning=f"Budget at {usage_pct:.0%} - downgrading to SONNET",
                estimated_cost=recommendation.estimated_cost * 0.5
            )

        return recommendation
