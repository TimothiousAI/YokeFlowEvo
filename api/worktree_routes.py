"""
Worktree API Routes
===================

REST API endpoints for managing git worktrees within projects.
Provides operations for creating, merging, syncing, and cleaning up worktrees.
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.database_connection import get_db
from core.parallel.worktree_manager import WorktreeManager, GitCommandError, WorktreeConflictError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["worktrees"])


# =============================================================================
# Request/Response Models
# =============================================================================

class WorktreeInfoResponse(BaseModel):
    """Response model for worktree information."""
    epic_id: int
    path: str
    branch: str
    status: str
    created_at: str
    merged_at: Optional[str] = None


class WorktreeCreateRequest(BaseModel):
    """Request model for creating a worktree."""
    epic_name: str = Field(..., description="Epic name for branch naming")


class WorktreeMergeRequest(BaseModel):
    """Request model for merging a worktree."""
    squash: bool = Field(False, description="Whether to squash commits")


class WorktreeSyncRequest(BaseModel):
    """Request model for syncing a worktree from main."""
    strategy: str = Field("merge", description="Sync strategy: 'merge' or 'rebase'")


class WorktreeResolveRequest(BaseModel):
    """Request model for resolving conflicts."""
    strategy: str = Field("manual", description="Resolution strategy: 'ours', 'theirs', or 'manual'")


class ConflictDetail(BaseModel):
    """Model for conflict details."""
    file: str
    status: str
    details: str


class ConflictListResponse(BaseModel):
    """Response model for conflict list."""
    conflicts: List[ConflictDetail]


class SyncResponse(BaseModel):
    """Response model for sync operation."""
    status: str
    strategy: str
    message: str
    conflicts: Optional[List[str]] = None


class ResolveResponse(BaseModel):
    """Response model for conflict resolution."""
    status: str
    strategy: str
    message: str
    conflicts: Optional[List[ConflictDetail]] = None
    files_resolved: Optional[List[str]] = None


class MergeResponse(BaseModel):
    """Response model for merge operation."""
    commit_sha: str
    message: str


# =============================================================================
# Helper Functions
# =============================================================================

async def get_worktree_manager(project_id: str, db=Depends(get_db)) -> WorktreeManager:
    """
    Get a WorktreeManager instance for a project.

    Args:
        project_id: Project UUID string
        db: Database connection

    Returns:
        Configured WorktreeManager instance

    Raises:
        HTTPException: If project not found
    """
    try:
        project_uuid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")

    # Get project from database
    project = await db.get_project(project_uuid)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get project path from local_path field
    project_path = project.get('local_path')
    if not project_path:
        raise HTTPException(
            status_code=500,
            detail="Project path not configured"
        )

    # Create and initialize WorktreeManager
    manager = WorktreeManager(
        project_path=project_path,
        project_id=project_id,
        db=db
    )

    await manager.initialize()

    return manager


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/api/projects/{project_id}/worktrees", response_model=List[WorktreeInfoResponse])
async def list_worktrees(
    project_id: str,
    db=Depends(get_db)
):
    """
    List all worktrees for a project.

    Returns list of worktree information including paths, branches, and status.
    """
    try:
        manager = await get_worktree_manager(project_id, db)
        worktrees = manager.list_worktrees()

        return [
            WorktreeInfoResponse(
                epic_id=wt.epic_id,
                path=wt.path,
                branch=wt.branch,
                status=wt.status,
                created_at=wt.created_at.isoformat() if wt.created_at else "",
                merged_at=wt.merged_at.isoformat() if wt.merged_at else None
            )
            for wt in worktrees
        ]
    except Exception as e:
        logger.error(f"Failed to list worktrees: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/projects/{project_id}/worktrees/{epic_id}", response_model=WorktreeInfoResponse)
async def get_worktree(
    project_id: str,
    epic_id: int,
    db=Depends(get_db)
):
    """
    Get specific worktree information by epic ID.
    """
    try:
        manager = await get_worktree_manager(project_id, db)
        worktrees = manager.list_worktrees()

        # Find worktree for this epic
        worktree = next((wt for wt in worktrees if wt.epic_id == epic_id), None)

        if not worktree:
            raise HTTPException(
                status_code=404,
                detail=f"No worktree found for epic {epic_id}"
            )

        return WorktreeInfoResponse(
            epic_id=worktree.epic_id,
            path=worktree.path,
            branch=worktree.branch,
            status=worktree.status,
            created_at=worktree.created_at.isoformat() if worktree.created_at else "",
            merged_at=worktree.merged_at.isoformat() if worktree.merged_at else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get worktree: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/projects/{project_id}/worktrees/{epic_id}/create", response_model=WorktreeInfoResponse)
async def create_worktree(
    project_id: str,
    epic_id: int,
    request: WorktreeCreateRequest,
    db=Depends(get_db)
):
    """
    Create a new worktree for an epic.

    Creates an isolated git worktree with its own branch for parallel development.
    """
    try:
        manager = await get_worktree_manager(project_id, db)

        worktree = await manager.create_worktree(
            epic_id=epic_id,
            epic_name=request.epic_name
        )

        return WorktreeInfoResponse(
            epic_id=worktree.epic_id,
            path=worktree.path,
            branch=worktree.branch,
            status=worktree.status,
            created_at=worktree.created_at.isoformat() if worktree.created_at else "",
            merged_at=worktree.merged_at.isoformat() if worktree.merged_at else None
        )
    except GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        raise HTTPException(status_code=500, detail=f"Git operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to create worktree: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/projects/{project_id}/worktrees/{epic_id}/merge", response_model=MergeResponse)
async def merge_worktree(
    project_id: str,
    epic_id: int,
    request: WorktreeMergeRequest,
    db=Depends(get_db)
):
    """
    Merge worktree changes back to main branch.

    Integrates all changes from the worktree's branch into the main branch.
    May return conflict error if merge conflicts are detected.
    """
    try:
        manager = await get_worktree_manager(project_id, db)

        merge_commit = await manager.merge_worktree(
            epic_id=epic_id,
            squash=request.squash
        )

        return MergeResponse(
            commit_sha=merge_commit,
            message=f"Successfully merged worktree for epic {epic_id}"
        )
    except WorktreeConflictError as e:
        logger.warning(f"Merge conflict: {e}")
        raise HTTPException(
            status_code=409,
            detail=f"Merge conflict detected: {str(e)}"
        )
    except GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        raise HTTPException(status_code=500, detail=f"Git operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to merge worktree: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/projects/{project_id}/worktrees/{epic_id}/conflicts", response_model=ConflictListResponse)
async def get_conflicts(
    project_id: str,
    epic_id: int,
    db=Depends(get_db)
):
    """
    Get detailed information about merge conflicts for a worktree.

    Returns list of files with conflicts and their conflict types.
    """
    try:
        manager = await get_worktree_manager(project_id, db)

        conflicts = await manager.get_conflict_details(epic_id)

        return ConflictListResponse(
            conflicts=[
                ConflictDetail(
                    file=c['file'],
                    status=c['status'],
                    details=c['details']
                )
                for c in conflicts
            ]
        )
    except GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        raise HTTPException(status_code=500, detail=f"Git operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to get conflicts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/projects/{project_id}/worktrees/{epic_id}/resolve", response_model=ResolveResponse)
async def resolve_conflicts(
    project_id: str,
    epic_id: int,
    request: WorktreeResolveRequest,
    db=Depends(get_db)
):
    """
    Resolve merge conflicts using specified strategy.

    Strategies:
    - 'ours': Keep changes from main branch
    - 'theirs': Keep changes from worktree branch
    - 'manual': Leave conflict markers for human resolution
    """
    try:
        manager = await get_worktree_manager(project_id, db)

        result = await manager.resolve_conflict(
            epic_id=epic_id,
            strategy=request.strategy
        )

        # Convert conflict details to ConflictDetail models if present
        conflicts = None
        if 'conflicts' in result and result['conflicts']:
            conflicts = [
                ConflictDetail(
                    file=c.get('file', 'unknown'),
                    status=c.get('status', 'unknown'),
                    details=c.get('details', '')
                )
                for c in result['conflicts']
            ]

        return ResolveResponse(
            status=result['status'],
            strategy=result['strategy'],
            message=result['message'],
            conflicts=conflicts,
            files_resolved=result.get('files_resolved')
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        raise HTTPException(status_code=500, detail=f"Git operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to resolve conflicts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/projects/{project_id}/worktrees/{epic_id}")
async def cleanup_worktree(
    project_id: str,
    epic_id: int,
    db=Depends(get_db)
):
    """
    Clean up and remove a worktree.

    Removes the worktree directory and cleans up associated branches.
    """
    try:
        manager = await get_worktree_manager(project_id, db)

        await manager.cleanup_worktree(epic_id)

        return {
            "message": f"Successfully cleaned up worktree for epic {epic_id}"
        }
    except GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        raise HTTPException(status_code=500, detail=f"Git operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to cleanup worktree: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/projects/{project_id}/worktrees/{epic_id}/sync", response_model=SyncResponse)
async def sync_worktree(
    project_id: str,
    epic_id: int,
    request: WorktreeSyncRequest,
    db=Depends(get_db)
):
    """
    Sync worktree with latest changes from main branch.

    Pulls the latest changes from main branch into the worktree.

    Strategies:
    - 'merge': Merge main branch changes into worktree (default)
    - 'rebase': Rebase worktree changes onto main
    """
    try:
        manager = await get_worktree_manager(project_id, db)

        result = await manager.sync_worktree_from_main(
            epic_id=epic_id,
            strategy=request.strategy
        )

        return SyncResponse(
            status=result['status'],
            strategy=result['strategy'],
            message=result['message'],
            conflicts=result.get('conflicts')
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        raise HTTPException(status_code=500, detail=f"Git operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to sync worktree: {e}")
        raise HTTPException(status_code=500, detail=str(e))
