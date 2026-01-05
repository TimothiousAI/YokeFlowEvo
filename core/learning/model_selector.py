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
import logging

logger = logging.getLogger(__name__)


# Model tier enumeration
class ModelTier:
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
    ModelTier.HAIKU: 0.3,   # < 0.3 = simple
    ModelTier.SONNET: 0.7,  # 0.3-0.7 = moderate
    ModelTier.OPUS: 1.0,    # > 0.7 = complex
}


@dataclass
class ModelRecommendation:
    """
    Model recommendation with reasoning.

    Attributes:
        model: Recommended model tier
        reasoning: Explanation for recommendation
        estimated_cost: Estimated cost in USD
    """
    model: str
    reasoning: str
    estimated_cost: float


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
            TaskComplexity with scores
        """
        # Stub - will be implemented in Epic 95
        logger.warning("ModelSelector.analyze_complexity() not yet implemented")
        return TaskComplexity(
            reasoning_depth=0.5,
            code_complexity=0.5,
            domain_specificity=0.5,
            context_requirements=0.5,
            overall_score=0.5
        )

    def recommend_model(self, task: Dict[str, Any]) -> ModelRecommendation:
        """
        Recommend optimal model for a task.

        Args:
            task: Task dictionary

        Returns:
            ModelRecommendation with model and reasoning
        """
        # Stub - will be implemented in Epic 95
        logger.warning("ModelSelector.recommend_model() not yet implemented")
        return ModelRecommendation(
            model=ModelTier.SONNET,
            reasoning="Default model (implementation pending)",
            estimated_cost=0.0
        )

    def check_budget(self) -> tuple[bool, float]:
        """
        Check if within budget limit.

        Returns:
            Tuple of (within_budget, remaining_usd)
        """
        # Stub - will be implemented in Epic 95
        logger.warning("ModelSelector.check_budget() not yet implemented")
        return (True, 0.0)

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
