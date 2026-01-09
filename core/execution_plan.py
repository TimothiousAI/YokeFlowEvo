"""
Execution Plan Builder
======================

Builds execution plans during Session 0 that determine parallel batches,
predict file conflicts, and pre-assign worktrees for parallel execution.

This module is the foundation for automatic parallel execution in Phase 2.
"""

import re
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from uuid import UUID

from core.parallel.dependency_resolver import DependencyResolver, DependencyGraph

logger = logging.getLogger(__name__)


@dataclass
class FileConflict:
    """
    Represents a predicted file conflict between tasks.

    Attributes:
        task_ids: List of task IDs that may conflict
        predicted_files: Files that might be modified by multiple tasks
        conflict_type: Type of conflict (same_file, same_directory, potential)
    """
    task_ids: List[int]
    predicted_files: List[str]
    conflict_type: str  # "same_file", "same_directory", "potential"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionBatch:
    """
    A batch of tasks that can potentially run in parallel.

    Attributes:
        batch_id: Unique identifier for this batch
        task_ids: List of task IDs in this batch
        can_parallel: Whether tasks in this batch can run in parallel
        depends_on: List of batch IDs that must complete before this batch
        estimated_duration: Estimated duration in seconds (optional)
    """
    batch_id: int
    task_ids: List[int]
    can_parallel: bool = True
    depends_on: List[int] = field(default_factory=list)
    estimated_duration: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionPlan:
    """
    Complete execution plan for a project.

    Attributes:
        project_id: UUID of the project
        created_at: When the plan was created
        batches: List of execution batches
        worktree_assignments: Mapping of task_id to worktree name
        predicted_conflicts: List of detected file conflicts
        metadata: Additional plan metadata
    """
    project_id: UUID
    created_at: datetime
    batches: List[ExecutionBatch]
    worktree_assignments: Dict[int, str]
    predicted_conflicts: List[FileConflict]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "project_id": str(self.project_id),
            "created_at": self.created_at.isoformat(),
            "batches": [b.to_dict() for b in self.batches],
            "worktree_assignments": {str(k): v for k, v in self.worktree_assignments.items()},
            "predicted_conflicts": [c.to_dict() for c in self.predicted_conflicts],
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionPlan":
        """Create ExecutionPlan from dictionary."""
        return cls(
            project_id=UUID(data["project_id"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            batches=[ExecutionBatch(**b) for b in data["batches"]],
            worktree_assignments={int(k): v for k, v in data["worktree_assignments"].items()},
            predicted_conflicts=[FileConflict(**c) for c in data["predicted_conflicts"]],
            metadata=data.get("metadata", {})
        )

    @property
    def total_tasks(self) -> int:
        """Total number of tasks in the plan."""
        return sum(len(b.task_ids) for b in self.batches)

    @property
    def parallel_batches(self) -> int:
        """Number of batches that can run in parallel."""
        return sum(1 for b in self.batches if b.can_parallel)


class ExecutionPlanBuilder:
    """
    Builds execution plans for projects.

    Uses DependencyResolver to compute batches, analyzes tasks for
    file conflicts, and assigns tasks to worktrees.
    """

    # Patterns for detecting file references in task descriptions
    # IMPORTANT: These must be specific to avoid false positives from common words
    # like "Node.js", "React.js", "SQLite", etc.
    FILE_PATTERNS = [
        r'`([a-zA-Z0-9_/\-\.]+\.[a-zA-Z]+)`',  # `path/to/file.ext` (backtick-quoted)
        r'"([a-zA-Z0-9_/\-\.]+/[a-zA-Z0-9_/\-\.]+\.[a-zA-Z]+)"',  # "path/to/file.ext" (must have path separator)
        r"'([a-zA-Z0-9_/\-\.]+/[a-zA-Z0-9_/\-\.]+\.[a-zA-Z]+)'",  # 'path/to/file.ext' (must have path separator)
        r'\b((?:src|lib|server|client|routes|components|services|middleware|migrations|utils|hooks|api|core|web-ui|tests|schema)/[a-zA-Z0-9_/\-\.]+\.[a-zA-Z]+)',  # Explicit path prefixes
        r'\b((?:index|main|app|config|schema|package|tsconfig|vite\.config|setup|init)\.(?:py|ts|tsx|js|jsx|json|yaml|sql))\b',  # Common root files only
    ]

    # Words to exclude from file detection (common false positives)
    FILE_EXCLUSIONS = {
        'node.js', 'react.js', 'vue.js', 'next.js', 'express.js', 'sqlite',
        'postgresql', 'mongodb', 'redis', 'docker', 'kubernetes',
        'typescript', 'javascript', 'python', 'golang', 'rust',
    }

    # Keywords that suggest file modifications
    MODIFICATION_KEYWORDS = [
        'modify', 'update', 'change', 'edit', 'add to', 'extend',
        'create', 'implement', 'write', 'refactor'
    ]

    def __init__(self, db: Any, max_worktrees: int = 4):
        """
        Initialize ExecutionPlanBuilder.

        Args:
            db: Database instance (TaskDatabase)
            max_worktrees: Maximum number of parallel worktrees
        """
        self.db = db
        self.max_worktrees = max_worktrees
        self.resolver = DependencyResolver()
        logger.info(f"ExecutionPlanBuilder initialized (max_worktrees={max_worktrees})")

    async def build_plan(
        self,
        project_id: UUID,
        progress_callback: Optional[callable] = None
    ) -> ExecutionPlan:
        """
        Build complete execution plan for a project.

        Args:
            project_id: UUID of the project
            progress_callback: Optional async callback for progress updates.
                               Called with (step: str, detail: str, progress: float)

        Returns:
            ExecutionPlan with batches, worktree assignments, and conflict analysis
        """
        async def emit_progress(step: str, detail: str, progress: float):
            """Emit progress update if callback provided."""
            if progress_callback:
                try:
                    await progress_callback(step, detail, progress)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")

        logger.info(f"Building execution plan for project {project_id}")
        await emit_progress("starting", "Initializing plan builder...", 0.0)

        # Get all tasks with their dependencies
        await emit_progress("loading_tasks", "Loading tasks from database...", 0.1)
        tasks = await self.db.get_tasks_for_planning(project_id)

        if not tasks:
            logger.info("No tasks found, returning empty plan")
            return ExecutionPlan(
                project_id=project_id,
                created_at=datetime.utcnow(),
                batches=[],
                worktree_assignments={},
                predicted_conflicts=[],
                metadata={"reason": "no_tasks"}
            )

        # Get epics with dependency information for epic-level planning
        await emit_progress("loading_epics", f"Loading epics ({len(tasks)} tasks found)...", 0.2)
        epics = await self.db.get_epics_with_dependencies(project_id)
        epic_map = {e["id"]: e for e in epics}

        # Separate parallel and sequential epics
        parallel_epics = [e for e in epics if e.get('epic_type', 'parallel') == 'parallel']
        sequential_epics = [e for e in epics if e.get('epic_type') == 'sequential']

        logger.info(f"Epic composition: {len(parallel_epics)} parallel, {len(sequential_epics)} sequential")

        # Determine if we should use epic-based or task-based planning
        # Use epic-based planning only if at least one epic has epic_type explicitly set
        has_epic_types = any(e.get('epic_type') is not None for e in epics)
        use_epic_planning = has_epic_types and (len(sequential_epics) > 0 or len(parallel_epics) > 1)

        if not use_epic_planning:
            # Fall back to task-level dependency resolution (backward compatibility)
            logger.info("Using task-level dependency planning (no epic types defined)")
            await emit_progress("resolving_deps", f"Resolving task dependencies...", 0.3)
            return await self._build_plan_task_based(
                project_id, tasks, epics, epic_map, conflicts=None,
                emit_progress=emit_progress
            )

        # Step 1: Sort sequential epics by dependencies (topological order)
        await emit_progress("resolving_deps", f"Resolving epic dependencies...", 0.3)
        sorted_sequential_epics = self._topological_sort_epics(sequential_epics)
        logger.info(f"Epic-level planning: {len(parallel_epics)} parallel epics, "
                   f"{len(sorted_sequential_epics)} sequential epics")

        # Step 2: Assign worktrees FIRST (based on epic boundaries)
        # This must happen before conflict analysis so we can consider worktree isolation
        await emit_progress("assigning_worktrees", f"Assigning worktrees for {len(epics)} epics...", 0.4)
        # Create temporary batch structure for worktree assignment
        temp_batches = [ExecutionBatch(
            batch_id=0,
            task_ids=[t["id"] for t in tasks],
            can_parallel=True,
            depends_on=[]
        )]

        worktree_assignments = await self.assign_worktrees(
            temp_batches, tasks, epic_map
        )

        # Step 3: Analyze file conflicts
        await emit_progress("analyzing_conflicts", "Analyzing potential file conflicts...", 0.5)
        conflicts = await self.analyze_file_conflicts(tasks)
        logger.info(f"File conflict analysis: {len(conflicts)} potential conflicts")

        # Step 4: Create batches based on epic-level dependencies
        await emit_progress("creating_batches", f"Creating execution batches ({len(conflicts)} conflicts detected)...", 0.6)
        execution_batches = []
        batch_counter = 0

        # Create a map of epic_id -> task_ids
        epic_to_tasks: Dict[int, List[int]] = {}
        for task in tasks:
            epic_id = task.get("epic_id")
            if epic_id:
                if epic_id not in epic_to_tasks:
                    epic_to_tasks[epic_id] = []
                epic_to_tasks[epic_id].append(task["id"])

        # Batch 0: All tasks from all parallel epics run together
        if parallel_epics:
            parallel_task_ids = []
            for epic in parallel_epics:
                epic_id = epic["id"]
                if epic_id in epic_to_tasks:
                    parallel_task_ids.extend(epic_to_tasks[epic_id])

            if parallel_task_ids:
                logger.info(f"Batch 0 (parallel epics): {len(parallel_task_ids)} tasks from {len(parallel_epics)} epics")

                # Group tasks by worktree within the parallel batch
                worktree_groups: Dict[str, List[int]] = {}
                for tid in parallel_task_ids:
                    wt = worktree_assignments.get(tid, "worktree-default")
                    if wt not in worktree_groups:
                        worktree_groups[wt] = []
                    worktree_groups[wt].append(tid)

                # If multiple worktrees, split into parallel sub-batches
                if len(worktree_groups) > 1:
                    logger.info(f"  Splitting into {len(worktree_groups)} worktree sub-batches")

                    for wt_name, wt_task_ids in worktree_groups.items():
                        # Tasks within same worktree, can run in parallel with other worktrees
                        execution_batches.append(ExecutionBatch(
                            batch_id=batch_counter,
                            task_ids=list(wt_task_ids),
                            can_parallel=True,
                            depends_on=[]
                        ))
                        logger.info(f"    Sub-batch {batch_counter} ({wt_name}): {len(wt_task_ids)} tasks")
                        batch_counter += 1
                else:
                    # All tasks in one worktree - check for conflicts
                    batch_conflicts = self._find_same_worktree_conflicts(
                        parallel_task_ids, conflicts, worktree_assignments
                    )
                    can_parallel = len(batch_conflicts) == 0 and len(parallel_task_ids) > 1

                    execution_batches.append(ExecutionBatch(
                        batch_id=batch_counter,
                        task_ids=parallel_task_ids,
                        can_parallel=can_parallel,
                        depends_on=[]
                    ))
                    logger.info(f"  Single batch {batch_counter}: {len(parallel_task_ids)} tasks, can_parallel={can_parallel}")
                    batch_counter += 1

        # Subsequent batches: One batch per sequential epic, in dependency order
        parallel_batch_count = batch_counter
        for seq_idx, epic in enumerate(sorted_sequential_epics):
            epic_id = epic["id"]
            epic_name = epic.get("name", f"Epic {epic_id}")
            epic_task_ids = epic_to_tasks.get(epic_id, [])

            if not epic_task_ids:
                logger.info(f"Sequential epic '{epic_name}' has no tasks, skipping")
                continue

            logger.info(f"Batch {batch_counter} (sequential epic '{epic_name}'): {len(epic_task_ids)} tasks")

            # Sequential epics depend on all parallel epics completing
            depends_on = list(range(parallel_batch_count)) if parallel_batch_count > 0 else []

            # Also depend on previous sequential batches based on depends_on_epics
            depends_on_epics = epic.get("depends_on_epics") or []
            for dep_epic_id in depends_on_epics:
                # Find the batch that contains this epic's tasks
                for batch in execution_batches[parallel_batch_count:]:
                    # Check if this batch contains tasks from the dependency epic
                    batch_epic_ids = set()
                    for tid in batch.task_ids:
                        for t in tasks:
                            if t["id"] == tid:
                                batch_epic_ids.add(t.get("epic_id"))
                                break
                    if dep_epic_id in batch_epic_ids:
                        if batch.batch_id not in depends_on:
                            depends_on.append(batch.batch_id)

            # Group by worktree if needed
            worktree_groups: Dict[str, List[int]] = {}
            for tid in epic_task_ids:
                wt = worktree_assignments.get(tid, "worktree-default")
                if wt not in worktree_groups:
                    worktree_groups[wt] = []
                worktree_groups[wt].append(tid)

            if len(worktree_groups) > 1:
                logger.info(f"  Splitting into {len(worktree_groups)} worktree sub-batches")

                for wt_name, wt_task_ids in worktree_groups.items():
                    execution_batches.append(ExecutionBatch(
                        batch_id=batch_counter,
                        task_ids=list(wt_task_ids),
                        can_parallel=False,  # Sequential epic
                        depends_on=depends_on
                    ))
                    logger.info(f"    Sub-batch {batch_counter} ({wt_name}): {len(wt_task_ids)} tasks")
                    batch_counter += 1
            else:
                execution_batches.append(ExecutionBatch(
                    batch_id=batch_counter,
                    task_ids=epic_task_ids,
                    can_parallel=False,  # Sequential epic
                    depends_on=depends_on
                ))
                logger.info(f"  Single batch {batch_counter}: {len(epic_task_ids)} tasks")
                batch_counter += 1

        # Step 5: Update tasks with predicted files
        await emit_progress("predicting_files", "Predicting file modifications...", 0.8)
        await self._update_task_predicted_files(tasks)

        # Build final plan
        await emit_progress("finalizing", f"Finalizing plan ({len(execution_batches)} batches)...", 0.9)
        plan = ExecutionPlan(
            project_id=project_id,
            created_at=datetime.utcnow(),
            batches=execution_batches,
            worktree_assignments=worktree_assignments,
            predicted_conflicts=conflicts,
            metadata={
                "total_tasks": len(tasks),
                "total_epics": len(epics),
                "parallel_epics": len(parallel_epics),
                "sequential_epics": len(sequential_epics),
                "total_batches": len(execution_batches),
                "parallel_batch_count": parallel_batch_count,
                "parallel_possible": sum(1 for b in execution_batches if b.can_parallel),
                "conflicts_detected": len(conflicts),
                "planning_mode": "epic_based"
            }
        )

        logger.info(f"Execution plan built: {plan.total_tasks} tasks in "
                   f"{len(plan.batches)} batches, {plan.parallel_batches} parallel")

        await emit_progress("complete", f"Plan complete: {plan.total_tasks} tasks in {len(plan.batches)} batches", 1.0)
        return plan

    async def analyze_file_conflicts(self, tasks: List[Dict[str, Any]]) -> List[FileConflict]:
        """
        Predict which tasks might modify the same files.

        Analyzes task descriptions for file paths and common modification keywords.

        Args:
            tasks: List of task dictionaries

        Returns:
            List of FileConflict objects
        """
        # Extract predicted files for each task
        task_files: Dict[int, Set[str]] = {}

        for task in tasks:
            task_id = task["id"]
            description = task.get("description", "") or ""
            action = task.get("action", "") or ""
            text = f"{description} {action}".lower()

            files = self._extract_file_references(text)
            if files:
                task_files[task_id] = files
                # Store for later
                task["_predicted_files"] = list(files)

        # Find conflicts (tasks that reference same files)
        conflicts: List[FileConflict] = []
        file_to_tasks: Dict[str, List[int]] = {}

        for task_id, files in task_files.items():
            for file in files:
                if file not in file_to_tasks:
                    file_to_tasks[file] = []
                file_to_tasks[file].append(task_id)

        # Create conflict objects for files with multiple tasks
        processed_pairs: Set[tuple] = set()
        for file, task_ids in file_to_tasks.items():
            if len(task_ids) > 1:
                # Create conflict for this group
                pair = tuple(sorted(task_ids))
                if pair not in processed_pairs:
                    processed_pairs.add(pair)
                    # Find all shared files for this task group
                    shared_files = [
                        f for f, tids in file_to_tasks.items()
                        if set(task_ids).issubset(set(tids)) or set(tids).issubset(set(task_ids))
                    ]
                    conflicts.append(FileConflict(
                        task_ids=list(task_ids),
                        predicted_files=shared_files,
                        conflict_type="same_file"
                    ))

        # Also check for directory-level conflicts
        dir_to_tasks: Dict[str, List[int]] = {}
        for task_id, files in task_files.items():
            for file in files:
                dir_path = "/".join(file.split("/")[:-1]) if "/" in file else ""
                if dir_path:
                    if dir_path not in dir_to_tasks:
                        dir_to_tasks[dir_path] = []
                    if task_id not in dir_to_tasks[dir_path]:
                        dir_to_tasks[dir_path].append(task_id)

        for dir_path, task_ids in dir_to_tasks.items():
            if len(task_ids) > 1:
                pair = tuple(sorted(task_ids))
                if pair not in processed_pairs:
                    # Only add if not already a same_file conflict
                    conflicts.append(FileConflict(
                        task_ids=list(task_ids),
                        predicted_files=[f"{dir_path}/*"],
                        conflict_type="same_directory"
                    ))

        return conflicts

    def _extract_file_references(self, text: str) -> Set[str]:
        """
        Extract file path references from text.

        Uses conservative pattern matching to avoid false positives from
        common technology names (Node.js, React.js, etc.).

        Args:
            text: Text to analyze

        Returns:
            Set of predicted file paths
        """
        files: Set[str] = set()

        for pattern in self.FILE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Normalize path
                file_path = match.strip().lower()

                # Filter out obvious non-files
                if file_path.startswith(('http', 'www', 'git')):
                    continue

                # Filter out common technology names that look like files
                if file_path in self.FILE_EXCLUSIONS:
                    continue

                # Only include if it looks like a real file path
                # (has path separator OR is a known root file pattern)
                has_path_sep = '/' in file_path
                is_root_file = file_path in {
                    'index.js', 'index.ts', 'index.tsx', 'index.py',
                    'main.js', 'main.ts', 'main.py', 'app.js', 'app.ts',
                    'app.py', 'app.jsx', 'app.tsx', 'config.js', 'config.ts',
                    'config.py', 'schema.sql', 'package.json', 'tsconfig.json',
                    'vite.config.js', 'vite.config.ts', 'setup.py', 'init.sql'
                }

                if has_path_sep or is_root_file:
                    files.add(file_path)

        return files

    async def assign_worktrees(
        self,
        batches: List[ExecutionBatch],
        tasks: List[Dict[str, Any]],
        epic_map: Dict[int, Dict[str, Any]]
    ) -> Dict[int, str]:
        """
        Pre-assign tasks to worktrees based on epic boundaries.

        Each epic gets its own worktree up to max_worktrees.
        Tasks from same epic share a worktree.

        Args:
            batches: List of execution batches
            tasks: List of task dictionaries
            epic_map: Mapping of epic_id to epic data

        Returns:
            Dictionary mapping task_id to worktree name
        """
        assignments: Dict[int, str] = {}
        task_map = {t["id"]: t for t in tasks}

        # Group tasks by epic
        epic_tasks: Dict[int, List[int]] = {}
        for task in tasks:
            epic_id = task.get("epic_id")
            if epic_id:
                if epic_id not in epic_tasks:
                    epic_tasks[epic_id] = []
                epic_tasks[epic_id].append(task["id"])

        # Sort epics by task count (larger epics get dedicated worktrees)
        sorted_epics = sorted(
            epic_tasks.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        # Assign worktrees
        worktree_idx = 0
        epic_to_worktree: Dict[int, str] = {}

        for epic_id, task_ids in sorted_epics:
            if worktree_idx < self.max_worktrees:
                # Dedicated worktree for this epic
                epic_name = epic_map.get(epic_id, {}).get("name", f"epic-{epic_id}")
                # Sanitize name for git branch
                safe_name = re.sub(r'[^a-zA-Z0-9\-]', '-', epic_name.lower())[:30]
                worktree_name = f"worktree-{safe_name}"
                epic_to_worktree[epic_id] = worktree_name
                worktree_idx += 1
            else:
                # Share with smallest existing worktree group
                # For simplicity, use round-robin
                existing_worktrees = list(set(epic_to_worktree.values()))
                worktree_name = existing_worktrees[epic_id % len(existing_worktrees)]
                epic_to_worktree[epic_id] = worktree_name

        # Assign tasks based on their epic
        for epic_id, task_ids in epic_tasks.items():
            worktree = epic_to_worktree.get(epic_id, "worktree-default")
            for task_id in task_ids:
                assignments[task_id] = worktree

        # Handle tasks without epics
        for task in tasks:
            if task["id"] not in assignments:
                assignments[task["id"]] = "worktree-default"

        logger.info(f"Assigned {len(assignments)} tasks to "
                   f"{len(set(assignments.values()))} worktrees")

        return assignments

    def _get_conflicting_task_ids(self, conflicts: List[FileConflict]) -> Set[int]:
        """Get all task IDs involved in any conflict."""
        result: Set[int] = set()
        for conflict in conflicts:
            result.update(conflict.task_ids)
        return result

    async def _build_plan_task_based(
        self,
        project_id: UUID,
        tasks: List[Dict[str, Any]],
        epics: List[Dict[str, Any]],
        epic_map: Dict[int, Dict[str, Any]],
        conflicts: Optional[List[FileConflict]],
        emit_progress: callable
    ) -> ExecutionPlan:
        """
        Build execution plan using task-level dependency resolution (legacy mode).

        This is the original implementation that respects task dependencies.
        Used when epic-level types are not defined.
        """
        # Resolve task dependencies to get batches
        graph = self.resolver.resolve(tasks)
        logger.info(f"Task-level dependency resolution: {len(graph.batches)} batches, "
                   f"{len(graph.circular_deps)} circular deps")

        # Assign worktrees
        await emit_progress("assigning_worktrees", f"Assigning worktrees for {len(epics)} epics...", 0.4)
        temp_batches = [ExecutionBatch(
            batch_id=idx,
            task_ids=list(task_ids),
            can_parallel=True,
            depends_on=[idx - 1] if idx > 0 else []
        ) for idx, task_ids in enumerate(graph.batches)]

        worktree_assignments = await self.assign_worktrees(
            temp_batches, tasks, epic_map
        )

        # Analyze file conflicts
        await emit_progress("analyzing_conflicts", "Analyzing potential file conflicts...", 0.5)
        if conflicts is None:
            conflicts = await self.analyze_file_conflicts(tasks)
        logger.info(f"File conflict analysis: {len(conflicts)} potential conflicts")

        # Convert batches and handle conflicts
        await emit_progress("creating_batches", f"Creating execution batches ({len(conflicts)} conflicts detected)...", 0.6)
        execution_batches = []
        batch_counter = 0

        for orig_batch_idx, task_ids in enumerate(graph.batches):
            # Group tasks by worktree
            worktree_groups: Dict[str, List[int]] = {}
            for tid in task_ids:
                wt = worktree_assignments.get(tid, "worktree-default")
                if wt not in worktree_groups:
                    worktree_groups[wt] = []
                worktree_groups[wt].append(tid)

            # If multiple worktrees, split into parallel sub-batches
            if len(worktree_groups) > 1:
                logger.info(f"Splitting batch {orig_batch_idx} into {len(worktree_groups)} worktree-parallel sub-batches")

                for wt_name, wt_task_ids in worktree_groups.items():
                    wt_conflicts = self._find_same_worktree_conflicts(
                        wt_task_ids, conflicts, worktree_assignments
                    )
                    can_parallel = True

                    execution_batches.append(ExecutionBatch(
                        batch_id=batch_counter,
                        task_ids=list(wt_task_ids),
                        can_parallel=can_parallel,
                        depends_on=[orig_batch_idx - 1] if orig_batch_idx > 0 else []
                    ))
                    logger.info(f"  Sub-batch {batch_counter} ({wt_name}): {len(wt_task_ids)} tasks")
                    batch_counter += 1
            else:
                # Single worktree batch
                batch_conflicts = self._find_same_worktree_conflicts(
                    task_ids, conflicts, worktree_assignments
                )
                can_parallel = len(batch_conflicts) == 0 and len(task_ids) > 1

                execution_batches.append(ExecutionBatch(
                    batch_id=batch_counter,
                    task_ids=list(task_ids),
                    can_parallel=can_parallel,
                    depends_on=[batch_counter - 1] if batch_counter > 0 else []
                ))
                batch_counter += 1

        # Update tasks with predicted files
        await emit_progress("predicting_files", "Predicting file modifications...", 0.8)
        await self._update_task_predicted_files(tasks)

        # Build final plan
        await emit_progress("finalizing", f"Finalizing plan ({len(execution_batches)} batches)...", 0.9)
        plan = ExecutionPlan(
            project_id=project_id,
            created_at=datetime.utcnow(),
            batches=execution_batches,
            worktree_assignments=worktree_assignments,
            predicted_conflicts=conflicts,
            metadata={
                "total_tasks": len(tasks),
                "total_batches": len(execution_batches),
                "parallel_possible": sum(1 for b in execution_batches if b.can_parallel),
                "conflicts_detected": len(conflicts),
                "circular_dependencies": len(graph.circular_deps),
                "missing_dependencies": len(graph.missing_deps),
                "planning_mode": "task_based"
            }
        )

        logger.info(f"Execution plan built: {plan.total_tasks} tasks in "
                   f"{len(plan.batches)} batches, {plan.parallel_batches} parallel")

        await emit_progress("complete", f"Plan complete: {plan.total_tasks} tasks in {len(plan.batches)} batches", 1.0)
        return plan

    def _topological_sort_epics(self, epics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort sequential epics in topological order based on depends_on_epics.

        Args:
            epics: List of sequential epic records

        Returns:
            List of epics sorted so dependencies come before dependents
        """
        if not epics:
            return []

        # Build dependency graph
        epic_map = {e["id"]: e for e in epics}
        in_degree = {e["id"]: 0 for e in epics}
        adj_list = {e["id"]: [] for e in epics}

        for epic in epics:
            depends_on = epic.get("depends_on_epics") or []
            for dep_id in depends_on:
                if dep_id in epic_map:
                    # dep_id -> epic["id"] edge
                    adj_list[dep_id].append(epic["id"])
                    in_degree[epic["id"]] += 1

        # Kahn's algorithm for topological sort
        queue = [eid for eid in in_degree if in_degree[eid] == 0]
        sorted_epic_ids = []

        while queue:
            # Sort by priority to maintain deterministic ordering
            queue.sort(key=lambda eid: epic_map[eid].get("priority", 999))
            current_id = queue.pop(0)
            sorted_epic_ids.append(current_id)

            for neighbor_id in adj_list[current_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)

        # Check for circular dependencies - raise exception instead of silently continuing
        if len(sorted_epic_ids) != len(epics):
            remaining = [e for e in epics if e["id"] not in sorted_epic_ids]
            cycle_names = [e.get("name", f"Epic {e['id']}") for e in remaining]
            raise ValueError(
                f"Circular dependency detected in sequential epics: {', '.join(cycle_names)}. "
                f"Check depends_on_epics configuration."
            )

        # Return epics in sorted order
        return [epic_map[eid] for eid in sorted_epic_ids]

    def _find_batch_conflicts(
        self,
        task_ids: List[int],
        conflicts: List[FileConflict]
    ) -> List[FileConflict]:
        """Find conflicts where all involved tasks are in the same batch."""
        task_set = set(task_ids)
        batch_conflicts = []

        for conflict in conflicts:
            # Check if all conflicting tasks are in this batch
            if set(conflict.task_ids).issubset(task_set):
                batch_conflicts.append(conflict)

        return batch_conflicts

    def _find_same_worktree_conflicts(
        self,
        task_ids: List[int],
        conflicts: List[FileConflict],
        worktree_assignments: Dict[int, str]
    ) -> List[FileConflict]:
        """
        Find conflicts where all involved tasks are in the same batch AND same worktree.

        Tasks in different worktrees can safely have file conflicts because each
        worktree is isolated (separate git branch/directory).

        Args:
            task_ids: Task IDs in the batch
            conflicts: List of all file conflicts
            worktree_assignments: Mapping of task_id to worktree name

        Returns:
            List of conflicts that actually matter (same worktree)
        """
        task_set = set(task_ids)
        same_worktree_conflicts = []

        for conflict in conflicts:
            # Check if all conflicting tasks are in this batch
            if not set(conflict.task_ids).issubset(task_set):
                continue

            # Check if conflicting tasks are in the SAME worktree
            worktrees_involved = set()
            for tid in conflict.task_ids:
                wt = worktree_assignments.get(tid, "worktree-default")
                worktrees_involved.add(wt)

            # Only a real conflict if all tasks are in the same worktree
            if len(worktrees_involved) == 1:
                same_worktree_conflicts.append(conflict)

        return same_worktree_conflicts

    async def _update_task_predicted_files(self, tasks: List[Dict[str, Any]]) -> None:
        """Update tasks in database with predicted files."""
        for task in tasks:
            predicted_files = task.get("_predicted_files", [])
            if predicted_files:
                try:
                    await self.db.update_task_predicted_files(
                        task["id"],
                        predicted_files
                    )
                except Exception as e:
                    logger.warning(f"Failed to update predicted files for task {task['id']}: {e}")

    async def validate_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """
        Validate an execution plan for issues.

        Args:
            plan: ExecutionPlan to validate

        Returns:
            Validation result with any issues found
        """
        issues = []

        # Check for empty batches
        for batch in plan.batches:
            if not batch.task_ids:
                issues.append({
                    "type": "empty_batch",
                    "batch_id": batch.batch_id,
                    "message": "Batch has no tasks"
                })

        # Check worktree assignments
        unassigned = [
            tid for batch in plan.batches
            for tid in batch.task_ids
            if tid not in plan.worktree_assignments
        ]
        if unassigned:
            issues.append({
                "type": "unassigned_tasks",
                "task_ids": unassigned,
                "message": f"{len(unassigned)} tasks not assigned to worktrees"
            })

        # Check for high conflict rate
        if plan.total_tasks > 0:
            conflict_rate = len(plan.predicted_conflicts) / plan.total_tasks
            if conflict_rate > 0.5:
                issues.append({
                    "type": "high_conflict_rate",
                    "rate": conflict_rate,
                    "message": f"High conflict rate ({conflict_rate:.1%}), parallel efficiency may be low"
                })

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": len([i for i in issues if i["type"] == "high_conflict_rate"])
        }
