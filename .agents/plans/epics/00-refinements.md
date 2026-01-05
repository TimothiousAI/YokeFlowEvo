# Epic 00: Core Refinements

**Priority:** P0 (Quick Wins)
**Estimated Duration:** 1 day
**Dependencies:** None
**Phase:** 0 (Can be done immediately)

---

## Overview

Improvements identified from real-world usage of YokeFlow, specifically from pushing generated projects to their own repositories. These are quick fixes that improve the quality of generated projects.

---

## Background: The PodPal Push Problem

When pushing the completed PodPal project to GitHub:
- Push kept timing out due to repository size
- **24,931 files** from `server/venv/` were tracked in git
- **6.2 million lines** of dependency code in the repository
- `.gitignore` existed but didn't exclude `venv/` before first commit

**Root Cause:** The agent installed dependencies and committed them before `.gitignore` was properly configured.

---

## Tasks

### 0.1 Standard .gitignore Template

**Description:** Ensure all generated projects start with a comprehensive `.gitignore`.

**File to Modify:** `prompts/initializer_prompt.md` (or `prompts/initializer_prompt_local.md` / `prompts/initializer_prompt_docker.md`)

**Add to Session 0 Instructions:**

```markdown
## Project Initialization Requirements

Before running init.sh or installing any dependencies, create a comprehensive .gitignore file:

```gitignore
# Dependencies
node_modules/
venv/
.venv/
env/
__pycache__/
*.pyc
.pyo
*.egg-info/
dist/
build/

# Environment
.env
.env.local
.env.*.local
*.env

# IDE
.vscode/
.idea/
*.swp
*.swo
.DS_Store

# Logs
*.log
logs/
npm-debug.log*

# Build outputs
dist/
build/
out/
.next/
.nuxt/

# Test coverage
coverage/
.coverage
htmlcov/
.pytest_cache/

# Package locks (optional - uncomment if not needed)
# package-lock.json
# yarn.lock
```

IMPORTANT: Commit .gitignore BEFORE running any install commands.
```

**Acceptance Criteria:**
- [ ] .gitignore created before any `npm install` or `pip install`
- [ ] Common dependency directories excluded
- [ ] Environment files excluded
- [ ] IDE and OS files excluded

---

### 0.2 init.sh .gitignore Guard

**Description:** Modify init.sh generation to ensure .gitignore is committed first.

**Current Problem:** init.sh installs dependencies which may get committed if .gitignore isn't set up.

**Solution - Add to init.sh Template:**

```bash
#!/bin/bash
set -e

echo "🚀 Initializing project..."

# CRITICAL: Ensure .gitignore is set up before installing dependencies
if [ ! -f .gitignore ]; then
    echo "⚠️  Creating .gitignore..."
    cat > .gitignore << 'GITIGNORE'
# Dependencies
node_modules/
venv/
.venv/
__pycache__/
*.pyc

# Environment
.env
.env.local

# Logs
*.log
logs/

# Build
dist/
build/
GITIGNORE
fi

# Commit .gitignore before installing anything
if ! git diff --quiet .gitignore 2>/dev/null; then
    git add .gitignore
    git commit -m "chore: Initialize .gitignore" 2>/dev/null || true
fi

# Now safe to install dependencies
echo "📦 Installing dependencies..."
# ... rest of init.sh
```

**Acceptance Criteria:**
- [ ] .gitignore created if missing
- [ ] .gitignore committed before dependency installation
- [ ] Prevents accidental venv/node_modules commits

---

### 0.3 Post-Session Validation

**Description:** Add validation to detect accidentally committed large directories.

**File to Create:** `core/validation.py`

**Implementation:**

```python
import subprocess
from pathlib import Path
from typing import List, Tuple

# Patterns that should NEVER be in git
FORBIDDEN_PATTERNS = [
    'node_modules/',
    'venv/',
    '.venv/',
    '__pycache__/',
    '.env',
    '*.pyc',
]

# Size thresholds
MAX_FILE_COUNT_WARNING = 1000
MAX_REPO_SIZE_MB_WARNING = 100

async def validate_repository(project_path: Path) -> List[str]:
    """
    Validate repository doesn't contain problematic files.
    Returns list of warnings.
    """
    warnings = []

    # Check for forbidden patterns in tracked files
    result = subprocess.run(
        ['git', 'ls-files'],
        cwd=project_path,
        capture_output=True,
        text=True
    )

    tracked_files = result.stdout.strip().split('\n')

    for pattern in FORBIDDEN_PATTERNS:
        matches = [f for f in tracked_files if pattern.rstrip('/') in f]
        if matches:
            warnings.append(
                f"⚠️  Found {len(matches)} files matching '{pattern}' in git. "
                f"These should be in .gitignore."
            )

    # Check total file count
    if len(tracked_files) > MAX_FILE_COUNT_WARNING:
        warnings.append(
            f"⚠️  Repository has {len(tracked_files)} tracked files. "
            f"Check for accidentally committed dependencies."
        )

    # Check repository size
    result = subprocess.run(
        ['git', 'count-objects', '-vH'],
        cwd=project_path,
        capture_output=True,
        text=True
    )
    # Parse size from output...

    return warnings

async def fix_gitignore(project_path: Path) -> bool:
    """Add missing entries to .gitignore."""
    gitignore_path = project_path / '.gitignore'

    existing = gitignore_path.read_text() if gitignore_path.exists() else ''

    missing = []
    for pattern in FORBIDDEN_PATTERNS:
        if pattern not in existing:
            missing.append(pattern)

    if missing:
        with open(gitignore_path, 'a') as f:
            f.write('\n# Auto-added by YokeFlow\n')
            for pattern in missing:
                f.write(f'{pattern}\n')
        return True

    return False
```

**Integration Points:**
- Run after Session 0 completes
- Run before project completion
- Add API endpoint for manual validation

**Acceptance Criteria:**
- [ ] Detects committed venv/node_modules
- [ ] Warns about large repositories
- [ ] Can auto-fix .gitignore
- [ ] Integrated into session completion

---

### 0.4 Documentation: Exporting Projects

**Description:** Add documentation for exporting generated projects to their own repositories.

**File to Create:** `docs/exporting-projects.md`

**Content:**

```markdown
# Exporting Generated Projects

After YokeFlow completes a project, you may want to push it to its own repository.

## Quick Export

1. Create a new repository on GitHub (empty, no README)

2. Add remote and push:
   ```bash
   cd generations/your_project
   git remote add origin https://github.com/you/your-project.git
   git push -u origin main
   ```

## If Push Fails (Repository Too Large)

If the push times out, dependencies may have been accidentally committed:

1. **Check for large directories:**
   ```bash
   git ls-files | grep -E "node_modules|venv" | wc -l
   ```

2. **If dependencies are tracked, remove them:**
   ```bash
   # Add to .gitignore first
   echo -e "\nvenv/\nnode_modules/" >> .gitignore

   # Remove from git (keeps files locally)
   git rm -r --cached venv/ node_modules/ 2>/dev/null || true

   # Commit the cleanup
   git commit -m "chore: Remove dependencies from git tracking"
   ```

3. **If history is bloated, create fresh start:**
   ```bash
   # Create orphan branch with current files only
   git checkout --orphan fresh-main
   git add -A
   git commit -m "Initial commit: Project name"

   # Force push to replace remote
   git push -u origin fresh-main:main --force

   # Clean up
   git branch -D master  # or main
   git branch -m fresh-main main
   ```

## Recommended .gitignore

Ensure your project has these exclusions:

```gitignore
# Dependencies
node_modules/
venv/
.venv/
__pycache__/

# Environment
.env
.env.local

# Build outputs
dist/
build/
```
```

**Acceptance Criteria:**
- [ ] Clear export instructions
- [ ] Troubleshooting for large repos
- [ ] .gitignore recommendations

---

### 0.5 Coding Prompt .gitignore Reminder

**Description:** Add reminder to coding prompt to check .gitignore before committing.

**File to Modify:** `prompts/coding_prompt.md`

**Add Section:**

```markdown
## Before Committing

Before running `git add .` or `git commit`:

1. Verify .gitignore excludes:
   - `node_modules/` (if using npm/yarn)
   - `venv/` or `.venv/` (if using Python)
   - `__pycache__/`
   - `.env` files

2. If you installed dependencies and .gitignore wasn't set up:
   ```bash
   # Add exclusions
   echo -e "node_modules/\nvenv/\n__pycache__/" >> .gitignore

   # Remove from tracking if already added
   git rm -r --cached node_modules/ venv/ 2>/dev/null || true
   ```

3. Never commit environment files with secrets.
```

**Acceptance Criteria:**
- [ ] Agent checks .gitignore before commits
- [ ] Agent knows how to fix if dependencies were staged

---

## Testing Requirements

### Manual Tests

1. Generate a new project and verify:
   - .gitignore exists before first dependency install
   - venv/node_modules not in `git ls-files` output
   - Repository size reasonable (<50MB typically)

2. Push generated project to GitHub:
   - Should complete without timeout
   - No warnings about large files

### Automated Tests

```python
class TestGitIgnoreHandling:
    def test_gitignore_created_before_install(self):
        """Verify .gitignore exists before npm/pip install in init.sh"""

    def test_venv_not_tracked(self):
        """Verify venv directory not in git ls-files"""

    def test_node_modules_not_tracked(self):
        """Verify node_modules not in git ls-files"""

    def test_validation_detects_problems(self):
        """Verify validation catches committed dependencies"""
```

---

## Dependencies

- None (independent quick wins)

## Dependents

- All other epics benefit from cleaner generated projects

---

## Notes

- These are low-risk, high-value improvements
- Can be implemented incrementally
- Each task is independent
- Consider adding pre-commit hooks in future iteration
