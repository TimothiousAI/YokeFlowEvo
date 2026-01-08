#!/usr/bin/env python3
"""
Rebuild Execution Plan for a Project

This script rebuilds the execution plan for a project that had Session 0
complete successfully but failed to build the execution plan (e.g., due to
Unicode encoding errors).

Usage:
    python scripts/rebuild_execution_plan.py <project_id>
"""

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


async def rebuild_execution_plan(project_id: UUID):
    """Rebuild execution plan for a project."""
    from core.database_connection import DatabaseManager
    from core.orchestrator import AgentOrchestrator

    print(f"Rebuilding execution plan for project: {project_id}")

    async with DatabaseManager() as db:
        # Get project info
        project = await db.get_project(project_id)
        if not project:
            print(f"ERROR: Project {project_id} not found")
            return False

        print(f"Project: {project['name']}")

        # Check if epics and tasks exist
        epics = await db.list_epics(project_id)
        print(f"Epics: {len(epics)}")

        if len(epics) == 0:
            print("ERROR: No epics found. Session 0 may not have completed successfully.")
            return False

        # Count tasks
        total_tasks = 0
        for epic in epics:
            tasks = await db.list_tasks(project_id, epic['id'])
            total_tasks += len(tasks)
        print(f"Total tasks: {total_tasks}")

        # Create orchestrator (we'll call private methods)
        orchestrator = AgentOrchestrator()

        # Get project path for logging
        local_path = project.get('local_path')
        if local_path:
            project_path = Path(local_path)
        else:
            project_path = Path("generations") / project['name'].lower().replace(" ", "-")

        print(f"Project path: {project_path}")

        # Create a minimal session logger for the events (or None)
        session_logger = None

        print("\n--- Building Execution Plan ---")
        await orchestrator._build_execution_plan(project_id, db, session_logger)

        # Check if plan was created by re-fetching project
        project_updated = await db.get_project(project_id)
        meta = project_updated.get('metadata') or {}
        if isinstance(meta, str):
            meta = json.loads(meta)

        if 'execution_plan' in meta:
            plan = meta['execution_plan']
            print(f"Execution plan created:")
            print(f"  Batches: {len(plan.get('batches', []))}")
            print(f"  Total tasks: {sum(len(b.get('task_ids', [])) for b in plan.get('batches', []))}")
            parallel_batches = sum(1 for b in plan.get('batches', []) if b.get('can_parallel'))
            print(f"  Parallel batches: {parallel_batches}")
        else:
            print("WARNING: No execution plan in metadata")

        print("\n--- Selecting Execution Mode ---")
        await orchestrator._select_execution_mode(project_id, db, session_logger)

        # Check the mode
        mode = await db.get_project_execution_mode(project_id)
        print(f"Execution mode set to: {mode}")

        print("\n--- Complete ---")
        print(f"Project {project['name']} execution plan rebuilt successfully")
        print(f"Mode: {mode}")

        return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/rebuild_execution_plan.py <project_id>")
        print("\nExample:")
        print("  python scripts/rebuild_execution_plan.py bdc04632-f314-4180-85e1-8a259fbecb91")
        sys.exit(1)

    project_id = UUID(sys.argv[1])

    success = asyncio.run(rebuild_execution_plan(project_id))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
