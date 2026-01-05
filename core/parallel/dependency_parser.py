"""
Dependency Parser
=================

Parses and validates task dependencies from various sources:
- Explicit dependencies (depends_on field)
- Inferred dependencies (from task descriptions)
- Validation of dependency references

This module helps automate dependency detection when explicit declarations
are missing, making the parallel execution engine more robust.
"""

from typing import List, Dict, Any, Set
import re
import logging

logger = logging.getLogger(__name__)


def parse_explicit_dependencies(task_json: Dict[str, Any]) -> List[int]:
    """
    Extract explicit dependencies from task data.

    Args:
        task_json: Task dictionary containing optional depends_on field

    Returns:
        List of task IDs that this task depends on
    """
    depends_on = task_json.get('depends_on', [])

    # Handle None or empty values
    if not depends_on:
        return []

    # Ensure it's a list
    if not isinstance(depends_on, list):
        logger.warning(f"Task {task_json.get('id')} has invalid depends_on format: {depends_on}")
        return []

    # Filter out non-integer values
    result = []
    for dep_id in depends_on:
        try:
            result.append(int(dep_id))
        except (ValueError, TypeError):
            logger.warning(f"Task {task_json.get('id')} has invalid dependency ID: {dep_id}")

    logger.debug(f"Task {task_json.get('id')} has explicit dependencies: {result}")
    return result


def infer_dependencies(
    task_description: str,
    task_action: str,
    all_tasks: List[Dict[str, Any]],
    exclude_task_id: int | None = None
) -> List[int]:
    """
    Infer dependencies from task description and action text using keyword heuristics.

    Looks for patterns like:
    - "requires Task 5"
    - "depends on task 3"
    - "after completing task 7"
    - "uses output from task 2"
    - "needs task 4 to be done"

    Args:
        task_description: Short task description
        task_action: Detailed action/implementation instructions
        all_tasks: List of all tasks to search for references
        exclude_task_id: Optional task ID to exclude (e.g., the current task itself)

    Returns:
        List of inferred task IDs
    """
    inferred = set()

    # Combine description and action for search
    full_text = f"{task_description} {task_action}".lower()

    # Keyword patterns that indicate dependencies
    dependency_keywords = [
        r'requires?\s+task\s+(\d+)',
        r'depends?\s+on\s+task\s+(\d+)',
        r'after\s+(?:completing\s+)?task\s+(\d+)',
        r'uses?\s+(?:output\s+from\s+)?task\s+(\d+)',
        r'needs?\s+task\s+(\d+)',
        r'building\s+on\s+task\s+(\d+)',
        r'based\s+on\s+task\s+(\d+)',
        r'following\s+task\s+(\d+)',
    ]

    # Search for patterns
    for pattern in dependency_keywords:
        matches = re.finditer(pattern, full_text)
        for match in matches:
            task_id = int(match.group(1))
            inferred.add(task_id)

    # Also look for references to task descriptions
    # e.g., "Requires: Database schema" when another task is "Create database schema"
    for other_task in all_tasks:
        other_desc = other_task.get('description', '').lower()
        if not other_desc:
            continue

        # Check if this task's text mentions the other task's description
        if len(other_desc) > 10:  # Only check substantial descriptions
            # Look for patterns like "Requires: [description]" or "Needs [description]"
            requires_pattern = rf'(?:requires?|needs?|depends?\s+on|after|uses?)[:\s]+{re.escape(other_desc[:30])}'
            if re.search(requires_pattern, full_text, re.IGNORECASE):
                inferred.add(other_task['id'])

    # Remove self-reference if exclude_task_id is provided
    if exclude_task_id is not None:
        inferred.discard(exclude_task_id)

    if inferred:
        logger.info(f"Inferred dependencies: {inferred}")

    return list(inferred)


def validate_dependencies(
    dependencies: List[int],
    all_task_ids: Set[int]
) -> tuple[List[int], List[int]]:
    """
    Validate dependency references and separate valid from invalid.

    Args:
        dependencies: List of task IDs to validate
        all_task_ids: Set of all valid task IDs in the project

    Returns:
        Tuple of (valid_dependencies, invalid_dependencies)
    """
    valid = []
    invalid = []

    for dep_id in dependencies:
        if dep_id in all_task_ids:
            valid.append(dep_id)
        else:
            invalid.append(dep_id)
            logger.warning(f"Invalid dependency reference: {dep_id}")

    return valid, invalid


def parse_and_validate(
    task: Dict[str, Any],
    all_tasks: List[Dict[str, Any]],
    enable_inference: bool = False
) -> Dict[str, Any]:
    """
    Parse all dependencies (explicit and inferred) and validate them.

    Args:
        task: The task to parse dependencies for
        all_tasks: List of all tasks in the project
        enable_inference: Whether to enable dependency inference (default: False)

    Returns:
        Dictionary with parsed dependency information:
        {
            'explicit': List[int] - Explicitly declared dependencies
            'inferred': List[int] - Inferred dependencies (if enabled)
            'valid': List[int] - All valid dependencies
            'invalid': List[int] - Invalid dependency references
            'all': List[int] - Combined valid dependencies (explicit + inferred)
        }
    """
    task_id = task.get('id')
    all_task_ids = {t['id'] for t in all_tasks if t['id'] != task_id}

    # Parse explicit dependencies
    explicit = parse_explicit_dependencies(task)

    # Parse inferred dependencies (if enabled)
    inferred = []
    if enable_inference:
        task_desc = task.get('description', '')
        task_action = task.get('action', '')
        inferred = infer_dependencies(task_desc, task_action, all_tasks, exclude_task_id=task_id)

    # Combine and deduplicate
    combined = list(set(explicit + inferred))

    # Validate all dependencies
    valid, invalid = validate_dependencies(combined, all_task_ids)

    result = {
        'explicit': explicit,
        'inferred': inferred,
        'valid': valid,
        'invalid': invalid,
        'all': valid  # Only return valid dependencies
    }

    logger.debug(f"Task {task_id} dependencies: {result}")
    return result


def enrich_tasks_with_dependencies(
    tasks: List[Dict[str, Any]],
    enable_inference: bool = False
) -> List[Dict[str, Any]]:
    """
    Enrich all tasks with parsed and validated dependencies.

    This is a convenience function that processes all tasks in bulk
    and updates their depends_on field with valid dependencies.

    Args:
        tasks: List of tasks to enrich
        enable_inference: Whether to enable dependency inference

    Returns:
        List of tasks with enriched dependency information
    """
    enriched_tasks = []

    for task in tasks:
        # Parse dependencies
        dep_info = parse_and_validate(task, tasks, enable_inference)

        # Update task with valid dependencies
        task_copy = task.copy()
        task_copy['depends_on'] = dep_info['all']

        # Add metadata about inference
        if enable_inference and dep_info['inferred']:
            task_copy['_inferred_dependencies'] = dep_info['inferred']

        if dep_info['invalid']:
            task_copy['_invalid_dependencies'] = dep_info['invalid']

        enriched_tasks.append(task_copy)

    logger.info(f"Enriched {len(enriched_tasks)} tasks with dependencies")
    return enriched_tasks
