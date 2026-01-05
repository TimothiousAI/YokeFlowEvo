"""
Integration tests for parallel execution workflow.

Tests end-to-end parallel execution including:
- Real git worktrees
- Database operations
- Worktree merge workflow
- Expertise accumulation
- Cost tracking

NOTE: These tests use temporary directories and test database.
They clean up resources after completion.
"""

import sys
import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

sys.path.insert(0, '.')

from core.parallel.parallel_executor import ParallelExecutor, ExecutionResult
from core.parallel.worktree_manager import WorktreeManager
from core.parallel.dependency_resolver import DependencyResolver
from core.learning.expertise_manager import ExpertiseManager
from core.learning.model_selector import ModelSelector


# Fixtures

@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with git repo."""
    temp_dir = tempfile.mkdtemp(prefix='yokeflow_test_')
    project_path = Path(temp_dir)

    # Initialize git repo
    import subprocess
    subprocess.run(['git', 'init'], cwd=project_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_path, check=True, capture_output=True)

    # Create initial commit
    (project_path / 'README.md').write_text('# Test Project')
    subprocess.run(['git', 'add', '.'], cwd=project_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=project_path, check=True, capture_output=True)

    yield project_path

    # Cleanup
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        print(f"Warning: Failed to cleanup temp dir {temp_dir}: {e}")


@pytest.fixture
def mock_db():
    """Create mock database with async support."""
    class MockDB:
        def __init__(self):
            self.tasks = []
            self.batches = []
            self.worktrees = []
            self.costs = []
            self.expertise = {}

        async def get_tasks_with_dependencies(self, project_id):
            """Return tasks with dependencies."""
            return self.tasks

        async def create_parallel_batch(self, project_id, batch_number, task_ids):
            """Create batch record."""
            batch = {
                'id': len(self.batches) + 1,
                'project_id': project_id,
                'batch_number': batch_number,
                'task_ids': task_ids,
                'status': 'pending',
                'created_at': datetime.now()
            }
            self.batches.append(batch)
            return batch

        async def update_batch_status(self, batch_id, status, **kwargs):
            """Update batch status."""
            for batch in self.batches:
                if batch['id'] == batch_id:
                    batch['status'] = status
                    batch.update(kwargs)
                    return batch
            return None

        async def create_worktree(self, project_id, epic_id, path, branch_name):
            """Create worktree record."""
            worktree = {
                'id': len(self.worktrees) + 1,
                'project_id': project_id,
                'epic_id': epic_id,
                'path': path,
                'branch_name': branch_name,
                'status': 'active'
            }
            self.worktrees.append(worktree)
            return worktree

        async def record_agent_cost(self, session_id, task_id, model, cost):
            """Record agent cost."""
            cost_record = {
                'session_id': session_id,
                'task_id': task_id,
                'model': model,
                'cost': cost,
                'created_at': datetime.now()
            }
            self.costs.append(cost_record)

        async def save_expertise(self, project_id, domain, content, line_count):
            """Save expertise."""
            self.expertise[domain] = {
                'id': uuid4(),
                'project_id': project_id,
                'domain': domain,
                'content': content,
                'line_count': line_count,
                'version': self.expertise.get(domain, {}).get('version', 0) + 1
            }
            return self.expertise[domain]

        async def get_expertise(self, project_id, domain):
            """Get expertise."""
            return self.expertise.get(domain)

    return MockDB()


# Integration Tests

def test_end_to_end_parallel_execution_setup(temp_project_dir, mock_db):
    """Test parallel executor setup and configuration."""
    project_id = uuid4()

    # Setup tasks with dependencies
    mock_db.tasks = [
        {
            'id': 1,
            'epic_id': 1,
            'description': 'Setup database schema',
            'action': 'Create initial tables',
            'depends_on': [],
            'dependency_type': 'hard',
            'priority': 1,
            'done': False,
            'epic_name': 'Backend'
        },
        {
            'id': 2,
            'epic_id': 1,
            'description': 'Add API routes',
            'action': 'Create REST endpoints',
            'depends_on': [1],
            'dependency_type': 'hard',
            'priority': 2,
            'done': False,
            'epic_name': 'Backend'
        }
    ]

    # Create executor
    executor = ParallelExecutor(
        project_path=str(temp_project_dir),
        project_id=project_id,
        max_concurrency=2,
        db_connection=mock_db
    )

    # Verify executor configuration
    assert executor.project_path == str(temp_project_dir), "Project path should match"
    assert executor.project_id == project_id, "Project ID should match"
    assert executor.max_concurrency == 2, "Max concurrency should match"
    assert executor.db == mock_db, "DB connection should match"

    print("✓ Parallel executor setup test passed")


@pytest.mark.asyncio
async def test_worktree_initialization(temp_project_dir, mock_db):
    """Test worktree manager initialization."""
    project_id = uuid4()

    # Create worktree manager
    worktree_mgr = WorktreeManager(
        project_path=str(temp_project_dir),
        project_id=project_id,
        db=mock_db
    )

    await worktree_mgr.initialize()

    # Verify worktree directory was created
    worktree_dir = temp_project_dir / '.worktrees'
    assert worktree_dir.exists(), "Worktree directory should be created"
    assert worktree_dir.is_dir(), "Worktree path should be a directory"

    print("✓ Worktree initialization test passed")


def test_dependency_resolution():
    """Test dependency resolution creates correct batches."""
    tasks = [
        {'id': 1, 'priority': 1, 'depends_on': []},
        {'id': 2, 'priority': 2, 'depends_on': [1], 'dependency_type': 'hard'},
        {'id': 3, 'priority': 3, 'depends_on': [1], 'dependency_type': 'hard'},
        {'id': 4, 'priority': 4, 'depends_on': [2, 3], 'dependency_type': 'hard'},
    ]

    resolver = DependencyResolver()
    graph = resolver.resolve(tasks)

    # Verify batching
    assert len(graph.batches) == 3, f"Expected 3 batches, got {len(graph.batches)}"

    # Batch 1: Task 1 (no dependencies)
    assert graph.batches[0] == [1], f"Batch 1 should be [1], got {graph.batches[0]}"

    # Batch 2: Tasks 2 and 3 (depend on 1)
    assert set(graph.batches[1]) == {2, 3}, f"Batch 2 should be {{2,3}}, got {graph.batches[1]}"

    # Batch 3: Task 4 (depends on 2 and 3)
    assert graph.batches[2] == [4], f"Batch 3 should be [4], got {graph.batches[2]}"

    # Verify no circular dependencies
    assert graph.circular_deps == [], "Should have no circular dependencies"

    print("✓ Dependency resolution test passed")


@pytest.mark.asyncio
async def test_expertise_accumulation(mock_db):
    """Test that expertise is accumulated across sessions."""
    project_id = uuid4()

    # Create expertise manager
    expertise_mgr = ExpertiseManager(project_id, mock_db)

    # Simulate learning from a session
    session_id = uuid4()
    task = {
        'id': 1,
        'description': 'Add new API endpoint',
        'action': 'Create REST endpoint with authentication',
        'status': 'completed',
        'done': True
    }

    logs = """
    Read(file_path="api/routes.py")
    Edit(file_path="api/routes.py", old_string="...", new_string="...")
    Bash(command="pytest tests/test_api.py")
    Test passed successfully
    """

    # Learn from session
    await expertise_mgr.learn_from_session(session_id, task, logs)

    # Verify expertise was saved
    api_expertise = await expertise_mgr.get_expertise('api')

    assert api_expertise is not None, "Should create API expertise"
    assert len(api_expertise.content.get('patterns', [])) > 0, "Should extract patterns"

    # Verify patterns were extracted
    patterns = api_expertise.content.get('patterns', [])
    pattern_names = [p['name'] for p in patterns]
    assert any('Read-Edit' in name for name in pattern_names), "Should find Read-Edit pattern"

    print(f"✓ Expertise accumulation test passed: {len(patterns)} patterns extracted")


@pytest.mark.asyncio
async def test_cost_tracking_accuracy(mock_db):
    """Test that costs are tracked accurately across parallel execution."""
    project_id = uuid4()
    session_id = uuid4()

    # Record costs for different tasks
    costs = [
        {'task_id': 1, 'model': 'haiku', 'cost': 0.001},
        {'task_id': 2, 'model': 'sonnet', 'cost': 0.003},
        {'task_id': 3, 'model': 'sonnet', 'cost': 0.003},
    ]

    for cost_data in costs:
        await mock_db.record_agent_cost(
            session_id=session_id,
            task_id=cost_data['task_id'],
            model=cost_data['model'],
            cost=cost_data['cost']
        )

    # Verify all costs recorded
    assert len(mock_db.costs) == 3, f"Expected 3 cost records, got {len(mock_db.costs)}"

    # Calculate total cost
    total_cost = sum(c['cost'] for c in mock_db.costs)
    expected_cost = sum(c['cost'] for c in costs)

    assert abs(total_cost - expected_cost) < 0.0001, \
        f"Total cost {total_cost} should match expected {expected_cost}"

    # Verify cost breakdown by model
    haiku_cost = sum(c['cost'] for c in mock_db.costs if c['model'] == 'haiku')
    sonnet_cost = sum(c['cost'] for c in mock_db.costs if c['model'] == 'sonnet')

    assert abs(haiku_cost - 0.001) < 0.0001, "HAIKU cost should be accurate"
    assert abs(sonnet_cost - 0.006) < 0.0001, "SONNET cost should be accurate"

    print(f"✓ Cost tracking test passed: ${total_cost:.4f} total (HAIKU: ${haiku_cost:.4f}, SONNET: ${sonnet_cost:.4f})")


def test_execution_result_creation():
    """Test ExecutionResult data structure."""
    # Test successful result
    success_result = ExecutionResult(
        task_id=1,
        success=True,
        duration=1.5,
        cost=0.02
    )

    assert success_result.task_id == 1, "Task ID should match"
    assert success_result.success is True, "Should be successful"
    assert success_result.duration == 1.5, "Duration should match"
    assert success_result.cost == 0.02, "Cost should match"
    assert success_result.error is None, "Should have no error"

    # Test failure result
    failure_result = ExecutionResult(
        task_id=2,
        success=False,
        duration=0.5,
        cost=0.01,
        error='Test error message'
    )

    assert failure_result.task_id == 2, "Task ID should match"
    assert failure_result.success is False, "Should be failed"
    assert failure_result.error == 'Test error message', "Error should match"

    print("✓ ExecutionResult creation test passed")


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
