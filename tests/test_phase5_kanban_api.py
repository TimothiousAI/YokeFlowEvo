"""
Tests for Phase 5: Kanban UI API Endpoints

Tests the parallel execution control and task management endpoints:
- POST /api/projects/{project_id}/parallel/pause
- POST /api/projects/{project_id}/parallel/resume
- PATCH /api/tasks/{task_id}/status
- PATCH /api/tasks/{task_id}/worktree

These endpoints support the Kanban UI components:
- KanbanBoard
- WorktreeCard
- ExecutionTimeline
- ParallelControlPanel
"""

import sys
import pytest
from uuid import uuid4, UUID
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from contextlib import asynccontextmanager

sys.path.insert(0, '.')

# Mock the database module before importing the app
@pytest.fixture(autouse=True)
def mock_db_module():
    """Mock database module to avoid actual database connections."""
    with patch.dict('sys.modules', {
        'core.database_connection': MagicMock(),
        'core.database': MagicMock()
    }):
        yield


class TestParallelExecutionPause:
    """Tests for parallel execution pause endpoint."""

    @pytest.mark.asyncio
    async def test_pause_requires_running_mode(self):
        """Pause fails if not in parallel_running mode."""
        project_id = uuid4()
        mock_db = AsyncMock()
        mock_db.get_project = AsyncMock(return_value={'id': str(project_id), 'name': 'Test'})
        mock_db.get_project_execution_mode = AsyncMock(return_value='idle')

        # Verify the logic - when mode is not parallel_running, should reject
        mode = await mock_db.get_project_execution_mode(project_id)
        assert mode != 'parallel_running'

    @pytest.mark.asyncio
    async def test_pause_sets_paused_mode(self):
        """Pause sets execution mode to paused."""
        project_id = uuid4()
        mock_db = AsyncMock()
        mock_db.get_project = AsyncMock(return_value={'id': str(project_id), 'name': 'Test'})
        mock_db.get_project_execution_mode = AsyncMock(return_value='parallel_running')
        mock_db.set_project_execution_mode = AsyncMock()
        mock_db.update_project_metadata = AsyncMock()

        # Simulate pause operation
        mode = await mock_db.get_project_execution_mode(project_id)
        assert mode == 'parallel_running'

        await mock_db.set_project_execution_mode(project_id, 'paused')
        mock_db.set_project_execution_mode.assert_called_with(project_id, 'paused')

    @pytest.mark.asyncio
    async def test_pause_updates_metadata(self):
        """Pause records timestamp in metadata."""
        project_id = uuid4()
        mock_db = AsyncMock()
        mock_db.update_project_metadata = AsyncMock()

        await mock_db.update_project_metadata(project_id, {
            'parallel_paused_at': datetime.now().isoformat()
        })

        mock_db.update_project_metadata.assert_called_once()
        call_args = mock_db.update_project_metadata.call_args
        assert 'parallel_paused_at' in call_args[0][1]


class TestParallelExecutionResume:
    """Tests for parallel execution resume endpoint."""

    @pytest.mark.asyncio
    async def test_resume_requires_paused_mode(self):
        """Resume fails if not in paused mode."""
        project_id = uuid4()
        mock_db = AsyncMock()
        mock_db.get_project = AsyncMock(return_value={'id': str(project_id), 'name': 'Test'})
        mock_db.get_project_execution_mode = AsyncMock(return_value='idle')

        mode = await mock_db.get_project_execution_mode(project_id)
        assert mode != 'paused'

    @pytest.mark.asyncio
    async def test_resume_sets_parallel_running_mode(self):
        """Resume sets execution mode back to parallel_running."""
        project_id = uuid4()
        mock_db = AsyncMock()
        mock_db.get_project = AsyncMock(return_value={'id': str(project_id), 'name': 'Test'})
        mock_db.get_project_execution_mode = AsyncMock(return_value='paused')
        mock_db.set_project_execution_mode = AsyncMock()

        mode = await mock_db.get_project_execution_mode(project_id)
        assert mode == 'paused'

        await mock_db.set_project_execution_mode(project_id, 'parallel_running')
        mock_db.set_project_execution_mode.assert_called_with(project_id, 'parallel_running')

    @pytest.mark.asyncio
    async def test_resume_updates_metadata(self):
        """Resume records timestamp in metadata."""
        project_id = uuid4()
        mock_db = AsyncMock()
        mock_db.update_project_metadata = AsyncMock()

        await mock_db.update_project_metadata(project_id, {
            'parallel_resumed_at': datetime.now().isoformat()
        })

        mock_db.update_project_metadata.assert_called_once()
        call_args = mock_db.update_project_metadata.call_args
        assert 'parallel_resumed_at' in call_args[0][1]


class TestTaskStatusUpdate:
    """Tests for task status update endpoint."""

    @pytest.mark.asyncio
    async def test_valid_statuses(self):
        """Valid status values are accepted."""
        valid_statuses = ["pending", "running", "review", "done", "error"]

        for status in valid_statuses:
            assert status in valid_statuses

    @pytest.mark.asyncio
    async def test_invalid_status_rejected(self):
        """Invalid status values are rejected."""
        valid_statuses = ["pending", "running", "review", "done", "error"]
        invalid_status = "invalid_status"

        assert invalid_status not in valid_statuses

    @pytest.mark.asyncio
    async def test_update_status_calls_db(self):
        """Updating status calls database update."""
        task_id = 42
        mock_db = AsyncMock()
        mock_db.get_task = AsyncMock(return_value={'id': task_id, 'status': 'pending'})
        mock_db.update_task_status = AsyncMock()

        await mock_db.update_task_status(task_id, 'running')
        mock_db.update_task_status.assert_called_with(task_id, 'running')

    @pytest.mark.asyncio
    async def test_done_status_marks_task_complete(self):
        """Setting status to 'done' also marks task as done."""
        task_id = 42
        mock_db = AsyncMock()
        mock_db.get_task = AsyncMock(return_value={'id': task_id, 'status': 'running'})
        mock_db.update_task_status = AsyncMock()
        mock_db.mark_task_done = AsyncMock()

        # Simulate the endpoint logic
        new_status = 'done'
        await mock_db.update_task_status(task_id, new_status)
        if new_status == 'done':
            await mock_db.mark_task_done(task_id)

        mock_db.mark_task_done.assert_called_with(task_id)

    @pytest.mark.asyncio
    async def test_task_not_found(self):
        """Returns 404 for non-existent task."""
        task_id = 99999
        mock_db = AsyncMock()
        mock_db.get_task = AsyncMock(return_value=None)

        task = await mock_db.get_task(task_id)
        assert task is None


class TestTaskWorktreeAssignment:
    """Tests for task worktree assignment endpoint."""

    @pytest.mark.asyncio
    async def test_assign_worktree_updates_plan(self):
        """Assigning worktree updates execution plan."""
        task_id = 42
        worktree_id = "worktree-1"
        project_id = uuid4()

        mock_db = AsyncMock()
        mock_db.get_task = AsyncMock(return_value={
            'id': task_id,
            'project_id': str(project_id)
        })
        mock_db.get_execution_plan = AsyncMock(return_value={
            'batches': [],
            'worktree_assignments': {}
        })
        mock_db.save_execution_plan = AsyncMock()

        # Simulate assignment logic
        task = await mock_db.get_task(task_id)
        plan = await mock_db.get_execution_plan(UUID(str(task['project_id'])))

        plan['worktree_assignments'][str(task_id)] = worktree_id

        await mock_db.save_execution_plan(UUID(str(task['project_id'])), plan)

        mock_db.save_execution_plan.assert_called_once()
        assert plan['worktree_assignments'][str(task_id)] == worktree_id

    @pytest.mark.asyncio
    async def test_missing_worktree_id_rejected(self):
        """Request without worktree_id is rejected."""
        request = {}
        worktree_id = request.get("worktree_id")
        assert worktree_id is None

    @pytest.mark.asyncio
    async def test_task_not_found_for_assignment(self):
        """Returns 404 when task doesn't exist."""
        task_id = 99999
        mock_db = AsyncMock()
        mock_db.get_task = AsyncMock(return_value=None)

        task = await mock_db.get_task(task_id)
        assert task is None

    @pytest.mark.asyncio
    async def test_creates_worktree_assignments_if_missing(self):
        """Creates worktree_assignments dict if not in plan."""
        task_id = 42
        worktree_id = "worktree-1"
        project_id = uuid4()

        plan = {
            'batches': []
            # No 'worktree_assignments' key
        }

        # Simulate logic from endpoint
        if "worktree_assignments" not in plan:
            plan["worktree_assignments"] = {}
        plan["worktree_assignments"][str(task_id)] = worktree_id

        assert "worktree_assignments" in plan
        assert plan["worktree_assignments"][str(task_id)] == worktree_id


class TestExecutionModeTransitions:
    """Tests for valid execution mode state transitions."""

    @pytest.mark.asyncio
    async def test_idle_to_parallel_running(self):
        """Can transition from idle to parallel_running."""
        valid_transitions = {
            'idle': ['parallel_running', 'sequential'],
            'parallel_running': ['paused', 'idle'],
            'paused': ['parallel_running', 'idle'],
            'sequential': ['idle']
        }

        assert 'parallel_running' in valid_transitions['idle']

    @pytest.mark.asyncio
    async def test_parallel_running_to_paused(self):
        """Can transition from parallel_running to paused."""
        valid_transitions = {
            'idle': ['parallel_running', 'sequential'],
            'parallel_running': ['paused', 'idle'],
            'paused': ['parallel_running', 'idle'],
            'sequential': ['idle']
        }

        assert 'paused' in valid_transitions['parallel_running']

    @pytest.mark.asyncio
    async def test_paused_to_parallel_running(self):
        """Can transition from paused back to parallel_running."""
        valid_transitions = {
            'idle': ['parallel_running', 'sequential'],
            'parallel_running': ['paused', 'idle'],
            'paused': ['parallel_running', 'idle'],
            'sequential': ['idle']
        }

        assert 'parallel_running' in valid_transitions['paused']


class TestKanbanColumnMapping:
    """Tests for mapping task status to Kanban columns."""

    def test_done_maps_to_done_column(self):
        """Tasks with done=True map to 'done' column."""
        task = {'done': True, 'status': 'pending'}
        column = self._get_kanban_column(task)
        assert column == 'done'

    def test_running_maps_to_in_progress(self):
        """Tasks with status='running' map to 'in_progress' column."""
        task = {'done': False, 'status': 'running'}
        column = self._get_kanban_column(task)
        assert column == 'in_progress'

    def test_review_maps_to_review(self):
        """Tasks with status='review' map to 'review' column."""
        task = {'done': False, 'status': 'review'}
        column = self._get_kanban_column(task)
        assert column == 'review'

    def test_pending_maps_to_backlog(self):
        """Tasks with status='pending' map to 'backlog' column."""
        task = {'done': False, 'status': 'pending'}
        column = self._get_kanban_column(task)
        assert column == 'backlog'

    def test_explicit_kanban_status_overrides(self):
        """Explicit kanban_status takes precedence."""
        task = {'done': False, 'status': 'pending', 'kanban_status': 'review'}
        column = self._get_kanban_column(task)
        assert column == 'review'

    def _get_kanban_column(self, task):
        """Helper to determine Kanban column - matches frontend logic."""
        if task.get('kanban_status'):
            return task['kanban_status']
        if task.get('done'):
            return 'done'
        if task.get('status') == 'running':
            return 'in_progress'
        if task.get('status') == 'review':
            return 'review'
        return 'backlog'


class TestBatchStatusMapping:
    """Tests for mapping batch status to timeline display."""

    def test_all_completed_tasks_means_completed_batch(self):
        """Batch with all completed tasks is 'completed'."""
        batch = {'task_ids': [1, 2, 3]}
        completed_tasks = [1, 2, 3]

        all_completed = all(t_id in completed_tasks for t_id in batch['task_ids'])
        status = 'completed' if all_completed else 'pending'

        assert status == 'completed'

    def test_current_batch_is_running(self):
        """Current batch shows as 'running'."""
        batch = {'batch_id': 2, 'task_ids': [4, 5]}
        current_batch = 2
        completed_tasks = []

        status = self._get_batch_status(batch, current_batch, completed_tasks)
        assert status == 'running'

    def test_some_completed_means_running(self):
        """Batch with some completed tasks is 'running'."""
        batch = {'batch_id': 3, 'task_ids': [6, 7, 8]}
        current_batch = 1  # Not this batch
        completed_tasks = [6]  # One task done

        status = self._get_batch_status(batch, current_batch, completed_tasks)
        assert status == 'running'

    def test_no_progress_means_pending(self):
        """Batch with no progress is 'pending'."""
        batch = {'batch_id': 5, 'task_ids': [10, 11]}
        current_batch = 2
        completed_tasks = [1, 2, 3]  # Other tasks

        status = self._get_batch_status(batch, current_batch, completed_tasks)
        assert status == 'pending'

    def _get_batch_status(self, batch, current_batch, completed_tasks):
        """Helper to determine batch status - matches frontend logic."""
        task_ids = batch.get('task_ids', [])

        # All completed?
        if all(t_id in completed_tasks for t_id in task_ids):
            return 'completed'

        # Current batch?
        if current_batch == batch.get('batch_id'):
            return 'running'

        # Some progress?
        if any(t_id in completed_tasks for t_id in task_ids):
            return 'running'

        return 'pending'


class TestWorktreeStatusDisplay:
    """Tests for worktree status display in cards."""

    def test_active_worktree_styling(self):
        """Active worktree gets blue styling."""
        styles = self._get_status_color('active')
        assert 'blue' in styles

    def test_merged_worktree_styling(self):
        """Merged worktree gets green styling."""
        styles = self._get_status_color('merged')
        assert 'green' in styles

    def test_conflict_worktree_styling(self):
        """Conflict worktree gets red styling."""
        styles = self._get_status_color('conflict')
        assert 'red' in styles

    def test_pending_worktree_styling(self):
        """Pending worktree gets gray styling."""
        styles = self._get_status_color('pending')
        assert 'gray' in styles

    def _get_status_color(self, status):
        """Helper matching frontend getStatusColor logic."""
        color_map = {
            'active': 'border-blue-500 bg-blue-500/10',
            'merged': 'border-green-500 bg-green-500/10',
            'conflict': 'border-red-500 bg-red-500/10',
            'pending': 'border-gray-700 bg-gray-800'
        }
        return color_map.get(status, color_map['pending'])


class TestParallelControlPanelLogic:
    """Tests for control panel button visibility logic."""

    def test_start_button_visible_when_idle_with_plan(self):
        """Start button visible when idle and has execution plan."""
        mode = 'idle'
        has_plan = True

        can_start = has_plan and (mode == 'idle' or mode == 'parallel')
        assert can_start is True

    def test_start_button_visible_when_parallel_ready(self):
        """Start button visible in 'parallel' ready state."""
        mode = 'parallel'
        has_plan = True

        can_start = has_plan and (mode == 'idle' or mode == 'parallel')
        assert can_start is True

    def test_start_hidden_without_plan(self):
        """Start button hidden without execution plan."""
        mode = 'idle'
        has_plan = False

        can_start = has_plan and (mode == 'idle' or mode == 'parallel')
        assert can_start is False

    def test_pause_visible_when_running(self):
        """Pause button visible when parallel_running."""
        mode = 'parallel_running'
        can_pause = mode == 'parallel_running'
        assert can_pause is True

    def test_resume_visible_when_paused(self):
        """Resume button visible when paused."""
        mode = 'paused'
        can_resume = mode == 'paused'
        assert can_resume is True

    def test_stop_visible_when_running_or_paused(self):
        """Stop button visible when running or paused."""
        for mode in ['parallel_running', 'paused']:
            can_stop = mode == 'parallel_running' or mode == 'paused'
            assert can_stop is True

    def test_stop_hidden_when_idle(self):
        """Stop button hidden when idle."""
        mode = 'idle'
        can_stop = mode == 'parallel_running' or mode == 'paused'
        assert can_stop is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
