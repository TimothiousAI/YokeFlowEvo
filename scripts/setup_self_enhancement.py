#!/usr/bin/env python3
"""
Setup YokeFlow Self-Enhancement Project

Creates a project in YokeFlow's database that points to the enhancement worktree,
allowing YokeFlow to enhance itself using "enhancement mode".

Usage:
    python scripts/setup_self_enhancement.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from core.database_connection import DatabaseManager
from core.orchestrator import AgentOrchestrator


async def setup_self_enhancement():
    """Create the self-enhancement project pointing to the worktree."""

    project_name = "yokeflow-enhancement"
    worktree_path = Path(__file__).parent.parent / ".worktrees" / "enhancement"
    spec_file = worktree_path / "app_spec.txt"

    # Verify worktree and spec exist
    if not worktree_path.exists():
        print(f"ERROR: Worktree not found at {worktree_path}")
        print("Run: git worktree add .worktrees/enhancement -b enhancement/parallel-execution")
        return None

    if not spec_file.exists():
        print(f"ERROR: app_spec.txt not found at {spec_file}")
        print("Copy yokeflow_enhancement_spec.txt to the worktree as app_spec.txt")
        return None

    print(f"Worktree: {worktree_path}")
    print(f"Spec file: {spec_file}")

    # Read the spec content (for reference)
    spec_content = spec_file.read_text(encoding='utf-8')
    print(f"Spec length: {len(spec_content)} chars")

    async with DatabaseManager() as db:
        # Check if project already exists
        existing = await db.get_project_by_name(project_name)
        if existing:
            print(f"\nProject '{project_name}' already exists (ID: {existing['id']})")
            confirm = input("Delete and recreate? (y/n): ").strip().lower()
            if confirm == 'y':
                await db.delete_project(existing['id'])
                print("Deleted existing project")
            else:
                print("Keeping existing project")
                return existing['id']

    # Create project using orchestrator with enhancement mode (local_path)
    print(f"\nCreating project '{project_name}' in enhancement mode...")
    print(f"  local_path: {worktree_path}")

    orchestrator = AgentOrchestrator(verbose=False)

    project = await orchestrator.create_project(
        project_name=project_name,
        spec_content=spec_content,  # Pass spec content for database storage
        force=False,
        sandbox_type='local',  # Local mode for self-enhancement
        initializer_model='opus',
        coding_model='sonnet',
        local_path=str(worktree_path),  # Enhancement mode: use worktree
    )

    project_id = project['id']
    print(f"Created project with ID: {project_id}")
    print(f"Working directory: {project.get('local_path', 'N/A')}")

    print(f"\n{'='*60}")
    print(f"Project '{project_name}' is ready for self-enhancement!")
    print(f"{'='*60}")
    print(f"\nProject ID: {project_id}")
    print(f"Mode: Enhancement (targeting existing codebase)")
    print(f"Path: {worktree_path}")
    print(f"\nTo run initialization:")
    print(f"  python scripts/run_self_enhancement.py --init")
    print(f"\nOr use the Web UI to start the project")

    return project_id


if __name__ == "__main__":
    project_id = asyncio.run(setup_self_enhancement())
    if project_id:
        print(f"\nSuccess! Project ID: {project_id}")
    else:
        print("\nFailed to create project")
        sys.exit(1)
