"""
PostgreSQL Database Abstraction Layer
=====================================

Database interface for YokeFlow using PostgreSQL.
Uses asyncpg for high-performance async database operations.

This module replaces the SQLite-based database.py with a PostgreSQL
implementation optimized for the new unified database structure.
"""

import asyncpg
import json
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
from datetime import datetime
from contextlib import asynccontextmanager
from uuid import UUID, uuid4
import hashlib
import logging

from core.config import Config

logger = logging.getLogger(__name__)


class TaskDatabase:
    """
    PostgreSQL database interface for task management.

    Handles all interactions with the PostgreSQL database using asyncpg
    for high-performance async operations.
    """

    def __init__(self, connection_url: str):
        """
        Initialize database connection parameters.

        Args:
            connection_url: PostgreSQL connection string
                Format: postgresql://user:password@host:port/database
        """
        self.connection_url = connection_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self, min_size: int = 10, max_size: int = 20):
        """
        Create connection pool to PostgreSQL.

        Args:
            min_size: Minimum number of connections in pool
            max_size: Maximum number of connections in pool
        """
        self.pool = await asyncpg.create_pool(
            self.connection_url,
            min_size=min_size,
            max_size=max_size,
            command_timeout=60
        )
        logger.info(f"Connected to PostgreSQL with pool size {min_size}-{max_size}")

    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Disconnected from PostgreSQL")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self):
        """Create a transaction context."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    # =========================================================================
    # Project Operations
    # =========================================================================

    async def create_project(
        self,
        name: str,
        spec_file_path: str,
        spec_content: Optional[str] = None,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            name: Unique project name
            spec_file_path: Path to specification file
            spec_content: Content of spec file (for hash calculation)
            user_id: Optional user ID for multi-user support

        Returns:
            Created project record as dictionary
        """
        spec_hash = None
        if spec_content:
            spec_hash = hashlib.sha256(spec_content.encode()).hexdigest()

        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO projects (name, spec_file_path, spec_hash, user_id)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                name, spec_file_path, spec_hash, user_id
            )
            return dict(row)

    async def get_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get project by name.

        Args:
            name: Project name

        Returns:
            Project record or None if not found
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE name = $1",
                name
            )
            return dict(row) if row else None

    async def get_project(self, project_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get project by ID.

        Args:
            project_id: Project UUID

        Returns:
            Project record or None if not found
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE id = $1",
                project_id
            )
            if not row:
                return None

            project = dict(row)

            # Extract local_path from metadata JSONB if present
            # Handle both dict and JSON string formats
            metadata = project.get('metadata')
            if metadata:
                if isinstance(metadata, str):
                    import json
                    metadata = json.loads(metadata)
                    project['metadata'] = metadata
                if isinstance(metadata, dict) and 'local_path' in metadata:
                    project['local_path'] = metadata['local_path']

            return project

    async def update_project(
        self,
        project_id: UUID,
        **kwargs
    ) -> None:
        """
        Update project fields.

        Args:
            project_id: Project UUID
            **kwargs: Fields to update (local_path, github_repo_url, etc.)
        """
        # Store local_path in metadata JSONB field
        if 'local_path' in kwargs:
            async with self.acquire() as conn:
                # Get current metadata
                row = await conn.fetchrow(
                    "SELECT metadata FROM projects WHERE id = $1",
                    project_id
                )

                # Parse metadata - asyncpg may return it as string or dict
                if row and row['metadata']:
                    if isinstance(row['metadata'], str):
                        metadata = json.loads(row['metadata'])
                    else:
                        metadata = dict(row['metadata'])
                else:
                    metadata = {}

                metadata['local_path'] = kwargs['local_path']

                # Update metadata
                await conn.execute(
                    "UPDATE projects SET metadata = $1 WHERE id = $2",
                    json.dumps(metadata), project_id
                )
            return

        # For other fields, build dynamic UPDATE query
        if not kwargs:
            return

        set_clauses = []
        values = []
        param_num = 1

        for key, value in kwargs.items():
            set_clauses.append(f"{key} = ${param_num}")
            values.append(value)
            param_num += 1

        values.append(project_id)

        query = f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ${param_num}"

        async with self.acquire() as conn:
            await conn.execute(query, *values)

    async def rename_project(
        self,
        project_id: UUID,
        new_name: str
    ) -> None:
        """
        Rename a project (database name only).

        NOTE: This only updates the project name in the database.
        The directory name in the generations/ folder is NOT changed.
        This is intentional to avoid breaking running sessions and
        maintain filesystem stability.

        Args:
            project_id: Project UUID
            new_name: New project name

        Raises:
            ValueError: If project doesn't exist or name already in use
        """
        # Check if project exists
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        # Check if new name is already in use by another project
        async with self.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM projects WHERE name = $1 AND id != $2",
                new_name, project_id
            )
            if existing:
                raise ValueError(f"Project name '{new_name}' is already in use")

            # Update the name
            await conn.execute(
                "UPDATE projects SET name = $1, updated_at = NOW() WHERE id = $2",
                new_name, project_id
            )

    async def update_project_env_configured(
        self,
        project_id: UUID,
        configured: bool = True
    ) -> None:
        """
        Update project environment configuration status.

        Args:
            project_id: Project UUID
            configured: Whether environment is configured
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE projects
                SET env_configured = $1,
                    env_configured_at = CASE WHEN $1 THEN NOW() ELSE NULL END
                WHERE id = $2
                """,
                configured, project_id
            )

    async def mark_project_complete(self, project_id: UUID) -> None:
        """
        Mark a project as complete.

        Sets the completed_at timestamp to NOW() if not already set.

        Args:
            project_id: Project UUID
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE projects
                SET completed_at = COALESCE(completed_at, NOW())
                WHERE id = $1
                """,
                project_id
            )

    async def delete_project(self, project_id: UUID) -> None:
        """
        Delete a project and all associated data.

        This will cascade to delete:
        - All epics
        - All tasks
        - All tests
        - All sessions
        - All reviews
        - All github commits

        Args:
            project_id: Project UUID
        """
        async with self.acquire() as conn:
            await conn.execute(
                "DELETE FROM projects WHERE id = $1",
                project_id
            )

    async def get_project_settings(self, project_id: UUID) -> Dict[str, Any]:
        """
        Get project settings from metadata JSONB field.

        Returns default settings if none exist.

        Args:
            project_id: Project UUID

        Returns:
            Dictionary of settings with defaults applied
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            if not row or not row['metadata']:
                # Return default settings from Config
                config = Config.load_default()
                return {
                    'sandbox_type': 'docker',
                    'coding_model': config.models.coding,
                    'initializer_model': config.models.initializer,
                    'max_iterations': None,  # None = unlimited (auto-continue)
                }

            metadata = row['metadata']
            # asyncpg returns JSONB as string, parse if needed
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)

            settings = metadata.get('settings', {})

            # Apply defaults for missing keys from Config
            config = Config.load_default()
            defaults = {
                'sandbox_type': 'docker',
                'coding_model': config.models.coding,
                'initializer_model': config.models.initializer,
                'max_iterations': None,  # None = unlimited (auto-continue)
            }

            return {**defaults, **settings}

    async def update_project_settings(
        self,
        project_id: UUID,
        settings: Dict[str, Any]
    ) -> None:
        """
        Update project settings in metadata JSONB field.

        Args:
            project_id: Project UUID
            settings: Dictionary of settings to update
        """
        async with self.acquire() as conn:
            # Get current metadata
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            metadata = row['metadata'] if row and row['metadata'] else {}
            # asyncpg returns JSONB as string, parse if needed
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)

            current_settings = metadata.get('settings', {})

            # Merge with new settings
            updated_settings = {**current_settings, **settings}
            metadata['settings'] = updated_settings

            # Update in database
            await conn.execute(
                "UPDATE projects SET metadata = $1 WHERE id = $2",
                json.dumps(metadata),
                project_id
            )

    async def store_test_coverage(
        self,
        project_id: UUID,
        coverage_data: Dict[str, Any]
    ) -> None:
        """
        Store test coverage analysis results in project metadata.

        Args:
            project_id: Project UUID
            coverage_data: Coverage analysis results from test_coverage.analyze_test_coverage()
        """
        async with self.acquire() as conn:
            # Get current metadata
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            metadata = row['metadata'] if row and row['metadata'] else {}
            # asyncpg returns JSONB as string, parse if needed
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            # Store coverage data with timestamp
            from datetime import datetime
            metadata['test_coverage'] = {
                'analyzed_at': datetime.now().isoformat(),
                'data': coverage_data
            }

            # Update metadata
            await conn.execute(
                "UPDATE projects SET metadata = $1 WHERE id = $2",
                json.dumps(metadata),
                project_id
            )

    async def get_test_coverage(
        self,
        project_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get test coverage analysis results from project metadata.

        Args:
            project_id: Project UUID

        Returns:
            Coverage data with 'analyzed_at' timestamp and 'data', or None if not available
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            if not row or not row['metadata']:
                return None

            metadata = row['metadata']
            # asyncpg returns JSONB as string, parse if needed
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            return metadata.get('test_coverage')

    async def list_projects(
        self,
        user_id: Optional[UUID] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all projects with optional filtering.

        Args:
            user_id: Filter by user ID
            status: Filter by project status

        Returns:
            List of project records
        """
        query = "SELECT * FROM projects WHERE 1=1"
        params = []

        if user_id:
            params.append(user_id)
            query += f" AND user_id = ${len(params)}"

        if status:
            params.append(status)
            query += f" AND status = ${len(params)}"

        query += " ORDER BY created_at DESC"

        async with self.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    # =========================================================================
    # Session Operations
    # =========================================================================

    async def create_session(
        self,
        project_id: UUID,
        session_number: int,
        session_type: str,
        model: str,
        max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new session.

        Args:
            project_id: Project UUID
            session_number: Sequential session number
            session_type: 'initializer', 'coding', or 'review'
            model: Model name
            max_iterations: Optional iteration limit

        Returns:
            Created session record
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO sessions
                (project_id, session_number, type, model, max_iterations, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                RETURNING *
                """,
                project_id, session_number, session_type, model, max_iterations
            )
            return dict(row)

    async def start_session(self, session_id: UUID) -> None:
        """
        Mark session as started and initialize heartbeat.

        Args:
            session_id: Session UUID
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET status = 'running', started_at = NOW(), last_heartbeat = NOW()
                WHERE id = $1
                """,
                session_id
            )

    async def end_session(
        self,
        session_id: UUID,
        status: str,
        error_message: Optional[str] = None,
        interruption_reason: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark session as ended with outcome.

        Args:
            session_id: Session UUID
            status: 'completed', 'error', or 'interrupted'
            error_message: Error message if applicable
            interruption_reason: Reason for interruption
            metrics: Session metrics dictionary
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET status = $1,
                    ended_at = NOW(),
                    error_message = $2,
                    interruption_reason = $3,
                    metrics = COALESCE($4::jsonb, metrics)
                WHERE id = $5
                """,
                status, error_message, interruption_reason,
                json.dumps(metrics) if metrics else None,
                session_id
            )

    async def update_session_metrics(
        self,
        session_id: UUID,
        metrics: Dict[str, Any]
    ) -> None:
        """
        Update session metrics (merges with existing).

        Args:
            session_id: Session UUID
            metrics: Metrics to update
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET metrics = metrics || $1::jsonb
                WHERE id = $2
                """,
                json.dumps(metrics), session_id
            )

    async def get_active_session(
        self,
        project_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get currently active session for a project.

        Args:
            project_id: Project UUID

        Returns:
            Active session or None
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM sessions
                WHERE project_id = $1 AND status = 'running'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                project_id
            )
            return dict(row) if row else None

    async def get_next_session_number(self, project_id: UUID) -> int:
        """
        Get next session number for a project.

        Args:
            project_id: Project UUID

        Returns:
            Next session number (0-based: 0 for initialization, 1+ for coding)
        """
        async with self.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT COALESCE(MAX(session_number), -1) + 1
                FROM sessions
                WHERE project_id = $1
                """,
                project_id
            )
            return result

    async def get_session_history(
        self,
        project_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get session history for a project.

        Args:
            project_id: Project UUID
            limit: Maximum number of sessions to return

        Returns:
            List of session records
        """
        import json
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM sessions
                WHERE project_id = $1
                ORDER BY session_number DESC
                LIMIT $2
                """,
                project_id, limit
            )
            # Convert rows to dicts and parse JSONB fields
            result = []
            for row in rows:
                session_dict = dict(row)
                # Parse metrics JSONB field (asyncpg returns it as a string)
                if 'metrics' in session_dict and isinstance(session_dict['metrics'], str):
                    try:
                        session_dict['metrics'] = json.loads(session_dict['metrics'])
                    except (json.JSONDecodeError, TypeError):
                        session_dict['metrics'] = {}
                result.append(session_dict)
            return result

    async def update_session_heartbeat(self, session_id: UUID) -> None:
        """
        Update the heartbeat timestamp for an active session.

        This should be called periodically (e.g., every 60 seconds) during
        session execution to indicate the session is still active.

        Args:
            session_id: Session UUID
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET last_heartbeat = NOW()
                WHERE id = $1 AND status = 'running'
                """,
                session_id
            )

    async def cleanup_stale_sessions(self) -> int:
        """
        Clean up stale sessions (sessions marked as 'running' but inactive).

        A session is considered stale if:
        - Status is 'running'
        - No heartbeat received within threshold (uses last_heartbeat or started_at)
        - ended_at is NULL (session never finished gracefully)

        Heartbeat thresholds (no heartbeat for this long = stale):
        - Initializer: 35 minutes (heartbeat every 60s + 5min grace period)
        - Coding: 15 minutes (heartbeat every 60s + 5min grace period)
        - Review: 10 minutes (heartbeat every 60s + 5min grace period)

        Grace period accounts for:
        - Network delays
        - Temporary system slowdowns
        - Heartbeat interval variations

        This handles cases where sessions were interrupted ungracefully:
        - System sleep/hibernation
        - Process killed without cleanup
        - Orchestrator crash

        Returns:
            Number of sessions marked as interrupted
        """
        async with self.acquire() as conn:
            # Update stale sessions to 'interrupted' status
            # Use last_heartbeat if available, otherwise fall back to started_at
            result = await conn.execute(
                """
                UPDATE sessions
                SET status = 'interrupted',
                    ended_at = COALESCE(ended_at, NOW()),
                    interruption_reason = 'Marked as stale (ungraceful shutdown detected)'
                WHERE status = 'running'
                  AND ended_at IS NULL
                  AND (
                    -- Use last_heartbeat if available, otherwise started_at (for backwards compatibility)
                    (type = 'initializer' AND COALESCE(last_heartbeat, started_at) < NOW() - INTERVAL '35 minutes')
                    OR (type = 'coding' AND COALESCE(last_heartbeat, started_at) < NOW() - INTERVAL '15 minutes')
                    OR (type = 'review' AND COALESCE(last_heartbeat, started_at) < NOW() - INTERVAL '10 minutes')
                    OR (type IS NULL AND COALESCE(last_heartbeat, started_at) < NOW() - INTERVAL '15 minutes')  -- Default
                  )
                """
            )

            # Extract number of updated rows from result
            # asyncpg returns "UPDATE N" where N is the count
            count = int(result.split()[-1]) if result else 0

            if count > 0:
                logger.info(f"Cleaned up {count} stale session(s)")

            return count

    # =========================================================================
    # Execution Plan Operations
    # =========================================================================

    async def save_execution_plan(
        self,
        project_id: UUID,
        plan: Dict[str, Any]
    ) -> None:
        """
        Save execution plan to project metadata.

        Args:
            project_id: Project UUID
            plan: Execution plan dictionary
        """
        async with self.acquire() as conn:
            # Get current metadata
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            if row and row['metadata']:
                if isinstance(row['metadata'], str):
                    metadata = json.loads(row['metadata'])
                else:
                    metadata = dict(row['metadata'])
            else:
                metadata = {}

            # Store execution plan
            metadata['execution_plan'] = plan

            await conn.execute(
                "UPDATE projects SET metadata = $1::jsonb, updated_at = NOW() WHERE id = $2",
                json.dumps(metadata), project_id
            )
            logger.info(f"Saved execution plan for project {project_id}")

    async def get_execution_plan(
        self,
        project_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get execution plan from project metadata.

        Args:
            project_id: Project UUID

        Returns:
            Execution plan dictionary or None
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            if not row or not row['metadata']:
                return None

            metadata = row['metadata']
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            return metadata.get('execution_plan')

    async def update_task_predicted_files(
        self,
        task_id: int,
        files: List[str]
    ) -> None:
        """
        Update predicted files for a task in its metadata.

        Args:
            task_id: Task ID
            files: List of predicted file paths
        """
        async with self.acquire() as conn:
            # Get current metadata
            row = await conn.fetchrow(
                "SELECT metadata FROM tasks WHERE id = $1",
                task_id
            )

            if row and row['metadata']:
                if isinstance(row['metadata'], str):
                    metadata = json.loads(row['metadata'])
                else:
                    metadata = dict(row['metadata'])
            else:
                metadata = {}

            metadata['predicted_files'] = files

            await conn.execute(
                "UPDATE tasks SET metadata = $1::jsonb WHERE id = $2",
                json.dumps(metadata), task_id
            )

    async def get_tasks_for_planning(
        self,
        project_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all tasks with dependencies for execution planning.

        Args:
            project_id: Project UUID

        Returns:
            List of task dictionaries with epic and dependency info
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    t.id,
                    t.epic_id,
                    t.description,
                    t.action,
                    t.priority,
                    t.done,
                    t.metadata,
                    e.name as epic_name,
                    e.priority as epic_priority
                FROM tasks t
                JOIN epics e ON t.epic_id = e.id
                WHERE t.project_id = $1
                  AND t.done = false
                ORDER BY e.priority, t.priority, t.id
                """,
                project_id
            )

            tasks = []
            for row in rows:
                task = dict(row)
                # Parse metadata for dependencies
                metadata = task.get('metadata', {})
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                task['depends_on'] = metadata.get('depends_on', [])
                task['dependency_type'] = metadata.get('dependency_type', 'hard')
                tasks.append(task)

            return tasks

    async def update_batch_status(
        self,
        batch_id: int,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ) -> None:
        """
        Update batch execution status in execution plan.

        Note: Batches are stored in project metadata, not a separate table.
        This updates the batch status within the execution plan.

        Args:
            batch_id: Batch index in execution plan
            status: New status (pending, running, completed, failed)
            started_at: When batch started
            completed_at: When batch completed
        """
        # Batch status is tracked in project metadata for now
        # since batches are ephemeral and part of execution plan
        logger.debug(f"Batch {batch_id} status updated to {status}")

    async def get_batch_worktrees(self, batch_id: int) -> List[Dict[str, Any]]:
        """
        Get all worktrees associated with a batch.

        Note: This queries the worktrees table if it exists,
        otherwise returns empty list.

        Args:
            batch_id: Batch ID

        Returns:
            List of worktree info dicts
        """
        # Worktrees are managed by WorktreeManager
        # Return empty for now - batch_executor handles this via worktree_manager
        return []

    async def update_project_metadata(
        self,
        project_id: UUID,
        metadata_updates: Dict[str, Any]
    ) -> None:
        """
        Update specific fields in project metadata (merge, not replace).

        Args:
            project_id: Project UUID
            metadata_updates: Dictionary of fields to update/add
        """
        async with self.acquire() as conn:
            # Get current metadata
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            if row and row['metadata']:
                if isinstance(row['metadata'], str):
                    metadata = json.loads(row['metadata'])
                else:
                    metadata = dict(row['metadata'])
            else:
                metadata = {}

            # Merge updates
            metadata.update(metadata_updates)

            await conn.execute(
                "UPDATE projects SET metadata = $1::jsonb, updated_at = NOW() WHERE id = $2",
                json.dumps(metadata), project_id
            )
            logger.debug(f"Updated project {project_id} metadata: {list(metadata_updates.keys())}")

    async def get_project_execution_mode(self, project_id: UUID) -> Optional[str]:
        """
        Get the execution mode for a project.

        Args:
            project_id: Project UUID

        Returns:
            Execution mode string or None
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            if not row or not row['metadata']:
                return None

            metadata = row['metadata']
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            return metadata.get('execution_mode')

    # =========================================================================
    # Epic Operations
    # =========================================================================

    async def create_epic(
        self,
        project_id: UUID,
        name: str,
        description: Optional[str] = None,
        priority: int = 0
    ) -> Dict[str, Any]:
        """
        Create a new epic.

        Args:
            project_id: Project UUID
            name: Epic name
            description: Epic description
            priority: Epic priority (lower = higher priority)

        Returns:
            Created epic record
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO epics (project_id, name, description, priority)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                project_id, name, description, priority
            )
            return dict(row)

    async def list_epics(
        self,
        project_id: UUID,
        only_pending: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List epics for a project.

        Args:
            project_id: Project UUID
            only_pending: Only return non-completed epics

        Returns:
            List of epic records
        """
        query = "SELECT * FROM epics WHERE project_id = $1"
        if only_pending:
            query += " AND status != 'completed'"
        query += " ORDER BY priority, id"

        async with self.acquire() as conn:
            rows = await conn.fetch(query, project_id)
            return [dict(row) for row in rows]

    async def get_epics_needing_expansion(
        self,
        project_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get epics that have no tasks yet.

        Args:
            project_id: Project UUID

        Returns:
            List of epics needing expansion
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT e.*
                FROM epics e
                LEFT JOIN tasks t ON e.id = t.epic_id
                WHERE e.project_id = $1
                GROUP BY e.id
                HAVING COUNT(t.id) = 0
                ORDER BY e.priority
                """,
                project_id
            )
            return [dict(row) for row in rows]

    # =========================================================================
    # Task Operations
    # =========================================================================

    async def create_task(
        self,
        epic_id: int,
        project_id: UUID,
        description: str,
        action: Optional[str] = None,
        priority: int = 0
    ) -> Dict[str, Any]:
        """
        Create a new task.

        Args:
            epic_id: Epic ID
            project_id: Project UUID
            description: Task description
            action: Implementation details
            priority: Task priority

        Returns:
            Created task record
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tasks (epic_id, project_id, description, action, priority)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                epic_id, project_id, description, action, priority
            )
            return dict(row)

    async def get_next_task(self, project_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get next task to work on for a project.

        Args:
            project_id: Project UUID

        Returns:
            Next task with epic info and tests, or None
        """
        async with self.acquire() as conn:
            # Get the next task
            task_row = await conn.fetchrow(
                """
                SELECT
                    t.*,
                    e.name as epic_name,
                    e.description as epic_description
                FROM tasks t
                JOIN epics e ON t.epic_id = e.id
                WHERE t.project_id = $1
                    AND t.done = false
                    AND e.status != 'completed'
                ORDER BY e.priority, t.priority, t.id
                LIMIT 1
                """,
                project_id
            )

            if not task_row:
                return None

            task = dict(task_row)

            # Get tests for this task
            test_rows = await conn.fetch(
                """
                SELECT * FROM tests
                WHERE task_id = $1
                ORDER BY id
                """,
                task['id']
            )

            task['tests'] = [dict(row) for row in test_rows]

            return task

    async def update_task_status(
        self,
        task_id: int,
        done: bool,
        session_id: Optional[UUID] = None,
        session_notes: Optional[str] = None
    ) -> None:
        """
        Update task completion status.

        Args:
            task_id: Task ID
            done: Whether task is complete
            session_id: Session that completed the task
            session_notes: Notes from session
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE tasks
                SET done = $1,
                    completed_at = CASE WHEN $1 THEN NOW() ELSE NULL END,
                    session_id = COALESCE($2, session_id),
                    session_notes = COALESCE($3, session_notes)
                WHERE id = $4
                """,
                done, session_id, session_notes, task_id
            )

    async def list_tasks(
        self,
        project_id: UUID,
        epic_id: Optional[int] = None,
        only_pending: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List tasks with optional filtering.

        Args:
            project_id: Project UUID
            epic_id: Filter by epic
            only_pending: Only incomplete tasks
            limit: Maximum tasks to return

        Returns:
            List of task records
        """
        query = """
            SELECT t.*, e.name as epic_name
            FROM tasks t
            JOIN epics e ON t.epic_id = e.id
            WHERE t.project_id = $1
        """
        params = [project_id]

        if epic_id:
            params.append(epic_id)
            query += f" AND t.epic_id = ${len(params)}"

        if only_pending:
            query += " AND t.done = false"

        query += " ORDER BY e.priority, t.priority, t.id"

        if limit:
            params.append(limit)
            query += f" LIMIT ${len(params)}"

        async with self.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    # =========================================================================
    # Test Operations
    # =========================================================================

    async def create_test(
        self,
        task_id: int,
        project_id: UUID,
        category: str,
        description: str,
        steps: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new test for a task.

        Args:
            task_id: Task ID
            project_id: Project UUID
            category: Test category
            description: Test description
            steps: List of test steps

        Returns:
            Created test record
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tests (task_id, project_id, category, description, steps)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                task_id, project_id, category, description,
                json.dumps(steps) if steps else '[]'
            )
            return dict(row)

    async def update_test_result(
        self,
        test_id: int,
        passes: bool,
        session_id: Optional[UUID] = None,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update test result.

        Args:
            test_id: Test ID
            passes: Whether test passed
            session_id: Session that ran the test
            result: Test result details
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE tests
                SET passes = $1,
                    verified_at = CASE WHEN $1 THEN NOW() ELSE NULL END,
                    session_id = COALESCE($2, session_id),
                    result = COALESCE($3::jsonb, result)
                WHERE id = $4
                """,
                passes, session_id,
                json.dumps(result) if result else None,
                test_id
            )

    # =========================================================================
    # Progress and Statistics
    # =========================================================================

    async def get_progress(self, project_id: UUID) -> Dict[str, Any]:
        """
        Get overall project progress statistics.

        Args:
            project_id: Project UUID

        Returns:
            Progress statistics dictionary
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM v_progress
                WHERE project_id = $1
                """,
                project_id
            )

            if row:
                return dict(row)
            else:
                # Return empty stats if no data
                return {
                    "project_id": project_id,
                    "total_epics": 0,
                    "completed_epics": 0,
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "total_tests": 0,
                    "passing_tests": 0,
                    "task_completion_pct": 0.0,
                    "test_pass_pct": 0.0
                }

    async def get_epic_progress(
        self,
        project_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get progress for each epic.

        Args:
            project_id: Project UUID

        Returns:
            List of epic progress records
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM v_epic_progress
                WHERE project_id = $1
                ORDER BY epic_id
                """,
                project_id
            )
            return [dict(row) for row in rows]

    async def get_task_with_tests(
        self,
        task_id: int,
        project_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get task with all associated tests and epic context.

        Args:
            task_id: Task ID
            project_id: Project UUID

        Returns:
            Task dict with 'tests' array and 'epic_name' field, or None if not found
        """
        async with self.acquire() as conn:
            # Get task with epic name
            task_row = await conn.fetchrow(
                """
                SELECT t.*, e.name as epic_name, e.description as epic_description
                FROM tasks t
                JOIN epics e ON t.epic_id = e.id
                WHERE t.id = $1 AND t.project_id = $2
                """,
                task_id, project_id
            )

            if not task_row:
                return None

            task = dict(task_row)

            # Get tests for this task
            tests = await conn.fetch(
                """
                SELECT *
                FROM tests
                WHERE task_id = $1
                ORDER BY category, id
                """,
                task_id
            )
            task['tests'] = [dict(test) for test in tests]

            return task

    async def get_epic_with_tasks(
        self,
        epic_id: int,
        project_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get epic with all tasks and their test counts.

        Args:
            epic_id: Epic ID
            project_id: Project UUID

        Returns:
            Epic dict with 'tasks' array (including test_count per task), or None if not found
        """
        async with self.acquire() as conn:
            # Get epic
            epic_row = await conn.fetchrow(
                """
                SELECT *
                FROM epics
                WHERE id = $1 AND project_id = $2
                """,
                epic_id, project_id
            )

            if not epic_row:
                return None

            epic = dict(epic_row)

            # Get tasks with test counts
            tasks = await conn.fetch(
                """
                SELECT
                    t.*,
                    COUNT(ts.id) as test_count,
                    SUM(CASE WHEN ts.passes = true THEN 1 ELSE 0 END) as passing_test_count
                FROM tasks t
                LEFT JOIN tests ts ON t.id = ts.task_id
                WHERE t.epic_id = $1
                GROUP BY t.id
                ORDER BY t.priority, t.id
                """,
                epic_id
            )
            epic['tasks'] = [dict(task) for task in tasks]

            return epic

    # =========================================================================
    # Session Quality Checks (Phase 1 Review System Integration)
    # =========================================================================
    # Note: Legacy methods removed in cleanup (create_review, record_github_commit,
    #       get/update_project_preferences) - tables were never used

    async def store_quality_check(
        self,
        session_id: UUID,
        metrics: Dict[str, Any],
        critical_issues: List[str],
        warnings: List[str],
        overall_rating: Optional[int] = None,
        check_version: str = "1.0"
    ) -> UUID:
        """
        Store quality check results for a session (quick checks only).

        Args:
            session_id: Session UUID
            metrics: Full metrics dict from review_metrics.analyze_session_logs()
            critical_issues: List of critical issue strings
            warnings: List of warning strings
            overall_rating: Optional 1-10 quality score
            check_version: Version of quality check logic

        Returns:
            UUID of created quality check record
        """
        async with self.acquire() as conn:
            # Extract key metrics for indexed columns
            playwright_count = metrics.get('playwright_count', 0)
            playwright_screenshot_count = metrics.get('playwright_screenshot_count', 0)
            total_tool_uses = metrics.get('total_tool_uses', 0)
            error_count = metrics.get('error_count', 0)
            error_rate = metrics.get('error_rate', 0.0)

            check_id = await conn.fetchval(
                """
                INSERT INTO session_quality_checks (
                    session_id,
                    check_version,
                    overall_rating,
                    playwright_count,
                    playwright_screenshot_count,
                    total_tool_uses,
                    error_count,
                    error_rate,
                    critical_issues,
                    warnings,
                    metrics
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
                """,
                session_id, check_version, overall_rating,
                playwright_count, playwright_screenshot_count, total_tool_uses,
                error_count, error_rate,
                json.dumps(critical_issues), json.dumps(warnings), json.dumps(metrics)
            )
            return check_id

    async def store_deep_review(
        self,
        session_id: UUID,
        metrics: Dict[str, Any],
        overall_rating: int,
        review_text: str,
        prompt_improvements: List[str],
        review_summary: Optional[Dict[str, Any]] = None,
        review_version: str = "2.0",
        model: Optional[str] = None
    ) -> UUID:
        """
        Store deep review results for a session (Phase 2 Review System).

        Now stores in the dedicated session_deep_reviews table.

        Args:
            session_id: Session UUID
            metrics: Full metrics dict from review_metrics.analyze_session_logs() (used for quick check)
            overall_rating: 1-10 quality score
            review_text: Full review report (markdown)
            prompt_improvements: List of prompt improvement recommendations
            review_summary: Optional structured summary data (rating, one_line, summary text)
            review_version: Version of review logic (default: "2.0" for Phase 2)
            model: Optional model name used for review

        Returns:
            UUID of created deep review record
        """
        async with self.acquire() as conn:
            # Store deep review in session_deep_reviews table
            # Use ON CONFLICT to update existing review instead of creating duplicate
            review_id = await conn.fetchval(
                """
                INSERT INTO session_deep_reviews (
                    session_id,
                    review_version,
                    overall_rating,
                    review_text,
                    review_summary,
                    prompt_improvements,
                    model
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (session_id) DO UPDATE SET
                    review_version = EXCLUDED.review_version,
                    overall_rating = EXCLUDED.overall_rating,
                    review_text = EXCLUDED.review_text,
                    review_summary = EXCLUDED.review_summary,
                    prompt_improvements = EXCLUDED.prompt_improvements,
                    model = EXCLUDED.model,
                    created_at = NOW()
                RETURNING id
                """,
                session_id,
                review_version,
                overall_rating,
                review_text,
                json.dumps(review_summary or {}),  # review_summary extracted from Executive Summary
                json.dumps(prompt_improvements),
                model
            )

            return review_id

    async def get_session_quality(
        self,
        session_id: UUID,
        include_deep_review: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get quality check results for a session.

        Now queries both session_quality_checks and session_deep_reviews tables.

        Args:
            session_id: Session UUID
            include_deep_review: If True, also fetch deep review data (default: True)

        Returns:
            Quality check dict with optional deep review fields, or None if not found
        """
        async with self.acquire() as conn:
            # Get quick check
            quick_check = await conn.fetchrow(
                """
                SELECT
                    id,
                    session_id,
                    check_version,
                    created_at,
                    overall_rating,
                    playwright_count,
                    playwright_screenshot_count,
                    total_tool_uses,
                    error_count,
                    error_rate,
                    critical_issues,
                    warnings,
                    metrics
                FROM session_quality_checks
                WHERE session_id = $1
                ORDER BY created_at DESC LIMIT 1
                """,
                session_id
            )

            if not quick_check:
                return None

            # Convert to dict
            result = dict(quick_check)
            result['check_type'] = 'quick'  # Add for backwards compatibility

            # Parse JSONB fields
            jsonb_fields = ['critical_issues', 'warnings', 'metrics']
            for field in jsonb_fields:
                if field in result and isinstance(result[field], str):
                    try:
                        result[field] = json.loads(result[field])
                    except (json.JSONDecodeError, TypeError):
                        result[field] = [] if field in ['critical_issues', 'warnings'] else {}

            # Get deep review if requested
            if include_deep_review:
                deep_review = await conn.fetchrow(
                    """
                    SELECT
                        id as review_id,
                        review_version,
                        created_at as review_created_at,
                        overall_rating as review_rating,
                        review_text,
                        review_summary,
                        prompt_improvements,
                        model
                    FROM session_deep_reviews
                    WHERE session_id = $1
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    session_id
                )

                if deep_review:
                    # Add deep review fields
                    result['has_deep_review'] = True
                    result['review_id'] = deep_review['review_id']
                    result['review_version'] = deep_review['review_version']
                    result['review_created_at'] = deep_review['review_created_at']
                    result['review_rating'] = deep_review['review_rating']
                    result['review_text'] = deep_review['review_text']
                    result['model'] = deep_review['model']

                    # Parse JSONB fields from deep review
                    for field in ['review_summary', 'prompt_improvements']:
                        value = deep_review[field]
                        if isinstance(value, str):
                            try:
                                result[field] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                result[field] = {} if field == 'review_summary' else []
                        else:
                            result[field] = value
                else:
                    result['has_deep_review'] = False

            return result

    async def get_project_quality_summary(
        self,
        project_id: UUID
    ) -> Dict[str, Any]:
        """
        Get overall quality summary for a project.

        Returns aggregate statistics across all sessions.

        Args:
            project_id: Project UUID

        Returns:
            Dict with quality summary stats
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM v_project_quality WHERE project_id = $1
                """,
                project_id
            )
            return dict(row) if row else {
                'project_id': str(project_id),
                'total_sessions': 0,
                'checked_sessions': 0,
                'avg_quality_rating': None,
                'sessions_without_browser_verification': 0,
                'avg_error_rate_percent': None,
                'avg_playwright_calls_per_session': None
            }

    async def list_deep_reviews(
        self,
        project_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all deep reviews for a project.

        Args:
            project_id: Project UUID

        Returns:
            List of deep review dicts with session info
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    dr.id,
                    dr.session_id,
                    s.session_number,
                    dr.review_version,
                    dr.created_at,
                    dr.overall_rating,
                    dr.review_text,
                    dr.review_summary,
                    dr.prompt_improvements,
                    dr.model
                FROM session_deep_reviews dr
                JOIN sessions s ON dr.session_id = s.id
                WHERE s.project_id = $1
                ORDER BY s.session_number ASC
                """,
                project_id
            )

            results = []
            for row in rows:
                result = dict(row)
                # Parse JSONB fields
                for field in ['review_summary', 'prompt_improvements']:
                    value = result.get(field)
                    if isinstance(value, str):
                        try:
                            result[field] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            result[field] = {} if field == 'review_summary' else []
                results.append(result)

            return results

    async def get_sessions_with_quality_issues(
        self,
        project_id: Optional[UUID] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent sessions with quality issues.

        Args:
            project_id: Optional filter by project
            limit: Maximum number of sessions to return

        Returns:
            List of session dicts with quality issues
        """
        async with self.acquire() as conn:
            query = "SELECT * FROM v_recent_quality_issues"

            if project_id:
                query += " WHERE project_id = $1"
                query += f" LIMIT {limit}"
                rows = await conn.fetch(query, project_id)
            else:
                query += f" LIMIT {limit}"
                rows = await conn.fetch(query)

            return [dict(row) for row in rows]

    async def get_browser_verification_compliance(
        self,
        project_id: UUID
    ) -> Dict[str, Any]:
        """
        Get browser verification compliance stats for a project.

        Returns breakdown of sessions by Playwright usage level.

        Args:
            project_id: Project UUID

        Returns:
            Dict with compliance statistics
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM v_browser_verification_compliance
                WHERE project_id = $1
                """,
                project_id
            )
            return dict(row) if row else {
                'project_id': str(project_id),
                'total_sessions': 0,
                'sessions_with_verification': 0,
                'sessions_excellent_verification': 0,
                'sessions_good_verification': 0,
                'sessions_minimal_verification': 0,
                'sessions_no_verification': 0,
                'verification_rate_percent': 0.0
            }

    # =========================================================================
    # Prompt Improvement Operations
    # =========================================================================

    async def create_prompt_analysis(
        self,
        project_ids: List[UUID],
        sandbox_type: str,
        triggered_by: str = "manual",
        user_id: Optional[UUID] = None
    ) -> UUID:
        """
        Create a new prompt improvement analysis record.

        Args:
            project_ids: List of project UUIDs to analyze
            sandbox_type: 'docker' or 'local'
            triggered_by: How analysis was triggered
            user_id: Optional user ID

        Returns:
            Analysis UUID
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO prompt_improvement_analyses (
                    projects_analyzed,
                    sandbox_type,
                    triggered_by,
                    user_id,
                    status
                )
                VALUES ($1, $2, $3, $4, 'pending')
                RETURNING id
                """,
                project_ids, sandbox_type, triggered_by, user_id
            )
            return row['id']

    async def get_prompt_analysis(self, analysis_id: UUID) -> Optional[Dict[str, Any]]:
        """Get prompt analysis by ID."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM prompt_improvement_analyses WHERE id = $1",
                analysis_id
            )
            return dict(row) if row else None

    async def list_prompt_analyses(
        self,
        limit: int = 20,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List prompt improvement analyses.

        Args:
            limit: Maximum number to return
            status: Optional filter by status

        Returns:
            List of analysis records
        """
        async with self.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM v_recent_analyses
                    WHERE status = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    status, limit
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM v_recent_analyses
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit
                )
            return [dict(row) for row in rows]

    async def update_prompt_analysis_status(
        self,
        analysis_id: UUID,
        status: str,
        **kwargs
    ):
        """
        Update analysis status and optional fields.

        Args:
            analysis_id: Analysis UUID
            status: New status
            **kwargs: Additional fields to update
        """
        fields = ["status = $2"]
        params = [analysis_id, status]
        idx = 3

        for key, value in kwargs.items():
            fields.append(f"{key} = ${idx}")
            params.append(value)
            idx += 1

        query = f"""
            UPDATE prompt_improvement_analyses
            SET {', '.join(fields)}
            WHERE id = $1
        """

        async with self.acquire() as conn:
            await conn.execute(query, *params)

    async def delete_prompt_analysis(self, analysis_id: UUID) -> bool:
        """
        Delete a prompt improvement analysis.

        Cascades to delete all proposals associated with this analysis.

        Args:
            analysis_id: UUID of the analysis to delete

        Returns:
            True if deleted successfully
        """
        async with self.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM prompt_improvement_analyses
                WHERE id = $1
                """,
                analysis_id
            )
            # Return True if at least one row was deleted
            return result.split()[-1] != '0'

    async def create_prompt_proposal(
        self,
        analysis_id: UUID,
        prompt_file: str,
        section_name: str,
        change_type: str,
        original_text: str,
        proposed_text: str,
        rationale: str,
        evidence: List[Dict[str, Any]],
        confidence_level: int
    ) -> UUID:
        """
        Create a prompt change proposal.

        Args:
            analysis_id: Parent analysis UUID
            prompt_file: Name of prompt file
            section_name: Section to modify
            change_type: Type of change
            original_text: Current text
            proposed_text: Proposed new text
            rationale: Why this change is needed
            evidence: Supporting evidence
            confidence_level: 1-10 confidence score

        Returns:
            Proposal UUID
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO prompt_proposals (
                    analysis_id,
                    prompt_file,
                    section_name,
                    change_type,
                    original_text,
                    proposed_text,
                    rationale,
                    evidence,
                    confidence_level
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                analysis_id,
                prompt_file,
                section_name,
                change_type,
                original_text,
                proposed_text,
                rationale,
                json.dumps(evidence),
                confidence_level
            )
            return row['id']

    async def get_prompt_proposal(self, proposal_id: UUID) -> Optional[Dict[str, Any]]:
        """Get prompt proposal by ID."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM prompt_proposals WHERE id = $1",
                proposal_id
            )
            return dict(row) if row else None

    async def list_prompt_proposals(
        self,
        analysis_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List prompt proposals.

        Args:
            analysis_id: Optional filter by analysis
            status: Optional filter by status
            limit: Maximum number to return

        Returns:
            List of proposal records
        """
        async with self.acquire() as conn:
            if analysis_id:
                if status:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM prompt_proposals
                        WHERE analysis_id = $1 AND status = $2
                        ORDER BY confidence_level DESC, created_at DESC
                        LIMIT $3
                        """,
                        analysis_id, status, limit
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM prompt_proposals
                        WHERE analysis_id = $1
                        ORDER BY confidence_level DESC, created_at DESC
                        LIMIT $2
                        """,
                        analysis_id, limit
                    )
            elif status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM v_pending_proposals
                    WHERE status = $1
                    LIMIT $2
                    """,
                    status, limit
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM prompt_proposals
                    ORDER BY confidence_level DESC, created_at DESC
                    LIMIT $1
                    """,
                    limit
                )
            return [dict(row) for row in rows]

    async def update_prompt_proposal_status(
        self,
        proposal_id: UUID,
        status: str,
        applied_by: Optional[str] = None,
        applied_to_version: Optional[str] = None
    ):
        """
        Update proposal status.

        Args:
            proposal_id: Proposal UUID
            status: New status ('accepted', 'rejected', 'implemented')
            applied_by: Who applied the change
            applied_to_version: Git commit hash
        """
        async with self.acquire() as conn:
            if status == 'implemented':
                await conn.execute(
                    """
                    UPDATE prompt_proposals
                    SET
                        status = $2,
                        applied_at = NOW(),
                        applied_by = $3,
                        applied_to_version = $4
                    WHERE id = $1
                    """,
                    proposal_id, status, applied_by, applied_to_version
                )
            else:
                await conn.execute(
                    """
                    UPDATE prompt_proposals
                    SET status = $2
                    WHERE id = $1
                    """,
                    proposal_id, status
                )

    async def get_project_review_stats(
        self,
        project_id: UUID
    ) -> Dict[str, Any]:
        """
        Get project statistics including session count and deep review coverage.

        Returns:
            Dict with total_sessions, sessions_with_reviews, sessions_without_reviews, coverage_percent, unreviewed_session_numbers
        """
        async with self.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT s.id) as total_sessions,
                    COUNT(dr.id) as sessions_with_reviews,
                    COUNT(DISTINCT s.id) - COUNT(dr.id) as sessions_without_reviews,
                    CASE
                        WHEN COUNT(DISTINCT s.id) > 0
                        THEN ROUND((COUNT(dr.id)::decimal / COUNT(DISTINCT s.id)::decimal) * 100, 1)
                        ELSE 0
                    END as coverage_percent
                FROM sessions s
                LEFT JOIN session_deep_reviews dr ON s.id = dr.session_id
                WHERE s.project_id = $1 AND s.type = 'coding' AND s.status = 'completed'
                """,
                project_id
            )

            # Get list of unreviewed session numbers (exclude Session 0 - initialization)
            unreviewed = await conn.fetch(
                """
                SELECT s.session_number
                FROM sessions s
                LEFT JOIN session_deep_reviews dr ON s.id = dr.session_id
                WHERE s.project_id = $1
                  AND s.status = 'completed'
                  AND s.type = 'coding'
                  AND dr.id IS NULL
                ORDER BY s.session_number
                """,
                project_id
            )

            result = dict(stats) if stats else {
                'total_sessions': 0,
                'sessions_with_reviews': 0,
                'sessions_without_reviews': 0,
                'coverage_percent': 0.0
            }
            result['unreviewed_session_numbers'] = [row['session_number'] for row in unreviewed]
            return result

    # =========================================================================
    # Parallel Batch Operations
    # =========================================================================

    async def create_parallel_batch(
        self,
        project_id: UUID,
        batch_number: int,
        task_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Create a new parallel batch record.

        Args:
            project_id: Project UUID
            batch_number: Sequential batch number
            task_ids: List of task IDs in this batch

        Returns:
            Created batch record
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO parallel_batches
                    (project_id, batch_number, task_ids, status)
                    VALUES ($1, $2, $3, 'pending')
                    RETURNING *
                    """,
                    project_id, batch_number, task_ids
                )
                logger.info(f"Created parallel batch {batch_number} for project {project_id} with {len(task_ids)} tasks")
                return dict(row)
        except Exception as e:
            logger.error(f"Failed to create parallel batch: {e}")
            raise

    async def get_parallel_batch(self, batch_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single parallel batch by ID.

        Args:
            batch_id: Batch ID

        Returns:
            Batch record or None if not found
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM parallel_batches WHERE id = $1",
                    batch_id
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get parallel batch {batch_id}: {e}")
            raise

    async def list_parallel_batches(self, project_id: UUID) -> List[Dict[str, Any]]:
        """
        List all parallel batches for a project.

        Args:
            project_id: Project UUID

        Returns:
            List of batch records ordered by batch_number
        """
        try:
            async with self.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM parallel_batches
                    WHERE project_id = $1
                    ORDER BY batch_number
                    """,
                    project_id
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list parallel batches for project {project_id}: {e}")
            raise

    async def update_batch_status(
        self,
        batch_id: int,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ) -> None:
        """
        Update parallel batch status.

        Args:
            batch_id: Batch ID
            status: New status (pending/running/completed/failed/cancelled)
            started_at: Optional timestamp when batch started
            completed_at: Optional timestamp when batch completed
        """
        try:
            async with self.acquire() as conn:
                # Build dynamic query based on provided fields
                updates = ["status = $2"]
                params = [batch_id, status]
                param_idx = 3

                if started_at is not None:
                    updates.append(f"started_at = ${param_idx}")
                    params.append(started_at)
                    param_idx += 1

                if completed_at is not None:
                    updates.append(f"completed_at = ${param_idx}")
                    params.append(completed_at)
                    param_idx += 1

                query = f"""
                    UPDATE parallel_batches
                    SET {', '.join(updates)}
                    WHERE id = $1
                """

                await conn.execute(query, *params)
                logger.info(f"Updated batch {batch_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update batch {batch_id} status: {e}")
            raise

    # =========================================================================
    # Worktree Operations
    # =========================================================================

    async def create_worktree(
        self,
        project_id: UUID,
        epic_id: int,
        branch_name: str,
        worktree_path: str
    ) -> Dict[str, Any]:
        """
        Create a new worktree record.

        Args:
            project_id: Project UUID
            epic_id: Epic ID this worktree is for
            branch_name: Git branch name
            worktree_path: Path to worktree directory

        Returns:
            Created worktree record
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO worktrees
                    (project_id, epic_id, branch_name, worktree_path, status)
                    VALUES ($1, $2, $3, $4, 'active')
                    RETURNING *
                    """,
                    project_id, epic_id, branch_name, worktree_path
                )
                logger.info(f"Created worktree for epic {epic_id}: {branch_name} at {worktree_path}")
                return dict(row)
        except Exception as e:
            logger.error(f"Failed to create worktree for epic {epic_id}: {e}")
            raise

    async def get_worktree(self, worktree_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single worktree by ID.

        Args:
            worktree_id: Worktree ID

        Returns:
            Worktree record or None if not found
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM worktrees WHERE id = $1",
                    worktree_id
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get worktree {worktree_id}: {e}")
            raise

    async def get_worktree_by_epic(
        self,
        project_id: UUID,
        epic_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get worktree for a specific epic.

        Args:
            project_id: Project UUID
            epic_id: Epic ID

        Returns:
            Worktree record or None if not found
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM worktrees
                    WHERE project_id = $1 AND epic_id = $2
                    """,
                    project_id, epic_id
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get worktree for epic {epic_id}: {e}")
            raise

    async def list_worktrees(self, project_id: UUID) -> List[Dict[str, Any]]:
        """
        List all worktrees for a project.

        Args:
            project_id: Project UUID

        Returns:
            List of worktree records ordered by created_at
        """
        try:
            async with self.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM worktrees
                    WHERE project_id = $1
                    ORDER BY created_at DESC
                    """,
                    project_id
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list worktrees for project {project_id}: {e}")
            raise

    async def mark_worktree_merged(
        self,
        worktree_id: int,
        merge_commit: str
    ) -> None:
        """
        Mark worktree as merged with commit hash.

        Args:
            worktree_id: Worktree ID
            merge_commit: SHA of the merge commit
        """
        try:
            async with self.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE worktrees
                    SET status = 'merged',
                        merge_commit = $2,
                        merged_at = NOW()
                    WHERE id = $1
                    """,
                    worktree_id, merge_commit
                )
                logger.info(f"Marked worktree {worktree_id} as merged: {merge_commit}")
        except Exception as e:
            logger.error(f"Failed to mark worktree {worktree_id} as merged: {e}")
            raise

    async def update_worktree(
        self,
        worktree_id: int,
        status: Optional[str] = None,
        merge_commit: Optional[str] = None
    ) -> bool:
        """
        Update worktree record by epic_id.

        Note: worktree_id parameter actually accepts epic_id for compatibility
        with worktree_manager.py which uses epic_id as the identifier.
        The lookup is done by epic_id via the UNIQUE(project_id, epic_id) constraint.

        Args:
            worktree_id: Epic ID (not worktree table ID)
            status: New status (active, merged, conflict, abandoned, cleanup)
            merge_commit: Merge commit SHA (optional)

        Returns:
            True if updated successfully
        """
        try:
            async with self.acquire() as conn:
                # Build dynamic update
                updates = []
                params = []
                param_idx = 1

                if status is not None:
                    updates.append(f"status = ${param_idx}")
                    params.append(status)
                    param_idx += 1

                if merge_commit is not None:
                    updates.append(f"merge_commit = ${param_idx}")
                    params.append(merge_commit)
                    param_idx += 1
                    updates.append(f"merged_at = NOW()")

                if not updates:
                    return False

                # Update by epic_id (the worktree_id parameter is actually epic_id)
                params.append(worktree_id)
                query = f"""
                    UPDATE worktrees
                    SET {', '.join(updates)}
                    WHERE epic_id = ${param_idx}
                """

                result = await conn.execute(query, *params)
                updated = result.split()[-1] != '0'
                if updated:
                    logger.info(f"Updated worktree for epic {worktree_id}: status={status}")
                return updated
        except Exception as e:
            logger.error(f"Failed to update worktree for epic {worktree_id}: {e}")
            raise

    async def delete_worktree(self, worktree_id: int) -> bool:
        """
        Delete a worktree record.

        Args:
            worktree_id: Worktree ID

        Returns:
            True if deleted successfully
        """
        try:
            async with self.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM worktrees WHERE id = $1",
                    worktree_id
                )
                deleted = result.split()[-1] != '0'
                if deleted:
                    logger.info(f"Deleted worktree {worktree_id}")
                return deleted
        except Exception as e:
            logger.error(f"Failed to delete worktree {worktree_id}: {e}")
            raise

    # =========================================================================
    # Agent Cost Tracking Operations
    # =========================================================================

    async def record_agent_cost(
        self,
        project_id: UUID,
        session_id: Optional[UUID],
        task_id: Optional[int],
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float
    ) -> Dict[str, Any]:
        """
        Record agent execution cost.

        Args:
            project_id: Project UUID
            session_id: Optional session UUID
            task_id: Optional task ID
            model: Model name (haiku/sonnet/opus)
            input_tokens: Input token count
            output_tokens: Output token count
            cost_usd: Cost in USD

        Returns:
            Created cost record
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO agent_costs
                    (project_id, session_id, task_id, model, input_tokens, output_tokens, cost_usd)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING *
                    """,
                    project_id, session_id, task_id, model, input_tokens, output_tokens, cost_usd
                )
                logger.info(f"Recorded cost ${cost_usd:.4f} for {model} (task {task_id})")
                return dict(row)
        except Exception as e:
            logger.error(f"Failed to record agent cost: {e}")
            raise

    async def get_project_costs(self, project_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all cost records for a project.

        Args:
            project_id: Project UUID

        Returns:
            List of cost records ordered by created_at
        """
        try:
            async with self.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM agent_costs
                    WHERE project_id = $1
                    ORDER BY created_at DESC
                    """,
                    project_id
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get project costs: {e}")
            raise

    async def get_cost_by_model(self, project_id: UUID) -> List[Dict[str, Any]]:
        """
        Get costs aggregated by model.

        Args:
            project_id: Project UUID

        Returns:
            List of aggregated costs by model from v_project_costs view
        """
        try:
            async with self.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM v_project_costs
                    WHERE project_id = $1
                    ORDER BY total_cost_usd DESC
                    """,
                    project_id
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get costs by model: {e}")
            raise

    async def get_session_cost(self, session_id: UUID) -> Dict[str, Any]:
        """
        Get total cost for a specific session.

        Args:
            session_id: Session UUID

        Returns:
            Dict with total_cost_usd, total_input_tokens, total_output_tokens
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        COALESCE(SUM(cost_usd), 0) as total_cost_usd,
                        COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                        COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                        COUNT(*) as cost_entries
                    FROM agent_costs
                    WHERE session_id = $1
                    """,
                    session_id
                )
                return dict(row) if row else {
                    'total_cost_usd': 0,
                    'total_input_tokens': 0,
                    'total_output_tokens': 0,
                    'cost_entries': 0
                }
        except Exception as e:
            logger.error(f"Failed to get session cost: {e}")
            raise

    async def get_total_cost(self, project_id: UUID) -> float:
        """
        Get total cost for a project.

        Args:
            project_id: Project UUID

        Returns:
            Total cost in USD
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT COALESCE(SUM(cost_usd), 0) as total_cost
                    FROM agent_costs
                    WHERE project_id = $1
                    """,
                    project_id
                )
                return float(row['total_cost']) if row else 0.0
        except Exception as e:
            logger.error(f"Failed to get total cost: {e}")
            raise

    # =========================================================================
    # Expertise Management Operations
    # =========================================================================

    async def get_expertise(
        self,
        project_id: UUID,
        domain: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get expertise file for a specific domain.

        Args:
            project_id: Project UUID
            domain: Expertise domain (database/api/frontend/testing/security/deployment/general)

        Returns:
            Expertise record or None if not found
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM expertise_files
                    WHERE project_id = $1 AND domain = $2
                    """,
                    project_id, domain
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get expertise for domain {domain}: {e}")
            raise

    async def save_expertise(
        self,
        project_id: UUID,
        domain: str,
        content: Dict[str, Any],
        line_count: int
    ) -> Dict[str, Any]:
        """
        Save or update expertise file.

        Args:
            project_id: Project UUID
            domain: Expertise domain
            content: JSONB content (core_files, patterns, techniques, learnings)
            line_count: Approximate line count

        Returns:
            Created or updated expertise record
        """
        try:
            async with self.acquire() as conn:
                # Use INSERT ... ON CONFLICT to handle upsert
                row = await conn.fetchrow(
                    """
                    INSERT INTO expertise_files
                    (project_id, domain, content, line_count, version)
                    VALUES ($1, $2, $3, $4, 1)
                    ON CONFLICT (project_id, domain)
                    DO UPDATE SET
                        content = $3,
                        line_count = $4,
                        version = expertise_files.version + 1,
                        updated_at = NOW()
                    RETURNING *
                    """,
                    project_id, domain, json.dumps(content), line_count
                )
                logger.info(f"Saved expertise for domain {domain} (version {row['version']}, {line_count} lines)")
                return dict(row)
        except Exception as e:
            logger.error(f"Failed to save expertise for domain {domain}: {e}")
            raise

    async def list_expertise_domains(self, project_id: UUID) -> List[Dict[str, Any]]:
        """
        List all expertise domains for a project.

        Args:
            project_id: Project UUID

        Returns:
            List of expertise records with summary info
        """
        try:
            async with self.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        id,
                        domain,
                        version,
                        line_count,
                        validated_at,
                        created_at,
                        updated_at
                    FROM expertise_files
                    WHERE project_id = $1
                    ORDER BY domain
                    """,
                    project_id
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list expertise domains: {e}")
            raise

    async def record_expertise_update(
        self,
        expertise_id: int,
        session_id: Optional[UUID],
        change_type: str,
        summary: str,
        diff: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record an expertise update for audit trail.

        Args:
            expertise_id: Expertise file ID
            session_id: Optional session UUID
            change_type: Type of change (learned/validated/pruned/self_improved)
            summary: Summary of changes
            diff: Optional diff text

        Returns:
            Created update record
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO expertise_updates
                    (expertise_id, session_id, change_type, summary, diff)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING *
                    """,
                    expertise_id, session_id, change_type, summary, diff
                )
                logger.info(f"Recorded expertise update: {change_type} - {summary}")
                return dict(row)
        except Exception as e:
            logger.error(f"Failed to record expertise update: {e}")
            raise

    async def get_expertise_history(self, expertise_id: int) -> List[Dict[str, Any]]:
        """
        Get update history for an expertise file.

        Args:
            expertise_id: Expertise file ID

        Returns:
            List of update records ordered by created_at
        """
        try:
            async with self.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM expertise_updates
                    WHERE expertise_id = $1
                    ORDER BY created_at DESC
                    """,
                    expertise_id
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get expertise history: {e}")
            raise

    # =========================================================================
    # Dependency Management Operations
    # =========================================================================

    async def get_task_dependencies(self, task_id: int) -> Dict[str, Any]:
        """
        Get dependencies for a task.

        Args:
            task_id: Task ID

        Returns:
            Dict with depends_on array and dependency_type
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT depends_on, dependency_type
                    FROM tasks
                    WHERE id = $1
                    """,
                    task_id
                )
                return dict(row) if row else {'depends_on': [], 'dependency_type': 'hard'}
        except Exception as e:
            logger.error(f"Failed to get task dependencies for task {task_id}: {e}")
            raise

    async def set_task_dependencies(
        self,
        task_id: int,
        depends_on: List[int],
        dependency_type: str = 'hard'
    ) -> None:
        """
        Set dependencies for a task.

        Args:
            task_id: Task ID
            depends_on: List of task IDs this task depends on
            dependency_type: 'hard' (blocking) or 'soft' (non-blocking)
        """
        try:
            async with self.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tasks
                    SET depends_on = $2, dependency_type = $3
                    WHERE id = $1
                    """,
                    task_id, depends_on, dependency_type
                )
                logger.info(f"Set dependencies for task {task_id}: {depends_on} ({dependency_type})")
        except Exception as e:
            logger.error(f"Failed to set task dependencies: {e}")
            raise

    async def get_tasks_with_dependencies(self, project_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all tasks with their dependencies for a project.

        Args:
            project_id: Project UUID

        Returns:
            List of tasks with id, description, depends_on, dependency_type, epic_id
        """
        try:
            async with self.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        t.id,
                        t.epic_id,
                        t.description,
                        t.depends_on,
                        t.dependency_type,
                        t.priority,
                        t.done,
                        e.name as epic_name
                    FROM tasks t
                    JOIN epics e ON t.epic_id = e.id
                    WHERE t.project_id = $1
                    ORDER BY t.epic_id, t.priority, t.id
                    """,
                    project_id
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get tasks with dependencies: {e}")
            raise

    async def get_epic_dependencies(self, epic_id: int) -> List[int]:
        """
        Get dependencies for an epic.

        Args:
            epic_id: Epic ID

        Returns:
            List of epic IDs this epic depends on
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT depends_on
                    FROM epics
                    WHERE id = $1
                    """,
                    epic_id
                )
                return row['depends_on'] if row and row['depends_on'] else []
        except Exception as e:
            logger.error(f"Failed to get epic dependencies for epic {epic_id}: {e}")
            raise

    async def set_epic_dependencies(
        self,
        epic_id: int,
        depends_on: List[int]
    ) -> None:
        """
        Set dependencies for an epic.

        Args:
            epic_id: Epic ID
            depends_on: List of epic IDs this epic depends on
        """
        try:
            async with self.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE epics
                    SET depends_on = $2
                    WHERE id = $1
                    """,
                    epic_id, depends_on
                )
                logger.info(f"Set dependencies for epic {epic_id}: {depends_on}")
        except Exception as e:
            logger.error(f"Failed to set epic dependencies: {e}")
            raise


# =============================================================================
# Factory function for compatibility
# =============================================================================

async def get_database(connection_url: str) -> TaskDatabase:
    """
    Factory function to create and connect to database.

    Args:
        connection_url: PostgreSQL connection string

    Returns:
        Connected TaskDatabase instance
    """
    db = TaskDatabase(connection_url)
    await db.connect()
    return db