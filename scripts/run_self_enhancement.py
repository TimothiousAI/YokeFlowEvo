#!/usr/bin/env python3
"""
Run YokeFlow Self-Enhancement

Runs the initialization and/or coding sessions for the self-enhancement project.

Usage:
    # Sequential execution (default)
    python scripts/run_self_enhancement.py --init         # Run initialization only
    python scripts/run_self_enhancement.py --coding       # Run coding sessions only
    python scripts/run_self_enhancement.py --all          # Run init then coding

    # Parallel execution (opt-in)
    python scripts/run_self_enhancement.py --coding --parallel
    python scripts/run_self_enhancement.py --coding --parallel --max-concurrency 5
    python scripts/run_self_enhancement.py --coding --parallel --merge-strategy squash

Options:
    --parallel              Enable parallel execution of tasks
    --max-concurrency N     Number of concurrent agents (1-10, default: 3)
    --merge-strategy TYPE   Worktree merge strategy: 'regular' or 'squash' (default: regular)
    --max-sessions N        Max coding sessions (sequential mode only)

Environment:
    Requires DATABASE_URL and CLAUDE_CODE_OAUTH_TOKEN in .env
"""

import asyncio
import argparse
import sys
from pathlib import Path
from uuid import UUID

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from core.orchestrator import AgentOrchestrator
from core.database_connection import DatabaseManager


PROJECT_NAME = "yokeflow-enhancement"


async def get_project_id() -> UUID:
    """Get the project ID for yokeflow-enhancement."""
    async with DatabaseManager() as db:
        project = await db.get_project_by_name(PROJECT_NAME)
        if not project:
            print(f"ERROR: Project '{PROJECT_NAME}' not found")
            print("Run: python scripts/setup_self_enhancement.py")
            sys.exit(1)
        return project['id']


async def run_initialization(project_id: UUID):
    """Run initialization session (Session 0)."""
    print(f"\n{'='*60}")
    print(f"Running Initialization for {PROJECT_NAME}")
    print(f"Project ID: {project_id}")
    print(f"{'='*60}\n")

    orchestrator = AgentOrchestrator(verbose=True)

    async def progress_callback(event):
        """Handle progress events."""
        event_type = event.get('type', 'unknown')
        if event_type == 'tool_use':
            print(f"  [TOOL] {event.get('tool_name', 'unknown')}")
        elif event_type == 'thinking':
            print(f"  [THINKING] ...")
        elif event_type == 'text':
            text = event.get('text', '')[:100]
            if text:
                print(f"  [TEXT] {text}...")

    try:
        session = await orchestrator.start_initialization(
            project_id=project_id,
            initializer_model='opus',
            progress_callback=progress_callback
        )
        print(f"\nInitialization complete!")
        print(f"Session ID: {session.session_id}")
        print(f"Status: {session.status}")
        return session
    except Exception as e:
        print(f"\nInitialization failed: {e}")
        raise


async def run_coding(
    project_id: UUID,
    max_sessions: int = None,
    parallel: bool = False,
    max_concurrency: int = 3,
    merge_strategy: str = 'regular'
):
    """Run coding sessions.

    Args:
        project_id: Project UUID
        max_sessions: Maximum number of sessions to run
        parallel: Enable parallel execution of tasks
        max_concurrency: Number of concurrent agents (1-10)
        merge_strategy: Worktree merge strategy ('regular' or 'squash')
    """
    print(f"\n{'='*60}")
    print(f"Running Coding Sessions for {PROJECT_NAME}")
    print(f"Project ID: {project_id}")
    if max_sessions:
        print(f"Max Sessions: {max_sessions}")
    if parallel:
        print(f"Parallel Execution: ENABLED")
        print(f"Max Concurrency: {max_concurrency}")
        print(f"Merge Strategy: {merge_strategy}")
    else:
        print(f"Parallel Execution: DISABLED (sequential mode)")
    print(f"{'='*60}\n")

    orchestrator = AgentOrchestrator(verbose=True)

    async def progress_callback(event):
        """Handle progress events."""
        event_type = event.get('type', 'unknown')
        if event_type == 'tool_use':
            print(f"  [TOOL] {event.get('tool_name', 'unknown')}")
        elif event_type == 'session_started':
            print(f"\n>>> Session {event.get('session_number', '?')} started")
        elif event_type == 'session_complete':
            print(f"<<< Session {event.get('session_number', '?')} complete")
        elif event_type == 'batch_started':
            print(f"\n>>> Batch {event.get('batch_number', '?')} started ({event.get('task_count', '?')} tasks)")
        elif event_type == 'batch_complete':
            print(f"<<< Batch {event.get('batch_number', '?')} complete")
        elif event_type == 'task_started':
            print(f"  [TASK] Started: {event.get('task_description', 'unknown')}")
        elif event_type == 'task_complete':
            print(f"  [TASK] Complete: {event.get('task_description', 'unknown')}")

    try:
        if parallel:
            # Run parallel execution
            print("Starting parallel execution...")
            session = await orchestrator.start_coding_sessions(
                project_id=project_id,
                coding_model='sonnet',
                progress_callback=progress_callback,
                parallel=True,
                max_concurrency=max_concurrency
            )
            print(f"\nParallel execution complete: {session.status}")
            return session
        else:
            # Run sequential coding sessions
            session = await orchestrator.start_coding_sessions(
                project_id=project_id,
                coding_model='sonnet',
                max_iterations=max_sessions or 0,  # 0 = unlimited
                progress_callback=progress_callback,
                parallel=False,
            )
            print(f"\nSequential execution complete: {session.status}")
            return session

    except Exception as e:
        print(f"\nCoding session failed: {e}")
        raise


async def main():
    parser = argparse.ArgumentParser(
        description="Run YokeFlow self-enhancement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sequential execution (default)
  python scripts/run_self_enhancement.py --coding

  # Parallel execution with 5 concurrent agents
  python scripts/run_self_enhancement.py --coding --parallel --max-concurrency 5

  # Parallel execution with squash merge strategy
  python scripts/run_self_enhancement.py --coding --parallel --merge-strategy squash

  # Run initialization then parallel coding
  python scripts/run_self_enhancement.py --all --parallel

Note: Parallel execution is opt-in. Use --parallel flag to enable it.
        """
    )
    parser.add_argument('--init', action='store_true', help='Run initialization only')
    parser.add_argument('--coding', action='store_true', help='Run coding sessions only')
    parser.add_argument('--all', action='store_true', help='Run init then coding')
    parser.add_argument('--max-sessions', type=int, default=None, help='Max coding sessions (sequential mode only)')
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Enable parallel execution of tasks (default: sequential)'
    )
    parser.add_argument(
        '--max-concurrency',
        type=int,
        default=3,
        help='Number of concurrent agents (1-10, default: 3)'
    )
    parser.add_argument(
        '--merge-strategy',
        type=str,
        choices=['regular', 'squash'],
        default='regular',
        help='Worktree merge strategy (default: regular)'
    )
    args = parser.parse_args()

    if not (args.init or args.coding or args.all):
        parser.print_help()
        print("\nError: Specify --init, --coding, or --all")
        sys.exit(1)

    # Validate max_concurrency
    if args.max_concurrency < 1 or args.max_concurrency > 10:
        print(f"Error: --max-concurrency must be between 1 and 10 (got {args.max_concurrency})")
        sys.exit(1)

    # Warn if max_sessions is used with parallel mode
    if args.parallel and args.max_sessions:
        print("Warning: --max-sessions is ignored in parallel mode")

    project_id = await get_project_id()
    print(f"Found project: {project_id}")

    if args.init or args.all:
        await run_initialization(project_id)

    if args.coding or args.all:
        await run_coding(
            project_id,
            max_sessions=args.max_sessions,
            parallel=args.parallel,
            max_concurrency=args.max_concurrency,
            merge_strategy=args.merge_strategy
        )

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
