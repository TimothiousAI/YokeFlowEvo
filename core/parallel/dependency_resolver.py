"""
Dependency Resolver
===================

Analyzes task dependencies and computes parallel execution batches using
topological sorting (Kahn's algorithm).

Key Features:
- Resolves task-level and epic-level dependencies
- Detects circular dependencies
- Supports hard (blocking) and soft (non-blocking) dependencies
- Applies priority ordering within each batch
- Generates visualization (Mermaid, ASCII) for dependency graphs
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class DependencyGraph:
    """
    Result of dependency resolution.

    Attributes:
        batches: List of task ID batches that can execute in parallel
        task_order: Flattened list of all tasks in execution order
        circular_deps: List of detected circular dependency cycles
        missing_deps: List of task IDs that have invalid dependency references
    """
    batches: List[List[int]]
    task_order: List[int]
    circular_deps: List[Tuple]
    missing_deps: List[int]


class DependencyResolver:
    """
    Resolves task dependencies and computes parallel execution batches.

    Uses Kahn's algorithm for topological sorting to determine which tasks
    can run in parallel while respecting dependency constraints.
    """

    def __init__(self, db_connection: Any = None):
        """
        Initialize dependency resolver.

        Args:
            db_connection: Optional database connection for querying tasks
        """
        self.db = db_connection
        self.last_graph: DependencyGraph | None = None
        self.last_tasks: Dict[int, Dict[str, Any]] = {}
        self.last_adjacency: Dict[int, List[int]] = {}
        logger.info("DependencyResolver initialized")

    def resolve(self, tasks: List[Dict[str, Any]]) -> DependencyGraph:
        """
        Resolve dependencies and compute parallel batches using Kahn's algorithm.

        Args:
            tasks: List of task dictionaries with id, depends_on, priority fields

        Returns:
            DependencyGraph with computed batches and metadata
        """
        if not tasks:
            logger.info("No tasks provided, returning empty graph")
            return DependencyGraph(
                batches=[],
                task_order=[],
                circular_deps=[],
                missing_deps=[]
            )

        # Build task ID set and dependency mapping
        task_ids = {task['id'] for task in tasks}
        task_map = {task['id']: task for task in tasks}

        # Track missing dependencies
        missing_deps = []

        # Build adjacency list and in-degree count for Kahn's algorithm
        # adjacency[task_id] = [list of tasks that depend on task_id]
        adjacency: Dict[int, List[int]] = {tid: [] for tid in task_ids}
        in_degree: Dict[int, int] = {tid: 0 for tid in task_ids}

        # Parse dependencies
        for task in tasks:
            task_id = task['id']
            depends_on = task.get('depends_on', []) or []
            dependency_type = task.get('dependency_type', 'hard')

            # Only process hard dependencies for topological sort
            # Soft dependencies are tracked but don't block execution
            if dependency_type == 'hard':
                for dep_id in depends_on:
                    if dep_id not in task_ids:
                        # Invalid dependency reference
                        if task_id not in missing_deps:
                            missing_deps.append(task_id)
                        logger.warning(f"Task {task_id} has invalid dependency: {dep_id}")
                    else:
                        # Add edge: dep_id -> task_id
                        adjacency[dep_id].append(task_id)
                        in_degree[task_id] += 1

        # Kahn's algorithm for topological sorting
        batches = []
        task_order = []
        queue = []

        # Start with tasks that have no dependencies (in-degree = 0)
        for task_id in task_ids:
            if in_degree[task_id] == 0:
                queue.append(task_id)

        # Sort initial queue by priority (lower number = higher priority)
        queue.sort(key=lambda tid: task_map[tid].get('priority', 999))

        while queue:
            # Current batch: all tasks with no remaining dependencies
            current_batch = queue[:]
            batches.append(current_batch)
            task_order.extend(current_batch)

            # Process current batch
            next_queue = []
            for task_id in current_batch:
                # For each task that depends on this one
                for dependent_id in adjacency[task_id]:
                    in_degree[dependent_id] -= 1
                    # If all dependencies satisfied, add to next batch
                    if in_degree[dependent_id] == 0:
                        next_queue.append(dependent_id)

            # Sort next queue by priority
            next_queue.sort(key=lambda tid: task_map[tid].get('priority', 999))
            queue = next_queue

        # Detect circular dependencies
        circular_deps = []
        remaining_tasks = [tid for tid in task_ids if in_degree[tid] > 0]

        if remaining_tasks:
            logger.warning(f"Circular dependencies detected: {remaining_tasks}")
            # Find cycles using DFS
            circular_deps = self._detect_cycles(remaining_tasks, task_map)

        logger.info(f"Resolved {len(tasks)} tasks into {len(batches)} parallel batches")
        logger.info(f"Batch sizes: {[len(b) for b in batches]}")

        # Store for visualization
        graph = DependencyGraph(
            batches=batches,
            task_order=task_order,
            circular_deps=circular_deps,
            missing_deps=missing_deps
        )
        self.last_graph = graph
        self.last_tasks = task_map
        self.last_adjacency = adjacency

        return graph

    def _detect_cycles(self, remaining_tasks: List[int], task_map: Dict[int, Dict[str, Any]]) -> List[Tuple]:
        """
        Detect circular dependency cycles using DFS.

        Args:
            remaining_tasks: Tasks that weren't processed (likely in cycles)
            task_map: Mapping of task ID to task data

        Returns:
            List of tuples representing circular dependency cycles
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(task_id: int, path: List[int]) -> bool:
            """DFS helper to find cycles"""
            visited.add(task_id)
            rec_stack.add(task_id)
            path.append(task_id)

            # Check dependencies
            depends_on = task_map.get(task_id, {}).get('depends_on', []) or []
            for dep_id in depends_on:
                if dep_id not in task_map:
                    continue

                if dep_id not in visited:
                    if dfs(dep_id, path):
                        return True
                elif dep_id in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(dep_id)
                    cycle = tuple(path[cycle_start:] + [dep_id])
                    if cycle not in cycles:
                        cycles.append(cycle)
                    return True

            path.pop()
            rec_stack.remove(task_id)
            return False

        # Run DFS from each unvisited task
        for task_id in remaining_tasks:
            if task_id not in visited:
                dfs(task_id, [])

        return cycles

    def to_mermaid(self, epic_filter: int | None = None, batch_filter: int | None = None) -> str:
        """
        Generate Mermaid flowchart diagram of dependencies.

        Args:
            epic_filter: Optional epic ID to filter tasks by
            batch_filter: Optional batch number to filter tasks by

        Returns:
            Mermaid diagram string
        """
        if not self.last_graph or not self.last_tasks:
            return "graph TD\n  Empty[No dependency graph available]"

        lines = ["graph TD"]

        # Filter tasks if needed
        tasks_to_show = set(self.last_tasks.keys())
        if epic_filter is not None:
            tasks_to_show = {tid for tid, task in self.last_tasks.items()
                           if task.get('epic_id') == epic_filter}
        if batch_filter is not None and batch_filter < len(self.last_graph.batches):
            tasks_to_show = set(self.last_graph.batches[batch_filter])

        # Add nodes with labels
        for task_id in tasks_to_show:
            task = self.last_tasks[task_id]
            task_name = task.get('description', f'Task {task_id}')
            # Sanitize for Mermaid
            task_name = task_name.replace('"', "'").replace('[', '(').replace(']', ')')
            if len(task_name) > 40:
                task_name = task_name[:37] + "..."

            # Find which batch this task is in
            batch_num = None
            for i, batch in enumerate(self.last_graph.batches):
                if task_id in batch:
                    batch_num = i
                    break

            if batch_num is not None:
                lines.append(f'  T{task_id}["#{task_id}: {task_name}<br/>Batch {batch_num}"]')
            else:
                lines.append(f'  T{task_id}["#{task_id}: {task_name}"]')

        # Add edges (dependencies)
        for task_id in tasks_to_show:
            if task_id in self.last_adjacency:
                for dependent_id in self.last_adjacency[task_id]:
                    if dependent_id in tasks_to_show:
                        lines.append(f'  T{task_id} --> T{dependent_id}')

        # Highlight circular dependencies
        if self.last_graph.circular_deps:
            lines.append('')
            lines.append('  %% Circular dependencies detected')
            for cycle in self.last_graph.circular_deps:
                if any(tid in tasks_to_show for tid in cycle):
                    lines.append(f'  %% Cycle: {" -> ".join(str(t) for t in cycle)}')

        return '\n'.join(lines)

    def to_ascii(self, epic_filter: int | None = None, batch_filter: int | None = None) -> str:
        """
        Generate ASCII text representation of dependencies.

        Args:
            epic_filter: Optional epic ID to filter tasks by
            batch_filter: Optional batch number to filter tasks by

        Returns:
            ASCII diagram string
        """
        if not self.last_graph or not self.last_tasks:
            return "No dependency graph available"

        lines = []
        lines.append("=" * 70)
        lines.append("DEPENDENCY GRAPH")
        lines.append("=" * 70)

        # Filter tasks if needed
        batches_to_show = self.last_graph.batches
        if epic_filter is not None:
            batches_to_show = []
            for batch in self.last_graph.batches:
                filtered_batch = [tid for tid in batch
                                if self.last_tasks[tid].get('epic_id') == epic_filter]
                if filtered_batch:
                    batches_to_show.append(filtered_batch)
        if batch_filter is not None and batch_filter < len(self.last_graph.batches):
            batches_to_show = [self.last_graph.batches[batch_filter]]

        # Display batches
        for batch_num, batch in enumerate(batches_to_show):
            lines.append(f"\nBATCH {batch_num} (can run in parallel):")
            lines.append("-" * 70)

            for task_id in batch:
                task = self.last_tasks[task_id]
                task_name = task.get('description', f'Task {task_id}')
                priority = task.get('priority', 'N/A')

                # Get dependencies
                depends_on = task.get('depends_on', []) or []
                dep_type = task.get('dependency_type', 'hard')

                lines.append(f"  [{task_id}] {task_name}")
                lines.append(f"      Priority: {priority}")

                if depends_on:
                    dep_str = ', '.join(str(d) for d in depends_on)
                    lines.append(f"      Depends on: {dep_str} ({dep_type})")
                else:
                    lines.append(f"      Depends on: None")

        # Show circular dependencies if any
        if self.last_graph.circular_deps:
            lines.append("\n" + "!" * 70)
            lines.append("CIRCULAR DEPENDENCIES DETECTED:")
            lines.append("!" * 70)
            for cycle in self.last_graph.circular_deps:
                cycle_str = ' -> '.join(str(t) for t in cycle)
                lines.append(f"  {cycle_str}")

        # Show missing dependencies if any
        if self.last_graph.missing_deps:
            lines.append("\n" + "!" * 70)
            lines.append("MISSING/INVALID DEPENDENCIES:")
            lines.append("!" * 70)
            for task_id in self.last_graph.missing_deps:
                task = self.last_tasks.get(task_id, {})
                task_name = task.get('description', f'Task {task_id}')
                lines.append(f"  [{task_id}] {task_name}")

        lines.append("\n" + "=" * 70)
        lines.append(f"Total: {len(self.last_tasks)} tasks in {len(batches_to_show)} batches")
        lines.append("=" * 70)

        return '\n'.join(lines)

    def get_critical_path(self) -> List[int]:
        """
        Identify longest dependency chain (critical path).

        Uses dynamic programming to find the longest path in the DAG.

        Returns:
            List of task IDs in critical path (longest dependency chain)
        """
        if not self.last_graph or not self.last_tasks:
            return []

        if not self.last_graph.task_order:
            # No tasks or circular dependencies
            return []

        # Use dynamic programming to find longest path
        # dp[task_id] = (length, previous_task_id)
        dp: Dict[int, tuple[int, int | None]] = {}

        # Process tasks in topological order (reverse to go from leaves to roots)
        for task_id in reversed(self.last_graph.task_order):
            max_length = 0
            best_next = None

            # Check all tasks that depend on this one
            for dependent_id in self.last_adjacency.get(task_id, []):
                if dependent_id in dp:
                    dependent_length = dp[dependent_id][0]
                    if dependent_length + 1 > max_length:
                        max_length = dependent_length + 1
                        best_next = dependent_id

            dp[task_id] = (max_length, best_next)

        # Find the task with the longest path
        if not dp:
            return []

        start_task = max(dp.items(), key=lambda x: x[1][0])[0]

        # Reconstruct the path
        path = []
        current = start_task
        while current is not None:
            path.append(current)
            current = dp[current][1]

        logger.info(f"Critical path length: {len(path)} tasks")
        return path
