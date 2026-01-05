"""
Test ParallelExecutor initialization.
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.parallel_executor import ParallelExecutor
from core.parallel.worktree_manager import WorktreeManager
from core.parallel.dependency_resolver import DependencyResolver
from core.learning import ExpertiseManager


def test_parallel_executor_initialization():
    """Test that ParallelExecutor initializes with required components."""

    # Create executor
    executor = ParallelExecutor(
        project_path="/tmp/test-project",
        project_id="test-project-123",
        max_concurrency=3
    )

    # Verify components created
    assert isinstance(executor.worktree_manager, WorktreeManager), \
        "WorktreeManager instance not created"
    assert isinstance(executor.dependency_resolver, DependencyResolver), \
        "DependencyResolver instance not created"
    assert isinstance(executor.expertise_manager, ExpertiseManager), \
        "ExpertiseManager instance not created"

    # Verify semaphore set to max_concurrency
    assert isinstance(executor.semaphore, asyncio.Semaphore), \
        "Semaphore not initialized"
    assert executor.semaphore._value == 3, \
        f"Semaphore value should be 3, got {executor.semaphore._value}"

    # Verify cancel event initialized
    assert isinstance(executor.cancel_event, asyncio.Event), \
        "Cancel event not initialized"
    assert not executor.cancel_event.is_set(), \
        "Cancel event should not be set initially"

    # Verify running agents list initialized
    assert isinstance(executor.running_agents, list), \
        "Running agents list not initialized"
    assert len(executor.running_agents) == 0, \
        "Running agents list should be empty initially"

    print("All initialization tests passed!")


if __name__ == "__main__":
    test_parallel_executor_initialization()
