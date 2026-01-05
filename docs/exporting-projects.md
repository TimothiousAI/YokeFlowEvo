# Exporting Generated Projects to External Repositories

This guide explains how to push your YokeFlow-generated projects to external Git hosting services like GitHub, GitLab, or Bitbucket.

## Overview

YokeFlow generates projects in the `generations/` directory with full git history. Each project is ready to be pushed to an external repository for:
- Version control backup
- Team collaboration
- CI/CD integration
- Production deployment

## Prerequisites

- Git installed and configured
- Account on your chosen Git hosting service (GitHub, GitLab, Bitbucket)
- Generated project in `generations/your-project-name/`

---

## Quick Start

### 1. Navigate to Your Project

```bash
cd generations/your-project-name/
```

### 2. Verify Git Status

```bash
git status
git log --oneline
```

Your project should already have commits from the YokeFlow coding sessions.

### 3. Add Remote Repository

Choose your Git hosting provider:

#### GitHub

```bash
# Create a new repository on GitHub first, then:
git remote add origin https://github.com/your-username/your-repo-name.git

# Or using SSH:
git remote add origin git@github.com:your-username/your-repo-name.git
```

#### GitLab

```bash
# Create a new project on GitLab first, then:
git remote add origin https://gitlab.com/your-username/your-repo-name.git

# Or using SSH:
git remote add origin git@gitlab.com:your-username/your-repo-name.git
```

#### Bitbucket

```bash
# Create a new repository on Bitbucket first, then:
git remote add origin https://bitbucket.org/your-username/your-repo-name.git

# Or using SSH:
git remote add origin git@bitbucket.org:your-username/your-repo-name.git
```

### 4. Push to Remote

```bash
# Push all branches and history
git push -u origin main

# Or if your default branch is named differently:
git branch -M main  # Rename to main first
git push -u origin main
```

---

## Before You Push: Repository Validation

YokeFlow automatically validates repositories after each session to prevent common issues. However, it's good practice to manually check before pushing:

### Check for Accidentally Committed Dependencies

```bash
# Check if node_modules, venv, or other large directories are tracked
git log --all --pretty=format: --name-only --diff-filter=A | sort -u | grep -E "node_modules|venv|__pycache__|dist/|build/"

# If found, see "Troubleshooting" section below
```

### Verify .gitignore is Comprehensive

```bash
cat .gitignore

# Should include at minimum:
# - node_modules/
# - venv/, .venv/, env/, ENV/
# - __pycache__/
# - .env, .env.local, .env.*.local
# - dist/, build/, out/
# - *.log
# - *.sqlite, *.sqlite3, *.db
```

### Check Repository Size

```bash
# Check current repository size
du -sh .git

# List largest files in repository
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | sed -n 's/^blob //p' | sort -nk2 | tail -20
```

**Recommended limits:**
- ✅ < 50 MB: Good
- ⚠️ 50-100 MB: Review large files
- ❌ > 100 MB: Likely has issues, see troubleshooting

---

## Troubleshooting

### Problem: Accidentally Committed node_modules or venv

If you've committed large dependency directories, you need to remove them from git history:

#### Option 1: Using git filter-repo (Recommended)

```bash
# Install git-filter-repo first:
# pip install git-filter-repo

# Remove node_modules from history
git filter-repo --path node_modules --invert-paths --force

# Remove Python virtual environment
git filter-repo --path venv --invert-paths --force
git filter-repo --path .venv --invert-paths --force

# Remove __pycache__
git filter-repo --path __pycache__ --invert-paths --force
```

#### Option 2: Using BFG Repo-Cleaner

```bash
# Download BFG from https://rtyley.github.io/bfg-repo-cleaner/

# Remove folders
java -jar bfg.jar --delete-folders node_modules
java -jar bfg.jar --delete-folders venv
java -jar bfg.jar --delete-folders __pycache__

# Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

#### Option 3: Start Fresh (Nuclear Option)

If the history is too corrupted:

```bash
# 1. Backup current working directory
cp -r . ../project-backup

# 2. Delete .git directory
rm -rf .git

# 3. Re-initialize with clean history
git init
git add .
git commit -m "Initial commit - clean slate"

# 4. Push to remote
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main --force
```

### Problem: Missing .gitignore Patterns

If you pushed before .gitignore was set up correctly:

```bash
# 1. Update .gitignore with missing patterns
cat >> .gitignore << 'EOF'
# Dependencies
node_modules/
venv/
.venv/

# Environment
.env
.env.local

# Build outputs
dist/
build/
out/

# Logs
*.log
logs/

# Database
*.sqlite
*.sqlite3
*.db
EOF

# 2. Remove already-tracked files
git rm -r --cached node_modules venv .env dist build || true

# 3. Commit the cleanup
git add .gitignore
git commit -m "Update .gitignore and remove tracked files"

# 4. Force push to update remote
git push origin main --force
```

### Problem: Repository Too Large for Remote

Most Git hosting services have size limits:
- GitHub: 100 MB per file, ~5 GB repo
- GitLab: 10 GB repo (default)
- Bitbucket: 2 GB repo (free tier)

**Solutions:**

1. **Remove large files from history** (see above)

2. **Use Git LFS for large assets:**
   ```bash
   # Install Git LFS
   git lfs install

   # Track large file types
   git lfs track "*.psd"
   git lfs track "*.zip"
   git lfs track "*.mp4"

   # Commit .gitattributes
   git add .gitattributes
   git commit -m "Configure Git LFS"
   ```

3. **Split repository into multiple repos:**
   - Frontend in one repo
   - Backend in another repo
   - Shared libraries as separate packages

### Problem: Authentication Failed

#### For HTTPS:

```bash
# GitHub: Use Personal Access Token instead of password
# 1. Generate token at: https://github.com/settings/tokens
# 2. Use token as password when pushing

# Or configure credential helper:
git config --global credential.helper store
# Next push will save credentials
```

#### For SSH:

```bash
# 1. Generate SSH key if you don't have one
ssh-keygen -t ed25519 -C "your_email@example.com"

# 2. Add SSH key to ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# 3. Add public key to your Git hosting service
cat ~/.ssh/id_ed25519.pub
# Copy and paste to GitHub/GitLab/Bitbucket settings

# 4. Test connection
ssh -T git@github.com  # For GitHub
ssh -T git@gitlab.com  # For GitLab
ssh -T git@bitbucket.org  # For Bitbucket

# 5. Update remote URL to use SSH
git remote set-url origin git@github.com:username/repo.git
```

### Problem: Rejected Push (Non-Fast-Forward)

If remote has commits you don't have locally:

```bash
# Option 1: Pull and merge
git pull origin main --rebase
git push origin main

# Option 2: Force push (CAUTION: overwrites remote)
git push origin main --force

# Option 3: Force push with lease (safer)
git push origin main --force-with-lease
```

---

## Advanced Scenarios

### Pushing Multiple Branches

```bash
# Push all branches
git push origin --all

# Push specific branch
git push origin feature-branch

# Set upstream for all branches
git push --all -u origin
```

### Setting Up CI/CD

After pushing, configure continuous integration:

#### GitHub Actions

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm test
```

#### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
stages:
  - test
  - build

test:
  stage: test
  image: node:18
  script:
    - npm install
    - npm test
```

### Mirroring to Multiple Remotes

Push to multiple Git hosting services:

```bash
# Add multiple remotes
git remote add github git@github.com:user/repo.git
git remote add gitlab git@gitlab.com:user/repo.git

# Push to both
git push github main
git push gitlab main

# Or configure push to both at once
git remote set-url --add --push origin git@github.com:user/repo.git
git remote set-url --add --push origin git@gitlab.com:user/repo.git
git push origin main  # Pushes to both
```

---

## Best Practices

### Before First Push

1. ✅ Review all files being committed: `git status`
2. ✅ Check .gitignore is comprehensive: `cat .gitignore`
3. ✅ Verify no secrets in code: `grep -r "API_KEY\|SECRET\|PASSWORD" . --exclude-dir=.git`
4. ✅ Ensure .env is not tracked: `git ls-files | grep .env`
5. ✅ Check repository size: `du -sh .git`

### Repository Hygiene

1. **Keep commits clean:**
   ```bash
   # Squash messy commits before pushing
   git rebase -i HEAD~5
   ```

2. **Write clear commit messages:**
   ```bash
   # Good commit message format:
   # <type>: <subject>
   #
   # <body>
   #
   # Example:
   git commit -m "feat: Add user authentication

   - Implement JWT-based auth
   - Add login/logout endpoints
   - Create auth middleware"
   ```

3. **Tag releases:**
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

### Security Considerations

1. **Never commit secrets:**
   - API keys
   - Database passwords
   - Private keys
   - OAuth tokens

2. **Use environment variables:**
   - Keep `.env` in `.gitignore`
   - Provide `.env.example` with placeholder values

3. **Review public repositories:**
   - Ensure no proprietary code
   - Check licenses are appropriate
   - Remove internal references

---

## Automation

### Script: Quick Export

Create `export-to-github.sh` in your project:

```bash
#!/bin/bash
# Quick export script for generated projects

set -e

REPO_URL="$1"

if [ -z "$REPO_URL" ]; then
    echo "Usage: ./export-to-github.sh <repository-url>"
    echo "Example: ./export-to-github.sh git@github.com:user/repo.git"
    exit 1
fi

echo "🚀 Exporting project to: $REPO_URL"

# Validate repository
if [ ! -d .git ]; then
    echo "❌ Error: Not a git repository"
    exit 1
fi

# Check for issues
echo "📝 Checking for common issues..."
if git log --all --pretty=format: --name-only --diff-filter=A | sort -u | grep -qE "node_modules|venv|__pycache__"; then
    echo "⚠️  Warning: Dependency directories found in git history"
    echo "    Consider cleaning them before pushing (see docs/exporting-projects.md)"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Add remote and push
echo "📤 Adding remote and pushing..."
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
git branch -M main
git push -u origin main

echo "✅ Project successfully exported!"
echo "   View at: $(echo $REPO_URL | sed 's/git@/https:\/\//' | sed 's/\.com:/.com\//' | sed 's/\.git$//')"
```

Make it executable:
```bash
chmod +x export-to-github.sh
```

Usage:
```bash
./export-to-github.sh git@github.com:username/repo.git
```

---

## Getting Help

If you encounter issues not covered here:

1. **Check YokeFlow validation logs:**
   ```bash
   # Logs are in generations/your-project/logs/
   cat logs/session-*.log | grep -i "validation"
   ```

2. **Git hosting service documentation:**
   - [GitHub Docs](https://docs.github.com)
   - [GitLab Docs](https://docs.gitlab.com)
   - [Bitbucket Docs](https://support.atlassian.com/bitbucket-cloud/)

3. **YokeFlow community:**
   - GitHub Issues: Report problems or ask questions
   - Discussions: Share experiences and solutions

---

## Summary Checklist

Before pushing your generated project:

- [ ] Navigate to project directory: `cd generations/your-project/`
- [ ] Check git status: `git status`
- [ ] Verify .gitignore exists and is comprehensive
- [ ] Check for accidentally tracked files: `git ls-files | grep -E "node_modules|venv|\.env"`
- [ ] Review repository size: `du -sh .git`
- [ ] Create remote repository on hosting service
- [ ] Add remote: `git remote add origin <url>`
- [ ] Push to remote: `git push -u origin main`
- [ ] Verify push succeeded: Check repository on hosting service
- [ ] (Optional) Set up CI/CD workflows
- [ ] (Optional) Configure branch protection rules

**You're ready to share your project with the world! 🚀**
