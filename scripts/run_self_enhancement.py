#!/usr/bin/env python3
"""
Run YokeFlow Self-Enhancement

Runs the initialization and/or coding sessions for the self-enhancement project.

Usage:
    python scripts/run_self_enhancement.py --init         # Run initialization only
    python scripts/run_self_enhancement.py --coding       # Run coding sessions only
    python scripts/run_self_enhancement.py --all          # Run init then coding

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


async def run_coding(project_id: UUID, max_sessions: int = None):
    """Run coding sessions."""
    print(f"\n{'='*60}")
    print(f"Running Coding Sessions for {PROJECT_NAME}")
    print(f"Project ID: {project_id}")
    if max_sessions:
        print(f"Max Sessions: {max_sessions}")
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

    try:
        # Run coding sessions with auto-continue
        session_count = 0
        while True:
            session = await orchestrator.start_coding_session(
                project_id=project_id,
                coding_model='sonnet',
                auto_continue=True,
                progress_callback=progress_callback
            )
            session_count += 1
            print(f"\nSession {session_count} complete: {session.status}")

            if session.status in ['completed', 'error']:
                break

            if max_sessions and session_count >= max_sessions:
                print(f"Reached max sessions limit ({max_sessions})")
                break

            print("Continuing to next session...")

        return session

    except Exception as e:
        print(f"\nCoding session failed: {e}")
        raise


async def main():
    parser = argparse.ArgumentParser(description="Run YokeFlow self-enhancement")
    parser.add_argument('--init', action='store_true', help='Run initialization only')
    parser.add_argument('--coding', action='store_true', help='Run coding sessions only')
    parser.add_argument('--all', action='store_true', help='Run init then coding')
    parser.add_argument('--max-sessions', type=int, default=None, help='Max coding sessions')
    args = parser.parse_args()

    if not (args.init or args.coding or args.all):
        parser.print_help()
        print("\nError: Specify --init, --coding, or --all")
        sys.exit(1)

    project_id = await get_project_id()
    print(f"Found project: {project_id}")

    if args.init or args.all:
        await run_initialization(project_id)

    if args.coding or args.all:
        await run_coding(project_id, max_sessions=args.max_sessions)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
