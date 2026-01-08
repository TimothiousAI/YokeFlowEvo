#!/usr/bin/env python3
"""
Create epics and tasks for Parallel Execution v2 roadmap.
Run from project root: python scripts/create_parallel_v2_roadmap.py
"""
import asyncio
import os
import sys
from uuid import UUID

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import TaskDatabase

PROJECT_ID = UUID("abb4601b-bb99-43ff-b9a6-d95b2e371d0a")  # yokeflow-enhancement

# Epic definitions with their tasks
ROADMAP = [
    {
        "name": "Phase 1: Execution Plan Engine",
        "description": "Build execution plan during Session 0 that determines parallel batches, worktree assignments, and file conflict analysis.",
        "priority": 10,
        "tasks": [
            {
                "description": "Create ExecutionPlanBuilder class",
                "action": "Create `core/execution_plan.py` with ExecutionPlanBuilder class that extends DependencyResolver to output serializable execution plan with batches and worktree assignments. Store plan in projects.metadata.execution_plan JSONB field."
            },
            {
                "description": "Implement file conflict analyzer",
                "action": "Add FileConflictAnalyzer to execution_plan.py that parses task descriptions for likely file modifications, uses epic context to predict file overlap, and marks conflicting tasks for sequential execution. Store predicted files in tasks.metadata.predicted_files[]."
            },
            {
                "description": "Add worktree pre-planning logic",
                "action": "Extend ExecutionPlanBuilder to calculate optimal worktree count (max 4), pre-assign tasks to worktrees based on epic boundaries, and validate no predicted file conflicts within same batch."
            },
            {
                "description": "Create execution plan API endpoints",
                "action": "Add to api/main.py: POST /projects/{id}/build-execution-plan (trigger plan building), GET /projects/{id}/execution-plan (retrieve plan), PATCH /projects/{id}/execution-plan (manual adjustments). Auto-trigger after Session 0 completes."
            },
            {
                "description": "Add database schema for execution plans",
                "action": "Create migration to add: execution_plan JSONB column to projects table, predicted_files TEXT[] to tasks table. Update core/database.py with methods for execution plan CRUD."
            },
            {
                "description": "Integrate plan building into Session 0",
                "action": "Modify core/orchestrator.py to automatically trigger execution plan building after initialization session completes successfully. Store plan and log batch assignments."
            }
        ]
    },
    {
        "name": "Phase 2: Automatic Parallel Orchestration",
        "description": "Make parallel mode the default execution path with automatic batch execution, worktree lifecycle management, and merge validation.",
        "priority": 20,
        "tasks": [
            {
                "description": "Implement automatic mode selection",
                "action": "Modify Orchestrator.start_project() to check execution plan: if execution_plan.batches[0].can_parallel is true, use parallel mode; otherwise sequential mode. No manual trigger required."
            },
            {
                "description": "Create BatchExecutor class",
                "action": "Create `core/batch_executor.py` with BatchExecutor class that manages parallel batch lifecycle: create worktrees for batch tasks, spawn agents per worktree, monitor completion, trigger merge validation, advance to next batch."
            },
            {
                "description": "Implement merge validation pipeline",
                "action": "Add MergeValidator to batch_executor.py that after batch completion: runs git merge --no-commit from each worktree, spawns review agent if conflicts, runs test suite on merged result, commits merge and cleans up worktrees on pass, flags for human review on fail."
            },
            {
                "description": "Add worktree lifecycle management",
                "action": "Create worktrees table (id, project_id, branch_name, batch_id, status, created_at, merged_at, metadata). Add WorktreeManager class to handle create, execute, merge, cleanup lifecycle."
            },
            {
                "description": "Enhance progress tracking for batches",
                "action": "Add batch_id and worktree_id to sessions table. Update progress views to show parallel vs sequential execution time. Calculate and display efficiency gains."
            },
            {
                "description": "Create worktree API endpoints",
                "action": "Add to api/main.py: GET /projects/{id}/worktrees, POST /projects/{id}/worktrees (manual creation), DELETE /worktrees/{id} (cleanup), POST /worktrees/{id}/merge (trigger merge)."
            },
            {
                "description": "Add batch execution API endpoints",
                "action": "Add to api/main.py: POST /projects/{id}/batches/{batch}/start, GET /projects/{id}/batches/{batch}/status, POST /projects/{id}/batches/{batch}/pause. Wire up to BatchExecutor."
            },
            {
                "description": "Update parallel execution to use BatchExecutor",
                "action": "Refactor ParallelExecutor to use BatchExecutor for coordinated batch execution. Remove manual trigger requirement from /parallel/start - make it the default path when plan supports parallelism."
            }
        ]
    },
    {
        "name": "Phase 3: Expertise File System (ADWS Pattern)",
        "description": "Hybrid expertise storage - files for portability, DB for querying. Match ADWS .claude/ structure for compatibility with Claude SDK.",
        "priority": 30,
        "tasks": [
            {
                "description": "Create ExpertiseExporter class",
                "action": "Create `core/expertise_exporter.py` that writes database expertise to .claude/commands/experts/{domain}/ structure: expertise.yaml (from expertise.patterns + metrics), question.md (generated query template), self-improve.md (trigger conditions). Run after each session with new learnings."
            },
            {
                "description": "Implement expertise sync service",
                "action": "Add ExpertiseSyncService to expertise_exporter.py: on project load import from files to DB, on expertise update sync DB to files, handle conflicts with git-friendly resolution."
            },
            {
                "description": "Generate native Claude SDK skills",
                "action": "When expertise crosses threshold (confidence > 0.8, usage > 10): generate .claude/skills/{domain}-expert/SKILL.md with proper frontmatter (name, description), embed relevant patterns as skill instructions."
            },
            {
                "description": "Update domain router for file-based skills",
                "action": "Modify ExpertiseManager.route_to_expert() to: check .claude/skills/ for native skills first, fall back to DB-stored expertise, log routing decisions for learning."
            },
            {
                "description": "Add expertise file API endpoints",
                "action": "Add to api/main.py: POST /projects/{id}/expertise/export (trigger export), POST /projects/{id}/expertise/sync (bidirectional sync), GET /projects/{id}/expertise/files (list file-based expertise)."
            },
            {
                "description": "Create expertise file templates",
                "action": "Create templates/expertise/ directory with: expertise.yaml.j2, question.md.j2, self-improve.md.j2, SKILL.md.j2. Use Jinja2 for template rendering."
            }
        ]
    },
    {
        "name": "Phase 4: Generated Project Bootstrapping",
        "description": "Generated projects have Claude SDK structure from day 1 with skills, expertise, and sub-agent delegation.",
        "priority": 40,
        "tasks": [
            {
                "description": "Create project template structure",
                "action": "Create templates/claude-sdk-project/ with: .claude/settings.json, .claude/skills/.gitkeep, .claude/commands/experts/.gitkeep, .claude/CLAUDE.md template."
            },
            {
                "description": "Enhance init script for template copying",
                "action": "Modify initializer to copy template structure to generations/{project}/.claude/, generate initial CLAUDE.md from app_spec analysis, pre-create domain expert stubs based on detected domains."
            },
            {
                "description": "Add domain detection during initialization",
                "action": "Create DomainDetector class that analyzes app_spec.txt to identify domains (frontend, backend, database, auth, etc.). Create initial expertise stubs for each detected domain."
            },
            {
                "description": "Implement coding agent expertise hooks",
                "action": "After each task completion: analyze code changes for patterns, update domain expertise files in .claude/commands/experts/, commit expertise updates with code changes."
            },
            {
                "description": "Add sub-agent delegation to coding prompt",
                "action": "Update prompts/coding_prompt.md to: read .claude/commands/experts/ for domains, route complex tasks to domain-specific expertise, operate each domain expert in context of its expertise.yaml."
            }
        ]
    },
    {
        "name": "Phase 5: Kanban/Swimlane UI (Automaker Pattern)",
        "description": "Visual parallel execution management with drag-drop kanban board, worktree swimlanes, and real-time updates.",
        "priority": 50,
        "tasks": [
            {
                "description": "Create KanbanBoard component",
                "action": "Create web-ui/src/components/KanbanBoard.tsx using @dnd-kit for drag-drop. Columns: Backlog, In Progress, Review, Done. Cards show task + assigned worktree. Port patterns from Automaker's kanban-board.tsx."
            },
            {
                "description": "Implement worktree swimlanes",
                "action": "Create web-ui/src/components/WorktreeSwimlane.tsx with horizontal swimlanes per active worktree. Show: branch name, current task, agent status, last commit. Visual indicator for merge readiness."
            },
            {
                "description": "Add execution timeline visualization",
                "action": "Create web-ui/src/components/ExecutionTimeline.tsx with Gantt-style view of batch execution plan. Show dependencies between batches, predicted vs actual completion overlay."
            },
            {
                "description": "Implement real-time WebSocket updates",
                "action": "Add WebSocket events for: task status changes, worktree creation/deletion, merge conflicts detected, batch transitions. Update kanban without page refresh. Wire to existing WebSocket infrastructure."
            },
            {
                "description": "Add manual override controls",
                "action": "Add to KanbanBoard: drag task between worktrees (re-assign), force sequential execution toggle, pause/resume batch execution button, manually trigger merge validation."
            },
            {
                "description": "Create parallel execution dashboard page",
                "action": "Create web-ui/src/app/projects/[id]/parallel/page.tsx that combines: KanbanBoard, WorktreeSwimlanes, ExecutionTimeline. Add navigation link to project sidebar."
            },
            {
                "description": "Install @dnd-kit dependencies",
                "action": "Add @dnd-kit/core, @dnd-kit/sortable, @dnd-kit/utilities to web-ui package.json. Update any conflicting dependencies."
            }
        ]
    }
]


async def main():
    """Create all epics and tasks."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    db = TaskDatabase(db_url)
    await db.connect()

    try:
        print(f"Creating roadmap for project: {PROJECT_ID}")
        print("=" * 60)

        for epic_data in ROADMAP:
            # Create epic
            epic = await db.create_epic(
                project_id=PROJECT_ID,
                name=epic_data["name"],
                description=epic_data["description"],
                priority=epic_data["priority"]
            )
            print(f"\nCreated Epic {epic['id']}: {epic_data['name']}")

            # Create tasks
            for i, task_data in enumerate(epic_data["tasks"]):
                task = await db.create_task(
                    epic_id=epic["id"],
                    project_id=PROJECT_ID,
                    description=task_data["description"],
                    action=task_data["action"],
                    priority=i * 10  # 0, 10, 20, etc.
                )
                print(f"  Task {task['id']}: {task_data['description'][:50]}...")

        print("\n" + "=" * 60)
        print("Roadmap created successfully!")
        print(f"Total epics: {len(ROADMAP)}")
        print(f"Total tasks: {sum(len(e['tasks']) for e in ROADMAP)}")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
