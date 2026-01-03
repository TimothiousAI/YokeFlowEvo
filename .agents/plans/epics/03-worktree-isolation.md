# Epic 03: Git Worktree Isolation

**Priority:** P0 (Critical Path)
**Estimated Duration:** 2-3 days
**Dependencies:** Epic 01 (Foundation)
**Phase:** 1

---

## Overview

Implement git worktree-based isolation for parallel epic execution. Each epic gets its own isolated git branch and worktree, enabling multiple agents to work simultaneously without file conflicts.

---

## Background: Git Worktrees

Git worktrees allow multiple working directories linked to the same repository:

```bash
# Create a worktree on a new branch
git worktree add ../project-epic-1 -b epic/1-auth

# List worktrees
git worktree list

# Remove worktree
git worktree remove ../project-epic-1
```

**Benefits:**
- Lightweight (shared .git directory)
- Native branch management
- No container overhead
- Easy merge/conflict resolution
- Each worktree is a full working directory

---

## Tasks

### 3.1 WorktreeManager Core Implementation

**Description:** Implement the worktree management class.

**File:** `core/parallel/worktree_manager.py`

**Class Structure:**

```python
@dataclass
class WorktreeInfo:
    """Information about a worktree"""
    path: Path
    branch: str
    epic_id: int
    status: str  # 'active', 'merged', 'conflict', 'deleted'
    created_at: datetime
    merged_at: Optional[datetime] = None

class WorktreeManager:
    """
    Manages git worktrees for parallel epic execution.

    Each epic gets an isolated worktree where its agent can work
    without affecting other parallel agents or the main branch.
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.worktrees_dir = project_path / ".worktrees"
        self._active_worktrees: Dict[int, WorktreeInfo] = {}

    async def initialize(self) -> None:
        """Initialize worktree infrastructure"""

    async def create_worktree(self, epic_id: int, epic_name: str) -> Path:
        """Create isolated worktree for an epic"""

    async def merge_worktree(self, epic_id: int, squash: bool = False) -> bool:
        """Merge completed worktree back to main"""

    async def cleanup_worktree(self, epic_id: int) -> None:
        """Remove worktree after successful merge"""

    async def get_worktree_status(self, epic_id: int) -> Optional[WorktreeInfo]:
        """Get status of a worktree"""

    async def list_worktrees(self) -> List[WorktreeInfo]:
        """List all active worktrees"""

    async def sync_worktree_from_main(self, epic_id: int) -> bool:
        """Pull latest changes from main into worktree"""

    async def has_conflicts(self, epic_id: int) -> bool:
        """Check if merging worktree would cause conflicts"""
```

**Acceptance Criteria:**
- [ ] Creates worktrees successfully
- [ ] Handles branch name sanitization
- [ ] Merges without data loss
- [ ] Cleans up properly
- [ ] Handles existing worktrees gracefully

---

### 3.2 Git Command Execution

**Description:** Implement async git command execution with proper error handling.

**Helper Methods:**

```python
async def _run_git(self, args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run git command asynchronously with timeout"""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(),
        timeout=60.0  # 1 minute timeout
    )

    if proc.returncode != 0:
        raise GitCommandError(
            command=["git"] + args,
            returncode=proc.returncode,
            stdout=stdout.decode(),
            stderr=stderr.decode()
        )

    return subprocess.CompletedProcess(["git"] + args, 0, stdout, stderr)

async def _get_main_branch(self) -> str:
    """Detect main branch name (main or master)"""

async def _get_current_branch(self, cwd: Path) -> str:
    """Get current branch in a directory"""

async def _has_uncommitted_changes(self, cwd: Path) -> bool:
    """Check for uncommitted changes"""

async def _commit_pending(self, cwd: Path, message: str) -> Optional[str]:
    """Commit pending changes, return commit hash"""
```

**Error Handling:**

```python
class GitCommandError(Exception):
    """Raised when a git command fails"""
    def __init__(self, command, returncode, stdout, stderr):
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Git command failed: {' '.join(command)}")

class WorktreeConflictError(Exception):
    """Raised when merge conflict detected"""
    def __init__(self, epic_id, conflicting_files):
        self.epic_id = epic_id
        self.conflicting_files = conflicting_files
        super().__init__(f"Merge conflict for epic {epic_id}")
```

**Acceptance Criteria:**
- [ ] Commands execute asynchronously
- [ ] Timeouts prevent hanging
- [ ] Errors captured with context
- [ ] Windows path handling works

---

### 3.3 Worktree Creation Flow

**Description:** Implement the full worktree creation workflow.

**Flow:**

```python
async def create_worktree(self, epic_id: int, epic_name: str) -> Path:
    """
    Create isolated worktree for an epic.

    Steps:
    1. Check if worktree already exists (reuse if so)
    2. Ensure .worktrees directory exists
    3. Create branch from main
    4. Create worktree linked to branch
    5. Record in database
    6. Return worktree path
    """
    branch_name = self._make_branch_name(epic_id, epic_name)
    worktree_path = self.worktrees_dir / f"epic-{epic_id}"

    # Check for existing worktree
    if worktree_path.exists():
        existing = await self._validate_existing_worktree(worktree_path, branch_name)
        if existing:
            return worktree_path
        else:
            # Corrupted worktree, clean up
            await self._force_remove_worktree(worktree_path)

    # Ensure infrastructure
    self.worktrees_dir.mkdir(exist_ok=True)

    # Get main branch
    main_branch = await self._get_main_branch()

    # Create branch
    try:
        await self._run_git(
            ["branch", branch_name, main_branch],
            self.project_path
        )
    except GitCommandError as e:
        if "already exists" not in e.stderr:
            raise

    # Create worktree
    await self._run_git(
        ["worktree", "add", str(worktree_path), branch_name],
        self.project_path
    )

    # Record in memory and database
    info = WorktreeInfo(
        path=worktree_path,
        branch=branch_name,
        epic_id=epic_id,
        status='active',
        created_at=datetime.now()
    )
    self._active_worktrees[epic_id] = info

    # Record in database
    async with DatabaseManager() as db:
        await db.create_worktree(
            project_id=self.project_id,
            epic_id=epic_id,
            branch_name=branch_name,
            worktree_path=str(worktree_path)
        )

    logger.info(f"Created worktree for epic {epic_id}: {worktree_path}")
    return worktree_path
```

**Acceptance Criteria:**
- [ ] Creates worktree and branch
- [ ] Reuses existing worktrees
- [ ] Handles branch name conflicts
- [ ] Records in database
- [ ] Logs appropriately

---

### 3.4 Worktree Merge Flow

**Description:** Implement the merge workflow with conflict handling.

**Flow:**

```python
async def merge_worktree(self, epic_id: int, squash: bool = False) -> bool:
    """
    Merge completed worktree back to main branch.

    Steps:
    1. Verify worktree exists and is active
    2. Commit any uncommitted changes
    3. Check for potential conflicts
    4. Switch to main branch
    5. Perform merge (regular or squash)
    6. Handle conflicts if any
    7. Update status

    Returns True if successful, False if conflicts.
    """
    if epic_id not in self._active_worktrees:
        raise ValueError(f"No active worktree for epic {epic_id}")

    worktree = self._active_worktrees[epic_id]
    main_branch = await self._get_main_branch()

    # Commit pending changes
    await self._commit_pending(
        worktree.path,
        f"Final changes for epic {epic_id}"
    )

    # Check for conflicts before attempting merge
    conflicts = await self._check_merge_conflicts(worktree.branch)
    if conflicts:
        logger.warning(f"Potential conflicts detected: {conflicts}")

    # Switch to main
    await self._run_git(["checkout", main_branch], self.project_path)

    try:
        if squash:
            await self._run_git(
                ["merge", "--squash", worktree.branch],
                self.project_path
            )
            await self._run_git(
                ["commit", "-m", f"Squash merge epic {epic_id}: {worktree.branch}"],
                self.project_path
            )
        else:
            await self._run_git(
                ["merge", worktree.branch, "--no-ff", "-m",
                 f"Merge epic {epic_id}: {worktree.branch}"],
                self.project_path
            )

        # Get merge commit
        result = await self._run_git(["rev-parse", "HEAD"], self.project_path)
        merge_commit = result.stdout.decode().strip()

        # Update status
        worktree.status = 'merged'
        worktree.merged_at = datetime.now()

        # Update database
        async with DatabaseManager() as db:
            await db.mark_worktree_merged(worktree.id, merge_commit)

        logger.info(f"Successfully merged epic {epic_id}")
        return True

    except GitCommandError as e:
        if "CONFLICT" in e.stdout or "CONFLICT" in e.stderr:
            logger.error(f"Merge conflict for epic {epic_id}")
            await self._run_git(["merge", "--abort"], self.project_path)
            worktree.status = 'conflict'
            return False
        raise
```

**Acceptance Criteria:**
- [ ] Merges successfully when no conflicts
- [ ] Detects and reports conflicts
- [ ] Aborts cleanly on conflict
- [ ] Updates database status
- [ ] Supports squash merge

---

### 3.5 Conflict Resolution Workflow

**Description:** Implement conflict detection and resolution helpers.

**Methods:**

```python
async def _check_merge_conflicts(self, branch: str) -> List[str]:
    """Check for potential merge conflicts without actually merging"""
    try:
        # Dry run merge
        await self._run_git(
            ["merge", "--no-commit", "--no-ff", branch],
            self.project_path
        )
        # Abort the test merge
        await self._run_git(["merge", "--abort"], self.project_path)
        return []
    except GitCommandError as e:
        # Parse conflicting files from output
        conflicts = re.findall(r'CONFLICT.*?: (.+)', e.stdout + e.stderr)
        await self._run_git(["merge", "--abort"], self.project_path)
        return conflicts

async def get_conflict_details(self, epic_id: int) -> Dict:
    """Get details about merge conflicts"""
    worktree = self._active_worktrees.get(epic_id)
    if not worktree or worktree.status != 'conflict':
        return {}

    conflicts = await self._check_merge_conflicts(worktree.branch)
    return {
        'epic_id': epic_id,
        'branch': worktree.branch,
        'conflicting_files': conflicts,
        'resolution_options': [
            'manual',      # Human resolves
            'ours',        # Keep main branch version
            'theirs',      # Keep worktree version
            'retry_later'  # Try again after other merges
        ]
    }

async def resolve_conflict(self, epic_id: int, strategy: str) -> bool:
    """Resolve merge conflict using specified strategy"""
    if strategy == 'ours':
        await self._run_git(
            ["merge", "-X", "ours", worktree.branch],
            self.project_path
        )
    elif strategy == 'theirs':
        await self._run_git(
            ["merge", "-X", "theirs", worktree.branch],
            self.project_path
        )
    # ... etc
```

**Acceptance Criteria:**
- [ ] Detects conflicts accurately
- [ ] Provides resolution options
- [ ] Implements resolution strategies
- [ ] Doesn't corrupt repository

---

### 3.6 Database Integration

**Description:** Integrate worktree operations with database tracking.

**Database Methods Used:**

```python
# From core/database.py
async def create_worktree(project_id, epic_id, branch_name, worktree_path) -> Dict
async def get_worktree(worktree_id) -> Optional[Dict]
async def get_worktree_by_epic(project_id, epic_id) -> Optional[Dict]
async def list_worktrees(project_id) -> List[Dict]
async def update_worktree_status(worktree_id, status) -> None
async def mark_worktree_merged(worktree_id, merge_commit) -> None
async def delete_worktree_record(worktree_id) -> None
```

**Synchronization:**

```python
async def sync_with_database(self) -> None:
    """Sync in-memory state with database"""
    async with DatabaseManager() as db:
        db_worktrees = await db.list_worktrees(self.project_id)

        for db_wt in db_worktrees:
            if db_wt['status'] == 'active':
                path = Path(db_wt['worktree_path'])
                if path.exists():
                    self._active_worktrees[db_wt['epic_id']] = WorktreeInfo(
                        path=path,
                        branch=db_wt['branch_name'],
                        epic_id=db_wt['epic_id'],
                        status=db_wt['status'],
                        created_at=db_wt['created_at']
                    )
```

**Acceptance Criteria:**
- [ ] Database records created on worktree creation
- [ ] Status updates propagated to database
- [ ] State recoverable from database on restart

---

### 3.7 API Endpoints

**Description:** Add REST API endpoints for worktree management.

**Endpoints:**

```python
@app.get("/api/projects/{project_id}/worktrees")
async def list_worktrees(project_id: str):
    """List all worktrees for a project"""

@app.get("/api/projects/{project_id}/worktrees/{epic_id}")
async def get_worktree(project_id: str, epic_id: int):
    """Get worktree details for an epic"""

@app.post("/api/projects/{project_id}/worktrees/{epic_id}/merge")
async def merge_worktree(project_id: str, epic_id: int, squash: bool = False):
    """Merge a worktree back to main"""

@app.get("/api/projects/{project_id}/worktrees/{epic_id}/conflicts")
async def get_conflicts(project_id: str, epic_id: int):
    """Get conflict details if any"""

@app.post("/api/projects/{project_id}/worktrees/{epic_id}/resolve")
async def resolve_conflict(project_id: str, epic_id: int, strategy: str):
    """Resolve merge conflict"""

@app.delete("/api/projects/{project_id}/worktrees/{epic_id}")
async def cleanup_worktree(project_id: str, epic_id: int):
    """Clean up a worktree"""
```

**Acceptance Criteria:**
- [ ] All endpoints functional
- [ ] Proper error responses
- [ ] Authentication enforced

---

## Testing Requirements

### Unit Tests

```python
class TestWorktreeManager:
    def test_create_worktree(self):
        """Creates worktree and branch"""

    def test_create_existing_worktree(self):
        """Reuses existing worktree"""

    def test_merge_no_conflicts(self):
        """Merges cleanly"""

    def test_merge_with_conflicts(self):
        """Detects and handles conflicts"""

    def test_squash_merge(self):
        """Squash merge works"""

    def test_cleanup(self):
        """Removes worktree and branch"""

    def test_branch_name_sanitization(self):
        """Handles special characters in epic names"""
```

### Integration Tests

```python
class TestWorktreeIntegration:
    def test_parallel_worktrees(self):
        """Multiple worktrees can coexist"""

    def test_worktree_isolation(self):
        """Changes in one worktree don't affect others"""

    def test_database_sync(self):
        """State survives restart"""

    def test_merge_order_matters(self):
        """Earlier merges don't break later ones"""
```

---

## Dependencies

- Epic 01: Foundation (database schema)
- Git 2.20+ (worktree support)

## Dependents

- Epic 04: Parallel Executor (needs worktrees for isolation)

---

## Notes

- Windows: Long path names may cause issues, consider using short epic IDs
- Consider automatic cleanup of stale worktrees on startup
- May need to handle case where main branch has advanced during execution
