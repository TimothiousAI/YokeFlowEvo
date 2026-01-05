"""
Test task agent execution loads expertise and selects model.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parallel.parallel_executor import ParallelExecutor, ExecutionResult
from core.learning import ModelSelector
from core.learning.model_selector import ModelRecommendation


class MockDatabase:
    """Mock database for testing."""

    def __init__(self):
        self.sessions = []
        self.session_updates = []

    async def create_session(self, project_id, session_number, session_type, model, max_iterations=None):
        """Create mock session."""
        session = {
            'id': uuid4(),
            'project_id': project_id,
            'session_number': session_number,
            'type': session_type,
            'model': model,
            'status': 'pending'
        }
        self.sessions.append(session)
        return session

    async def start_session(self, session_id):
        """Mark session as started."""
        for session in self.sessions:
            if session['id'] == session_id:
                session['status'] = 'running'

    async def end_session(self, session_id, status, error_message=None, interruption_reason=None, metrics=None):
        """End session."""
        for session in self.sessions:
            if session['id'] == session_id:
                session['status'] = status
                session['error_message'] = error_message
                session['metrics'] = metrics
        self.session_updates.append({
            'session_id': session_id,
            'status': status,
            'metrics': metrics
        })

    async def update_task_status(self, task_id, project_id, done):
        """Update task status."""
        pass


async def test_task_agent_execution():
    """Test that run_task_agent loads expertise and selects model."""

    # Create mock database
    mock_db = MockDatabase()
    project_id = uuid4()

    # Create executor
    executor = ParallelExecutor(
        project_path="/tmp/test-project",
        project_id=project_id,
        max_concurrency=1,
        db_connection=mock_db
    )

    # Create mock task with known domain
    task = {
        'id': 1,
        'epic_id': 1,
        'epic_name': 'Test Epic',
        'description': 'Create database migration for users table',
        'action': 'Add migration file with CREATE TABLE users statement',
        'priority': 1,
        'tests': []
    }

    # Track expertise manager calls
    expertise_loaded = []
    original_get_expertise = executor.expertise_manager.get_expertise

    async def mock_get_expertise(domain):
        expertise_loaded.append(domain)
        return {'patterns': ['test pattern'], 'techniques': ['test technique']}

    executor.expertise_manager.get_expertise = mock_get_expertise

    # Track model selector calls (if initialized)
    model_selected = []

    # Create a mock ModelSelector
    mock_selector = Mock(spec=ModelSelector)
    mock_selector.recommend_model = Mock(return_value=ModelRecommendation(
        model='haiku',
        reasoning='Simple task, using cost-effective model',
        estimated_cost=0.005
    ))
    executor.model_selector = mock_selector

    # Execute task
    result = await executor.run_task_agent(task, "/tmp/test-worktree")

    # Verify expertise loaded for task domain
    assert len(expertise_loaded) > 0, "Expertise should have been loaded"
    domain = expertise_loaded[0]
    assert domain in ['database', 'api', 'frontend', 'testing', 'security', 'deployment', 'general'], \
        f"Domain should be one of the known domains, got: {domain}"

    # Verify model selected based on task
    assert mock_selector.recommend_model.called, "Model selector should have been called"

    # Verify session was created
    assert len(mock_db.sessions) == 1, f"Expected 1 session, got {len(mock_db.sessions)}"
    session = mock_db.sessions[0]
    assert session['type'] == 'coding', "Session type should be 'coding'"
    assert session['model'] == 'haiku', "Model should be 'haiku' from selector"

    # Verify session was completed
    assert len(mock_db.session_updates) == 1, "Session should have been updated"
    update = mock_db.session_updates[0]
    assert update['status'] == 'completed', "Session should be completed"

    # Verify cost was recorded
    assert update['metrics'] is not None, "Metrics should be recorded"
    assert 'cost' in update['metrics'], "Cost should be in metrics"
    assert update['metrics']['cost'] > 0, "Cost should be > 0"

    # Verify result
    assert result.success, "Task execution should succeed"
    assert result.task_id == 1, "Result should have correct task_id"
    assert result.duration > 0, "Duration should be > 0"

    print(f"Test passed! Domain: {domain}, Model: haiku, Cost: ${update['metrics']['cost']}")


if __name__ == "__main__":
    asyncio.run(test_task_agent_execution())
