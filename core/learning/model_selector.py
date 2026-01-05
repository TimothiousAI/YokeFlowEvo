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
