"""
Self-Learning Module
====================

This module implements YokeFlow's self-learning system that accumulates
expertise from completed sessions and optimizes model selection for cost efficiency.

Main Components:
- ExpertiseManager: Accumulates and manages domain-specific knowledge
- ModelSelector: Selects optimal model based on task complexity and budget

Usage:
    from core.learning import ExpertiseManager, ModelSelector

    expertise = ExpertiseManager(project_id, db)
    await expertise.learn_from_session(session_id, task, logs)

    selector = ModelSelector(project_id, config, db)
    recommendation = selector.recommend_model(task)
"""

from core.learning.expertise_manager import ExpertiseManager, ExpertiseFile, DOMAINS, MAX_EXPERTISE_LINES
from core.learning.model_selector import ModelSelector

__all__ = [
    'ExpertiseManager',
    'ExpertiseFile',
    'ModelSelector',
    'DOMAINS',
    'MAX_EXPERTISE_LINES',
]
