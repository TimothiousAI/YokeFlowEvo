"""
Parallel Execution Module
==========================

This module provides infrastructure for parallel task execution using git worktrees
and dependency-based scheduling.

Main Components:
- DependencyResolver: Computes parallel execution batches from task dependencies
- WorktreeManager: Manages git worktrees for isolated parallel execution
- ParallelExecutor: Orchestrates parallel agent execution across worktrees

Usage:
    from core.parallel import ParallelExecutor, WorktreeManager, DependencyResolver

    executor = ParallelExecutor(project_path, project_id, max_concurrency=3)
    await executor.execute()
"""

from core.parallel.dependency_resolver import DependencyResolver
from core.parallel.worktree_manager import WorktreeManager
from core.parallel.parallel_executor import ParallelExecutor

__all__ = [
    'DependencyResolver',
    'WorktreeManager',
    'ParallelExecutor',
]
