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

        # Track execution state
        self.execution_start_time: Optional[float] = None
        self.current_batch_number: int = 0

        # Periodic status updates task
        self.status_update_task: Optional[asyncio.Task] = None

        logger.info(f"ParallelExecutor initialized (max_concurrency={max_concurrency})")

    async def execute(self) -> List[ExecutionResult]:
        """
        Execute all incomplete tasks in parallel batches.

        Returns:
            List of ExecutionResult objects for all tasks
        """
        logger.info("Starting parallel execution")
        all_results = []

        # Track execution start time
        self.execution_start_time = time.time()

        # Start periodic agent status updates
        if self.progress_callback:
            self.status_update_task = asyncio.create_task(self._emit_agent_status_periodically())
            logger.info("Started periodic agent status updates")

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

                # Update current batch number for status tracking
                self.current_batch_number = batch_number

                logger.info(f"Processing batch {batch_number}/{len(dependency_graph.batches)}")

                # Emit batch_start event
                if self.progress_callback:
                    await self.progress_callback({
                        "type": "batch_start",
                        "batch_number": batch_number,
                        "total_batches": len(dependency_graph.batches),
                        "task_count": len(task_ids),
                        "task_ids": task_ids
                    })

                # Log current status
                status = self.get_status()
                logger.info(
                    f"Status: Batch {status['current_batch']}/{len(dependency_graph.batches)}, "
                    f"{len(task_ids)} tasks, "
                    f"Duration: {status['total_duration']:.1f}s"
                )

                # Execute batch and collect results
                batch_results = await self.execute_batch(batch_number, task_ids)
                all_results.extend(batch_results)

                # Merge successful worktrees after each batch
                # This will be implemented when we have worktree merge logic
                successful = sum(1 for r in batch_results if r.success)
                failed = len(batch_results) - successful
                logger.info(
                    f"Batch {batch_number} complete: {successful}/{len(batch_results)} tasks successful"
                )

                # Emit batch_complete event
                if self.progress_callback:
                    await self.progress_callback({
                        "type": "batch_complete",
                        "batch_number": batch_number,
                        "total_batches": len(dependency_graph.batches),
                        "success_count": successful,
                        "fail_count": failed,
                        "total_cost": sum(r.cost for r in all_results)
                    })

            logger.info(f"Parallel execution complete: {len(all_results)} tasks processed")
            return all_results

        except Exception as e:
            logger.error(f"Parallel execution failed: {e}", exc_info=True)
            return all_results

        finally:
            # Stop periodic agent status updates
            if self.status_update_task:
                self.status_update_task.cancel()
                try:
                    await self.status_update_task
                except asyncio.CancelledError:
                    pass
                logger.info("Stopped periodic agent status updates")

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
        epic_id = task.get('epic_id', 0)
        start_time = time.time()

        logger.info(f"Starting agent for task {task_id}")

        # Emit task_start event
        if self.progress_callback:
            await self.progress_callback({
                "type": "task_start",
                "task_id": task_id,
                "epic_id": epic_id,
                "task_description": task.get('description', ''),
                "started_at": datetime.now().isoformat()
            })

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

            # Emit task_complete event
            duration = time.time() - start_time
            if self.progress_callback:
                await self.progress_callback({
                    "type": "task_complete",
                    "task_id": task_id,
                    "epic_id": epic_id,
                    "success": execution_result.success,
                    "duration": duration,
                    "cost": execution_result.cost,
                    "model": model if 'model' in locals() else 'unknown'
                })

            # Emit cost_update event with cumulative cost
            if self.progress_callback:
                # Get current total cost (sum of all completed tasks)
                total_cost = execution_result.cost
                if self.db:
                    # Could query database for total costs, but for now use simple accumulation
                    pass

                await self.progress_callback({
                    "type": "cost_update",
                    "task_id": task_id,
                    "task_cost": execution_result.cost,
                    "cumulative_cost": total_cost  # Will be properly calculated when integrated
                })

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
        Build context-rich prompt for task execution in parallel worktree.

        Args:
            task: Task dictionary with description, action, epic_name, priority
            expertise: Optional expertise dictionary for domain

        Returns:
            Formatted prompt string with all context needed for autonomous execution
        """
        task_id = task.get('id', 0)
        task_desc = task.get('description', 'Unknown')
        task_action = task.get('action', 'No action specified')
        epic_name = task.get('epic_name', 'Unknown')
        priority = task.get('priority', 0)

        # Build comprehensive prompt with all required elements
        prompt = f"""# Parallel Task Execution: {task_desc}

**Task ID:** {task_id}
**Epic:** {epic_name}
**Priority:** {priority}

## * Task Objective

{task_desc}

## ## Implementation Instructions

{task_action}

## * Worktree Context (IMPORTANT)

You are executing in an **isolated git worktree** for parallel development:

- **Isolation:** Your changes are isolated from other parallel tasks
- **Branch:** This worktree has its own branch for epic {task.get('epic_id', 'unknown')}
- **Merging:** After task completion, changes will be merged back to main
- **Independence:** Work independently - don't worry about conflicts with other tasks
- **Git Operations:** All git commands work normally (add, commit, etc.)

**Key Points:**
- Focus only on this task - other tasks are handled by other agents
- Commit your changes when done (they'll be merged later)
- Test your changes thoroughly before completing
- Don't modify files outside the scope of this task
"""

        # Add domain expertise if available
        if expertise:
            prompt += "\n## Domain Expertise\n\n"

            # Handle expertise as dict with patterns/techniques or as string
            if isinstance(expertise, dict):
                if 'patterns' in expertise and expertise['patterns']:
                    prompt += "**Patterns:**\n"
                    for pattern in expertise['patterns']:
                        prompt += f"- {pattern}\n"
                    prompt += "\n"

                if 'techniques' in expertise and expertise['techniques']:
                    prompt += "**Techniques:**\n"
                    for technique in expertise['techniques']:
                        prompt += f"- {technique}\n"
                    prompt += "\n"

                # Include any other expertise content
                if 'content' in expertise:
                    prompt += f"{expertise['content']}\n\n"
            else:
                # Expertise is a string
                prompt += f"{expertise}\n\n"

        # Extract file paths from action if present (common pattern: "in file.py" or "file: path/to/file.py")
        import re
        file_paths = []

        # Pattern 1: "in `path/to/file.py`"
        file_matches = re.findall(r'`([^`]+\.(?:py|js|ts|jsx|tsx|html|css|json|md))`', task_action)
        file_paths.extend(file_matches)

        # Pattern 2: "file: path/to/file.py"
        file_matches2 = re.findall(r'(?:file|path|in|to):\s*([^\s]+\.(?:py|js|ts|jsx|tsx|html|css|json|md))', task_action, re.IGNORECASE)
        file_paths.extend(file_matches2)

        # Deduplicate
        file_paths = list(set(file_paths))

        if file_paths:
            prompt += "## Files to Modify\n\n"
            for file_path in file_paths:
                prompt += f"- `{file_path}`\n"
            prompt += "\n"

        # Add coding guidelines and verification requirements
        prompt += """## Coding Guidelines

**Code Quality:**
- Follow PEP 8 style guide for Python code
- Use type hints where appropriate
- Add docstrings to all functions and classes
- Keep functions focused and single-purpose
- Handle errors gracefully with proper exception handling

**Testing:**
- Write unit tests for new functionality
- Ensure all tests pass before completing task
- Use meaningful test names and assertions

**Documentation:**
- Update relevant documentation files
- Add inline comments for complex logic
- Keep README files up to date

**Git Commits:**
- Commit changes with clear, descriptive messages
- Use conventional commit format: "feat:", "fix:", "docs:", etc.
- Commit frequently with logical groupings

## * Verification Requirements

**Before marking this task complete, you MUST:**

1. **Code Verification:**
   - Verify code compiles/runs without syntax errors
   - Check that all imports are correct
   - Ensure no linting errors

2. **Functionality Verification:**
   - Test the implemented functionality works as expected
   - Verify edge cases are handled
   - Check error handling works correctly

3. **Integration Verification:**
   - Ensure changes integrate with existing code
   - Verify no regressions in related functionality
   - Check that dependencies are satisfied

4. **Commit Changes:**
   - Stage all relevant changes with `git add`
   - Commit with a clear message describing what was implemented
   - Example: `git commit -m "feat: implement agent session execution with timeout"`

## Task Dependencies

"""

        # Add dependency information if available in task
        if 'dependencies' in task and task['dependencies']:
            prompt += "This task depends on:\n"
            for dep_id in task['dependencies']:
                prompt += f"- Task #{dep_id}\n"
            prompt += "\nAll dependencies have been completed before this task started.\n\n"
        else:
            prompt += "This task has no dependencies - you can implement it independently.\n\n"

        prompt += """## Final Steps

When you complete the task:

1. Verify all requirements above are met
2. Commit your changes with a clear message
3. The task will be automatically validated
4. Your changes will be merged with other completed tasks

Focus on quality over speed. Take time to test thoroughly and write clean, maintainable code.

---

**You are an autonomous agent working on this isolated task. Complete it thoroughly and professionally.**
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

        Args:
            task: Task dictionary
            prompt: Formatted prompt
            model: Model to use
            worktree_path: Path to worktree

        Returns:
            ExecutionResult with success status, duration, cost, and any errors
        """
        task_id = task.get('id', 0)
        start_time = time.time()

        logger.info(f"Executing agent session for task {task_id} in worktree {worktree_path}")

        try:
            # Import client creation function
            from core.client import create_client
            from core.agent import run_agent_session
            from core.observability import create_session_logger
            from pathlib import Path

            # Convert worktree path to Path object
            worktree_dir = Path(worktree_path)

            # Create session logger for this agent session
            # Use task_id as session number for tracking
            session_logger = create_session_logger(
                worktree_dir,
                session_number=task_id,
                session_type='coding',
                model=model
            )

            # Create Claude SDK client pointing to worktree directory
            # Pass project_id for MCP task-manager integration
            client = create_client(
                project_dir=worktree_dir,
                model=model,
                project_id=str(self.project_id)
            )

            logger.info(f"Created Claude SDK client for task {task_id} (model: {model})")

            # Execute agent session with timeout
            # Use asyncio.wait_for to enforce timeout (default: 30 minutes)
            timeout_seconds = 1800  # 30 minutes per task

            try:
                async with client:
                    status, response_text, session_summary = await asyncio.wait_for(
                        run_agent_session(
                            client=client,
                            message=prompt,
                            project_dir=worktree_dir,
                            logger=session_logger,
                            verbose=False  # Quiet mode for parallel execution
                        ),
                        timeout=timeout_seconds
                    )

                # Extract metrics from session summary
                duration = time.time() - start_time
                cost = 0.0

                if session_summary and 'usage' in session_summary:
                    usage = session_summary['usage']
                    cost = usage.get('cost_usd', 0.0)

                    logger.info(
                        f"Task {task_id} session complete: "
                        f"{usage.get('input_tokens', 0)} input tokens, "
                        f"{usage.get('output_tokens', 0)} output tokens, "
                        f"${cost:.4f}"
                    )

                # Determine success based on status
                success = status == 'continue'
                error_msg = None if success else f"Agent session returned status: {status}"

                if not success:
                    logger.warning(f"Task {task_id} agent session unsuccessful: {status}")

                return ExecutionResult(
                    task_id=task_id,
                    success=success,
                    duration=duration,
                    cost=cost,
                    error=error_msg
                )

            except asyncio.TimeoutError:
                duration = time.time() - start_time
                error_msg = f"Agent session timed out after {timeout_seconds}s"
                logger.error(f"Task {task_id}: {error_msg}")

                return ExecutionResult(
                    task_id=task_id,
                    success=False,
                    duration=duration,
                    cost=0.0,
                    error=error_msg
                )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Agent session execution failed: {str(e)}"
            logger.error(f"Task {task_id}: {error_msg}", exc_info=True)

            return ExecutionResult(
                task_id=task_id,
                success=False,
                duration=duration,
                cost=0.0,
                error=error_msg
            )

    async def cancel(self) -> None:
        """
        Cancel all running agents gracefully.

        Sets the cancellation event, which will be checked by:
        1. The main execute() loop (stops processing new batches)
        2. Individual agent sessions via run_agent_session (stops current session)

        Note: Running agents will complete their current operation before stopping.
        This is a graceful shutdown, not a hard kill.
        """
        logger.info("Cancellation requested - setting cancel event")
        self.cancel_event.set()

        # Log current running agents that will be cancelled
        if self.running_agents:
            logger.info(f"Cancelling {len(self.running_agents)} running agents:")
            for agent in self.running_agents:
                duration = time.time() - agent.started_at
                logger.info(
                    f"  - Task {agent.task_id} (Epic {agent.epic_id}) "
                    f"running for {duration:.1f}s"
                )
        else:
            logger.info("No running agents to cancel")

        # Note: We don't forcefully kill processes here. The cancel_event will be
        # checked by the execute() loop and by run_agent_session() via session_manager.
        # This allows agents to clean up gracefully (save logs, finalize sessions, etc.)

    async def _emit_agent_status_periodically(self):
        """
        Periodically emit agent_status events with running agent information.
        Runs every 5 seconds until execution completes.
        """
        try:
            while not self.cancel_event.is_set():
                # Get current status
                status = self.get_status()

                # Emit agent_status event
                if self.progress_callback:
                    await self.progress_callback({
                        "type": "agent_status",
                        "running_agents": status['running_agents'],
                        "active_agent_count": status['active_agent_count'],
                        "current_batch": status['current_batch'],
                        "total_duration": status['total_duration']
                    })

                # Wait 5 seconds before next update
                await asyncio.sleep(5)

        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            logger.debug("Agent status update task cancelled")
        except Exception as e:
            logger.error(f"Error in agent status update task: {e}", exc_info=True)

    def get_status(self) -> dict:
        """
        Get current execution status.

        Returns:
            Dict with:
            - running_agents: List of dicts with task_id, epic_id, duration for each agent
            - active_agent_count: Number of currently running agents
            - current_batch: Current batch number being processed (0 if not started)
            - total_duration: Total execution time in seconds (0.0 if not started)
        """
        # Calculate total duration
        total_duration = 0.0
        if self.execution_start_time is not None:
            total_duration = time.time() - self.execution_start_time

        # Build running agents list with current duration
        running_agents_info = []
        for agent in self.running_agents:
            agent_duration = time.time() - agent.started_at
            running_agents_info.append({
                'task_id': agent.task_id,
                'epic_id': agent.epic_id,
                'duration': agent_duration,
                'started_at': agent.started_at
            })

        return {
            'running_agents': running_agents_info,
            'active_agent_count': len(self.running_agents),
            'current_batch': self.current_batch_number,
            'total_duration': total_duration
        }
