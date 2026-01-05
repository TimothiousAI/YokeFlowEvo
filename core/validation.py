"""
Repository Validation
========================================

Post-session validation to detect and fix common repository issues.

This module provides utilities to:
- Detect accidentally committed dependency directories (node_modules, venv, etc.)
- Auto-fix .gitignore to prevent future issues
- Report validation issues for user awareness
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import subprocess

logger = logging.getLogger(__name__)


class RepositoryIssue:
    """Represents a repository validation issue."""

    def __init__(self, severity: str, category: str, message: str, fix_available: bool = False):
        self.severity = severity  # "error", "warning", "info"
        self.category = category  # "gitignore", "committed_deps", "config"
        self.message = message
        self.fix_available = fix_available

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "fix_available": self.fix_available
        }


def validate_repository(project_path: Path) -> List[RepositoryIssue]:
    """
    Validate repository for common issues.

    Args:
        project_path: Path to the project repository

    Returns:
        List of RepositoryIssue objects found
    """
    issues: List[RepositoryIssue] = []

    # Check if this is a git repository
    git_dir = project_path / ".git"
    if not git_dir.exists():
        logger.debug(f"Not a git repository: {project_path}")
        return issues

    # Check for committed dependency directories
    dependency_dirs = [
        "node_modules",
        "venv",
        ".venv",
        "env",
        "ENV",
        "__pycache__",
        "dist",
        "build",
        ".next",
        "out"
    ]

    try:
        # Check git history for these directories
        for dep_dir in dependency_dirs:
            result = subprocess.run(
                ["git", "log", "--all", "--", dep_dir],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                issues.append(RepositoryIssue(
                    severity="warning",
                    category="committed_deps",
                    message=f"Dependency directory '{dep_dir}' found in git history",
                    fix_available=True
                ))

        # Check if .gitignore exists
        gitignore_path = project_path / ".gitignore"
        if not gitignore_path.exists():
            issues.append(RepositoryIssue(
                severity="error",
                category="gitignore",
                message="No .gitignore file found in repository",
                fix_available=True
            ))
        else:
            # Check if .gitignore has essential exclusions
            gitignore_content = gitignore_path.read_text()
            missing_exclusions = []

            essential_patterns = [
                ("node_modules", "node_modules/"),
                ("venv", "venv/"),
                ("__pycache__", "__pycache__/"),
                ("env vars", ".env")
            ]

            for name, pattern in essential_patterns:
                if pattern not in gitignore_content:
                    missing_exclusions.append(name)

            if missing_exclusions:
                issues.append(RepositoryIssue(
                    severity="warning",
                    category="gitignore",
                    message=f".gitignore missing exclusions: {', '.join(missing_exclusions)}",
                    fix_available=True
                ))

        # Check for large files in git
        result = subprocess.run(
            ["git", "ls-files", "-s"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            large_files = []
            for line in result.stdout.split('\n'):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    # Format: mode hash stage size path
                    try:
                        size = int(parts[3])
                        if size > 1_000_000:  # > 1MB
                            path = ' '.join(parts[4:])
                            large_files.append((path, size))
                    except (ValueError, IndexError):
                        continue

            if large_files:
                file_list = ', '.join([f"{path} ({size // 1024}KB)" for path, size in large_files[:5]])
                issues.append(RepositoryIssue(
                    severity="warning",
                    category="large_files",
                    message=f"Large files detected in repository: {file_list}",
                    fix_available=False
                ))

    except subprocess.TimeoutExpired:
        logger.warning(f"Git command timed out during validation of {project_path}")
    except Exception as e:
        logger.error(f"Error during repository validation: {e}")

    return issues


def fix_gitignore(project_path: Path) -> bool:
    """
    Auto-fix .gitignore by adding missing essential exclusions.

    Args:
        project_path: Path to the project repository

    Returns:
        True if fixes were applied, False otherwise
    """
    gitignore_path = project_path / ".gitignore"

    # Standard .gitignore template
    standard_gitignore = """
# Dependencies
node_modules/
venv/
.venv/
env/
ENV/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Environment variables
.env
.env.local
.env.*.local

# Build outputs
dist/
build/
*.egg-info/
.next/
out/

# Testing
coverage/
.nyc_output/
.pytest_cache/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS files
.DS_Store
Thumbs.db

# Logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
logs/

# Database
*.sqlite
*.sqlite3
*.db
"""

    try:
        if not gitignore_path.exists():
            # Create new .gitignore
            gitignore_path.write_text(standard_gitignore.strip())
            logger.info(f"Created .gitignore at {project_path}")

            # Try to commit it
            try:
                subprocess.run(
                    ["git", "add", ".gitignore"],
                    cwd=project_path,
                    check=True,
                    timeout=5
                )
                subprocess.run(
                    ["git", "commit", "-m", "Add comprehensive .gitignore"],
                    cwd=project_path,
                    check=True,
                    timeout=5
                )
                logger.info("Committed .gitignore to repository")
            except subprocess.CalledProcessError:
                logger.debug("Could not commit .gitignore (may already be staged)")

            return True
        else:
            # Append missing patterns to existing .gitignore
            existing_content = gitignore_path.read_text()
            patterns_to_add = []

            essential_patterns = [
                "node_modules/",
                "venv/",
                ".venv/",
                "env/",
                "ENV/",
                "__pycache__/",
                ".env",
                ".env.local",
                "dist/",
                "build/",
                "*.sqlite",
                "*.sqlite3"
            ]

            for pattern in essential_patterns:
                if pattern not in existing_content:
                    patterns_to_add.append(pattern)

            if patterns_to_add:
                # Add missing patterns
                updated_content = existing_content.rstrip() + "\n\n# Auto-added by YokeFlow validation\n"
                updated_content += "\n".join(patterns_to_add) + "\n"

                gitignore_path.write_text(updated_content)
                logger.info(f"Added {len(patterns_to_add)} missing patterns to .gitignore")

                return True
            else:
                logger.debug(".gitignore already contains all essential patterns")
                return False

    except Exception as e:
        logger.error(f"Error fixing .gitignore: {e}")
        return False


def get_repository_issues(project_path: Path) -> Dict[str, Any]:
    """
    Get comprehensive repository validation report.

    Args:
        project_path: Path to the project repository

    Returns:
        Dictionary containing validation results and issue details
    """
    issues = validate_repository(project_path)

    # Categorize issues by severity
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    info = [i for i in issues if i.severity == "info"]

    # Count fixable issues
    fixable_count = sum(1 for i in issues if i.fix_available)

    return {
        "total_issues": len(issues),
        "errors": len(errors),
        "warnings": len(warnings),
        "info": len(info),
        "fixable_issues": fixable_count,
        "issues": [i.to_dict() for i in issues],
        "has_critical_issues": len(errors) > 0,
        "project_path": str(project_path)
    }


def run_validation(project_path: Path, auto_fix: bool = True) -> Dict[str, Any]:
    """
    Run complete validation workflow with optional auto-fix.

    Args:
        project_path: Path to the project repository
        auto_fix: If True, automatically fix issues when possible

    Returns:
        Validation report dictionary
    """
    logger.info(f"Running repository validation for {project_path}")

    # Get initial issues
    report = get_repository_issues(project_path)

    if auto_fix and report["fixable_issues"] > 0:
        logger.info(f"Auto-fixing {report['fixable_issues']} issues...")
        fixed = fix_gitignore(project_path)

        if fixed:
            # Re-run validation to get updated report
            report = get_repository_issues(project_path)
            report["auto_fix_applied"] = True
        else:
            report["auto_fix_applied"] = False
    else:
        report["auto_fix_applied"] = False

    # Log summary
    if report["total_issues"] == 0:
        logger.info("[OK] Repository validation passed with no issues")
    else:
        logger.warning(
            f"[!] Repository validation found {report['total_issues']} issues "
            f"({report['errors']} errors, {report['warnings']} warnings)"
        )

    return report
