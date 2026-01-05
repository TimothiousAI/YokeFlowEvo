"""
Parallel Executor
=================

Orchestrates parallel task execution across multiple agents using worktrees.

Key Features:
- Manages batch-based parallel execution
- Respects max concurrency limits
- Creates and manages worktrees per epic
- Executes agents in isolated environments
- Tracks costs and performance
- Handles failures and cancellation
- Integrates with self-learning system
"""

from dataclasses import dataclass
from typing import Optional, List, Callable, Any
from datetime import datetime
from uuid import uuid4, UUID
import logging
import asyncio
import time

from core.parallel.worktree_manager import WorktreeManager
from core.parallel.dependency_resolver import DependencyResolver
from core.learning import ExpertiseManager, ModelSelector

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """
    Result of a task execution.

    Attributes:
        task_id: Task ID that was executed
        success: Whether execution succeeded
        duration: Execution time in seconds
        error: Error message if failed
        cost: Execution cost in USD
    """
    task_id: int
    success: bool
    duration: float
    error: Optional[str] = None
    cost: float = 0.0


@dataclass
class RunningAgent:
    """
    Information about a running agent.

    Attributes:
        task_id: Task being executed
        epic_id: Epic the task belongs to
        process: Async subprocess handle
        started_at: When execution started
    """
    task_id: int
    epic_id: int
    process: Any
    started_at: float


class ParallelExecutor:
    """
    Orchestrates parallel execution of tasks across multiple agents.

    Manages the complete parallel execution workflow:
    1. Resolve dependencies into batches
    2. Create worktrees for each epic
    3. Execute tasks in parallel (within concurrency limit)
    4. Merge successful worktrees
    5. Track costs and learning
    """

    def __init__(
        self,
        project_path: str,
        project_id: str,
        max_concurrency: int = 3,
        progress_callback: Optional[Callable] = None,
        db_connection: Optional[Any] = None
    ):
        """
        Initialize parallel executor.

        Args:
            project_path: Path to project repository
            project_id: Project UUID
            max_concurrency: Maximum concurrent agents (1-10)
            progress_callback: Optional callback for progress updates
            db_connection: Database connection for state management
        """
        self.project_path = project_path
        self.project_id = project_id
        self.max_concurrency = max_concurrency
        self.progress_callback = progress_callback
        self.db = db_connection

        # Initialize core components
        self.worktree_manager = WorktreeManager(
            project_path=project_path,
            project_id=project_id,
            db=db_connection
        )
        self.dependency_resolver = DependencyResolver(db_connection=db_connection)
        self.expertise_manager = ExpertiseManager(
            project_id=project_id,
            db_connection=db_connection
        )
        # ModelSelector will be initialized when needed (requires config)
        self.model_selector: Optional[ModelSelector] = None

        # Initialize concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.cancel_event = asyncio.Event()

        # Track running agents
        self.running_agents: List[RunningAgent] = []

        logger.info(f"ParallelExecutor initialized (max_concurrency={max_concurrency})")

    async def execute(self) -> List[ExecutionResult]:
        """
        Execute all incomplete tasks in parallel batches.

        Returns:
            List of ExecutionResult objects for all tasks
        """
        logger.info("Starting parallel execution")
        all_results = []

        try:
            # Load incomplete tasks from database
            if not self.db:
                logger.error("Database connection required for parallel execution")
                return []

            tasks = await self.db.get_tasks_with_dependencies(self.project_id)
            incomplete_tasks = [t for t in tasks if not t.get('done', False)]

            if not incomplete_tasks:
                logger.info("No incomplete tasks found")
                return []

            logger.info(f"Found {len(incomplete_tasks)} incomplete tasks")

            # Call DependencyResolver to compute batches
            dependency_graph = self.dependency_resolver.resolve(incomplete_tasks)

            if dependency_graph.circular_deps:
                logger.error(f"Circular dependencies detected: {dependency_graph.circular_deps}")
                # Continue with available batches despite circular deps

            if dependency_graph.missing_deps:
                logger.warning(f"Missing dependencies detected: {dependency_graph.missing_deps}")

            logger.info(f"Resolved into {len(dependency_graph.batches)} batches")

            # Create batch records in database
            for batch_number, task_ids in enumerate(dependency_graph.batches, start=1):
                await self.db.create_parallel_batch(
                    project_id=self.project_id,
                    batch_number=batch_number,
                    task_ids=task_ids
                )
                logger.info(f"Created batch {batch_number} with {len(task_ids)} tasks")

            # Initialize worktree manager
            await self.worktree_manager.initialize()
            logger.info("Worktree manager initialized")

            # Process batches sequentially (batch N must complete before batch N+1)
            for batch_number, task_ids in enumerate(dependency_graph.batches, start=1):
                if self.cancel_event.is_set():
                    logger.info("Execution cancelled")
                    break

                logger.info(f"Processing batch {batch_number}/{len(dependency_graph.batches)}")

                # Execute batch and collect results
                batch_results = await self.execute_batch(batch_number, task_ids)
                all_results.extend(batch_results)

                # Merge successful worktrees after each batch
                # This will be implemented when we have worktree merge logic
                logger.info(f"Batch {batch_number} complete with {len(batch_results)} results")

            logger.info(f"Parallel execution complete: {len(all_results)} tasks processed")
            return all_results

        except Exception as e:
            logger.error(f"Parallel execution failed: {e}", exc_info=True)
            return all_results

    async def execute_batch(self, batch_number: int, task_ids: List[int]) -> List[ExecutionResult]:
        """
        Execute a single batch of tasks in parallel.

        Args:
            batch_number: Batch number
            task_ids: List of task IDs to execute

        Returns:
            List of ExecutionResult objects
        """
        logger.info(f"Executing batch {batch_number} with {len(task_ids)} tasks")

        try:
            # Update batch status to running
            batch_record = None
            if self.db:
                # Find batch record
                batches = await self.db.list_parallel_batches(self.project_id)
                batch_record = next((b for b in batches if b['batch_number'] == batch_number), None)
                if batch_record:
                    await self.db.update_batch_status(
                        batch_id=batch_record['id'],
                        status='running',
                        started_at=datetime.now()
                    )

            # Load task details
            tasks_by_id = {}
            tasks_by_epic = {}  # epic_id -> list of tasks

            for task_id in task_ids:
                task = await self.db.get_task_with_tests(task_id, self.project_id)
                if not task:
                    logger.warning(f"Task {task_id} not found")
                    continue

                tasks_by_id[task_id] = task
                epic_id = task['epic_id']

                if epic_id not in tasks_by_epic:
                    tasks_by_epic[epic_id] = []
                tasks_by_epic[epic_id].append(task)

            # Create worktrees for each epic in batch (if not exists)
            worktree_paths = {}  # epic_id -> worktree_path
            for epic_id, tasks in tasks_by_epic.items():
                # Get epic name from first task
                epic_name = tasks[0].get('epic_name', f'Epic {epic_id}')

                try:
                    worktree_info = await self.worktree_manager.create_worktree(epic_id, epic_name)
                    worktree_paths[epic_id] = worktree_info.path
                    logger.info(f"Worktree ready for epic {epic_id}: {worktree_info.path}")
                except Exception as e:
                    logger.error(f"Failed to create worktree for epic {epic_id}: {e}")
                    # Continue with other epics

            # Use asyncio.gather() with return_exceptions=True for parallel execution
            # Create task coroutines
            task_coroutines = []
            for task_id in task_ids:
                if task_id not in tasks_by_id:
                    continue

                task = tasks_by_id[task_id]
                epic_id = task['epic_id']

                if epic_id not in worktree_paths:
                    logger.warning(f"No worktree for task {task_id} (epic {epic_id}), skipping")
                    continue

                worktree_path = worktree_paths[epic_id]
                task_coroutines.append(self._execute_task_with_semaphore(task, worktree_path))

            # Execute all tasks in parallel (respecting semaphore)
            results = await asyncio.gather(*task_coroutines, return_exceptions=True)

            # Process results and handle exceptions
            execution_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Task execution raised an exception
                    task_id = task_ids[i] if i < len(task_ids) else 0
                    logger.error(f"Task {task_id} execution failed with exception: {result}")
                    execution_results.append(ExecutionResult(
                        task_id=task_id,
                        success=False,
                        duration=0.0,
                        error=str(result)
                    ))
                else:
                    execution_results.append(result)

            # Update batch status to completed
            if self.db and batch_record:
                batch_status = 'completed' if all(r.success for r in execution_results) else 'failed'
                await self.db.update_batch_status(
                    batch_id=batch_record['id'],
                    status=batch_status,
                    completed_at=datetime.now()
                )

            successful = sum(1 for r in execution_results if r.success)
            logger.info(f"Batch {batch_number} complete: {successful}/{len(execution_results)} tasks successful")

            return execution_results

        except Exception as e:
            logger.error(f"Batch {batch_number} execution failed: {e}", exc_info=True)
            return []

    async def _execute_task_with_semaphore(self, task: dict, worktree_path: str) -> ExecutionResult:
        """
        Execute a single task respecting the concurrency semaphore.

        Args:
            task: Task dictionary
            worktree_path: Path to worktree for execution

        Returns:
            ExecutionResult
        """
        async with self.semaphore:
            return await self.run_task_agent(task, worktree_path)

    async def run_task_agent(self, task: dict, worktree_path: str) -> ExecutionResult:
        """
        Run agent for a single task in isolated worktree.

        Args:
            task: Task dictionary with details
            worktree_path: Path to worktree for execution

        Returns:
            ExecutionResult
        """
        task_id = task.get('id', 0)
        start_time = time.time()

        logger.info(f"Starting agent for task {task_id}")

        try:
            # Load relevant expertise for task domain
            task_description = task.get('description', '')
            task_action = task.get('action', '')
            file_paths = []  # Could be extracted from task action

            # Classify domain and get expertise
            domain = self.expertise_manager.classify_domain(task_description, file_paths)
            expertise = await self.expertise_manager.get_expertise(domain)
            logger.info(f"Task {task_id} classified as domain '{domain}'")

            # Select optimal model using ModelSelector
            # For now, use default sonnet since ModelSelector needs config
            # This will be properly implemented when Config is available
            if self.model_selector:
                recommendation = self.model_selector.recommend_model(task)
                model = recommendation.model
                logger.info(f"Model selected for task {task_id}: {model} ({recommendation.reasoning})")
            else:
                model = "sonnet"
                logger.info(f"Using default model '{model}' for task {task_id} (selector not initialized)")

            # Build context-rich prompt with task details
            prompt = self._build_task_prompt(task, expertise)

            # Create session record in database
            session_id = None
            if self.db:
                # Get project UUID
                if isinstance(self.project_id, str):
                    project_uuid = UUID(self.project_id)
                else:
                    project_uuid = self.project_id

                # Get next session number
                # For now, use timestamp-based approach
                session_number = int(time.time())

                session = await self.db.create_session(
                    project_id=project_uuid,
                    session_number=session_number,
                    session_type='coding',
                    model=model
                )
                session_id = session['id']
                logger.info(f"Created session {session_id} for task {task_id}")

                # Mark session as started
                await self.db.start_session(session_id)

            # Track running agent in RunningAgent registry
            running_agent = RunningAgent(
                task_id=task_id,
                epic_id=task.get('epic_id', 0),
                process=None,  # Will be set when actual process starts
                started_at=start_time
            )
            self.running_agents.append(running_agent)

            # Execute agent and capture result
            # This will call _execute_agent_session in Task 890
            execution_result = await self._execute_agent_session(
                task=task,
                prompt=prompt,
                model=model,
                worktree_path=worktree_path
            )

            # Remove from running agents
            self.running_agents = [a for a in self.running_agents if a.task_id != task_id]

            # Update task status based on result
            if self.db and execution_result.success:
                await self.db.update_task_status(
                    task_id=task_id,
                    project_id=project_uuid,
                    done=True
                )
                logger.info(f"Task {task_id} marked as complete")

            # Record cost information
            if self.db and session_id:
                # End session with results
                duration = time.time() - start_time
                status = 'completed' if execution_result.success else 'error'
                error_msg = execution_result.error if not execution_result.success else None

                await self.db.end_session(
                    session_id=session_id,
                    status=status,
                    error_message=error_msg,
                    metrics={'duration': duration, 'cost': execution_result.cost}
                )

                # TODO: Record cost in agent_costs table
                # This will be implemented when we have actual token counts

            # Call ExpertiseManager.learn_from_session()
            # This will extract learnings from the session logs
            if self.db and session_id and execution_result.success:
                # Get session logs (would need to implement log capture)
                logs = ""  # Placeholder - will capture actual logs in Task 890
                await self.expertise_manager.learn_from_session(
                    session_id=session_id,
                    task=task,
                    logs=logs
                )

            return execution_result

        except Exception as e:
            logger.error(f"Task {task_id} execution failed: {e}", exc_info=True)

            # Remove from running agents
            self.running_agents = [a for a in self.running_agents if a.task_id != task_id]

            # End session with error
            if self.db and session_id:
                await self.db.end_session(
                    session_id=session_id,
                    status='error',
                    error_message=str(e)
                )

            duration = time.time() - start_time
            return ExecutionResult(
                task_id=task_id,
                success=False,
                duration=duration,
                error=str(e)
            )

    def _build_task_prompt(self, task: dict, expertise: Optional[dict]) -> str:
        """
        Build context-rich prompt for task execution.

        Args:
            task: Task dictionary
            expertise: Expertise dictionary for domain

        Returns:
            Formatted prompt string
        """
        # This is a basic implementation - will be enhanced in Task 891
        prompt = f"""# Task: {task.get('description', 'Unknown')}

## Instructions
{task.get('action', 'No action specified')}

## Context
- Epic: {task.get('epic_name', 'Unknown')}
- Priority: {task.get('priority', 0)}
"""

        if expertise:
            prompt += f"\n## Domain Expertise\n{expertise}\n"

        prompt += """
## Requirements
- Follow coding guidelines and best practices
- Write tests for new functionality
- Update documentation as needed
- Commit changes with clear messages
"""

        return prompt

    async def _execute_agent_session(
        self,
        task: dict,
        prompt: str,
        model: str,
        worktree_path: str
    ) -> ExecutionResult:
        """
        Execute agent session with Claude SDK.

        This is a stub that will be implemented in Task 890.

        Args:
            task: Task dictionary
            prompt: Formatted prompt
            model: Model to use
            worktree_path: Path to worktree

        Returns:
            ExecutionResult
        """
        # Stub - will be implemented in Epic 93, Task 890
        logger.warning(f"Agent execution stub called for task {task.get('id')}")

        # Simulate successful execution for testing
        await asyncio.sleep(0.1)

        return ExecutionResult(
            task_id=task.get('id', 0),
            success=True,
            duration=0.1,
            cost=0.01,
            error=None
        )

    async def cancel(self) -> None:
        """
        Cancel all running agents gracefully.
        """
        # Stub - will be implemented in Epic 93
        logger.warning("ParallelExecutor.cancel() not yet implemented")

    def get_status(self) -> dict:
        """
        Get current execution status.

        Returns:
            Dict with running agents, progress, etc.
        """
        # Stub - will be implemented in Epic 93
        return {
            'running_agents': [],
            'active_agent_count': 0,
            'current_batch': 0,
            'total_duration': 0.0
        }
