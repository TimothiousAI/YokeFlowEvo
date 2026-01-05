"""
Unit tests for ExpertiseManager

Tests cover:
- Domain classification with various inputs
- Learning extraction from session logs
- Tool pattern extraction
- Line limit enforcement
- Validation and pruning
- Self-improvement scanning
- Prompt formatting output
- Database persistence and versioning
"""

import sys
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, '.')

from core.learning.expertise_manager import (
    ExpertiseManager,
    ExpertiseFile,
    DOMAINS,
    MAX_EXPERTISE_LINES,
    DOMAIN_KEYWORDS,
    DOMAIN_FILE_PATTERNS
)


# Fixtures

@pytest.fixture
def mock_db():
    """Create mock database connection."""
    db = AsyncMock()
    db.get_expertise = AsyncMock(return_value=None)
    db.save_expertise = AsyncMock(return_value={'id': uuid4()})
    db.record_expertise_update = AsyncMock()
    db.list_expertise_domains = AsyncMock(return_value=[])
    db.get_expertise_history = AsyncMock(return_value=[])
    db.acquire = AsyncMock()
    return db


@pytest.fixture
def project_id():
    """Create test project ID."""
    return uuid4()


@pytest.fixture
def manager(project_id, mock_db):
    """Create ExpertiseManager instance."""
    return ExpertiseManager(project_id, mock_db)


@pytest.fixture
def sample_expertise_content():
    """Sample expertise content for testing."""
    return {
        'core_files': ['api/routes.py', 'api/handlers.py'],
        'patterns': [
            {
                'name': 'Async handler pattern',
                'language': 'python',
                'description': 'Uses async/await for route handlers',
                'when_to_use': 'For API endpoints'
            }
        ],
        'techniques': [
            {
                'name': 'Read-Edit workflow',
                'steps': ['Read file', 'Edit file', 'Test changes']
            }
        ],
        'learnings': [
            {
                'type': 'success',
                'lesson': 'Always validate input',
                'date': datetime.now().isoformat()
            },
            {
                'type': 'failure',
                'lesson': 'Missing error handling',
                'date': datetime.now().isoformat()
            }
        ]
    }


# Domain Classification Tests

def test_classify_domain_database_keywords(manager):
    """Test domain classification with database keywords."""
    task_desc = "Create migration script to add new table with indexes"
    file_paths = []

    domain = manager.classify_domain(task_desc, file_paths)

    assert domain == 'database', f"Expected 'database', got '{domain}'"


def test_classify_domain_api_keywords(manager):
    """Test domain classification with API keywords."""
    task_desc = "Add new REST endpoint for user authentication"
    file_paths = []

    domain = manager.classify_domain(task_desc, file_paths)

    assert domain == 'api', f"Expected 'api', got '{domain}'"


def test_classify_domain_frontend_keywords(manager):
    """Test domain classification with frontend keywords."""
    task_desc = "Create React component for user profile form"
    file_paths = []

    domain = manager.classify_domain(task_desc, file_paths)

    assert domain == 'frontend', f"Expected 'frontend', got '{domain}'"


def test_classify_domain_testing_keywords(manager):
    """Test domain classification with testing keywords."""
    task_desc = "Write unit tests with pytest fixtures and assertions"
    file_paths = []

    domain = manager.classify_domain(task_desc, file_paths)

    assert domain == 'testing', f"Expected 'testing', got '{domain}'"


def test_classify_domain_file_paths(manager):
    """Test domain classification based on file paths."""
    task_desc = "Update code"
    file_paths = ['components/UserProfile.tsx', 'components/Header.jsx']

    domain = manager.classify_domain(task_desc, file_paths)

    # File paths weighted more heavily (2x)
    assert domain == 'frontend', f"Expected 'frontend', got '{domain}'"


def test_classify_domain_mixed_signals(manager):
    """Test domain classification with mixed signals (highest score wins)."""
    task_desc = "Add database migration for API endpoint"
    file_paths = []

    domain = manager.classify_domain(task_desc, file_paths)

    # Both database and api keywords present, but database has more
    assert domain in ['database', 'api'], f"Expected 'database' or 'api', got '{domain}'"


def test_classify_domain_no_keywords(manager):
    """Test domain classification with no recognizable keywords."""
    task_desc = "Refactor utility helper functions"
    file_paths = []

    domain = manager.classify_domain(task_desc, file_paths)

    # With no specific domain keywords, should return 'general'
    assert domain == 'general', f"Expected 'general', got '{domain}'"


def test_classify_domain_case_insensitive(manager):
    """Test domain classification is case-insensitive."""
    task_desc = "CREATE TABLE users with INDEX"
    file_paths = []

    domain = manager.classify_domain(task_desc, file_paths)

    assert domain == 'database', f"Expected 'database', got '{domain}'"


# File Path Extraction Tests

def test_extract_file_paths_from_logs(manager):
    """Test extracting file paths from logs."""
    logs = """
    Edit(file_path="core/learning/expertise_manager.py")
    Read(file_path="api/routes.py")
    Some random text with no paths
    Write(file_path="tests/test_new.py")
    """

    paths = manager._extract_file_paths_from_logs(logs)

    assert len(paths) > 0, "Should extract some paths"
    assert any('expertise_manager.py' in p for p in paths), "Should find expertise_manager.py"


def test_extract_file_paths_limit(manager):
    """Test file path extraction respects limit of 20."""
    # Create logs with 30 file references
    logs = "\n".join([f"file_{i}/path/file.py" for i in range(30)])

    paths = manager._extract_file_paths_from_logs(logs)

    assert len(paths) <= 20, f"Should limit to 20 paths, got {len(paths)}"


# Modified Files Extraction Tests

def test_extract_modified_files_edit_pattern(manager):
    """Test extracting files from Edit tool calls."""
    logs = """
    Edit(file_path="core/manager.py", old_string="...", new_string="...")
    Edit(file_path="api/routes.py", old_string="...", new_string="...")
    """

    modified = manager._extract_modified_files(logs)

    assert 'core/manager.py' in modified, "Should extract core/manager.py"
    assert 'api/routes.py' in modified, "Should extract api/routes.py"


def test_extract_modified_files_write_pattern(manager):
    """Test extracting files from Write tool calls."""
    logs = """
    Write(file_path="tests/test_new.py", content="...")
    """

    modified = manager._extract_modified_files(logs)

    assert 'tests/test_new.py' in modified, "Should extract tests/test_new.py"


def test_extract_modified_files_limit(manager):
    """Test modified files extraction respects limit of 20."""
    # Create logs with 30 Edit calls
    logs = "\n".join([f'Edit(file_path="file_{i}.py", old_string="", new_string="")' for i in range(30)])

    modified = manager._extract_modified_files(logs)

    assert len(modified) <= 20, f"Should limit to 20 files, got {len(modified)}"


# Failure Learning Extraction Tests

def test_extract_failure_learning_error(manager):
    """Test extracting failure from error message."""
    logs = "Error: Database connection timeout after 30 seconds"

    learning = manager._extract_failure_learning(logs)

    assert learning is not None, "Should extract learning"
    assert learning['type'] == 'failure', "Should be failure type"
    assert 'Error' in learning['lesson'], "Should contain error type"
    assert 'timeout' in learning['lesson'].lower(), "Should contain error details"


def test_extract_failure_learning_exception(manager):
    """Test extracting failure from exception."""
    logs = "Exception: KeyError - 'user_id' not found in session data"

    learning = manager._extract_failure_learning(logs)

    assert learning is not None, "Should extract learning"
    assert learning['type'] == 'failure', "Should be failure type"
    assert 'Exception' in learning['lesson'], "Should contain exception type"


def test_extract_failure_learning_no_error(manager):
    """Test no learning extracted when no error present."""
    logs = "Everything worked perfectly"

    learning = manager._extract_failure_learning(logs)

    assert learning is None, "Should not extract learning when no error"


# Success Pattern Extraction Tests

def test_extract_success_patterns_read_edit(manager):
    """Test extracting Read-Edit pattern."""
    logs = "Read(file_path='test.py') ... Edit(file_path='test.py')"
    task_desc = "Update test file"

    patterns = manager._extract_success_patterns(logs, task_desc)

    assert len(patterns) > 0, "Should find patterns"
    assert any('Read-Edit' in p['name'] for p in patterns), "Should find Read-Edit pattern"


def test_extract_success_patterns_testing(manager):
    """Test extracting test-driven pattern."""
    logs = "pytest test_file.py ... PASSED"
    task_desc = "Write tests"

    patterns = manager._extract_success_patterns(logs, task_desc)

    assert len(patterns) > 0, "Should find patterns"
    assert any('test' in p['name'].lower() for p in patterns), "Should find test pattern"


# Tool Pattern Extraction Tests

def test_extract_tool_patterns_read_edit_sequence(manager):
    """Test extracting Read->Edit workflow."""
    logs = "Read tool called ... Edit tool called"

    patterns = manager._extract_tool_patterns(logs)

    assert len(patterns) > 0, "Should find patterns"
    assert any('Read-Edit' in p['name'] for p in patterns), "Should find Read-Edit workflow"


def test_extract_tool_patterns_read_edit_test_sequence(manager):
    """Test extracting Read->Edit->Test workflow."""
    logs = "Read tool called ... Edit tool called ... pytest execution"

    patterns = manager._extract_tool_patterns(logs)

    assert len(patterns) > 0, "Should find patterns"
    workflow = next((p for p in patterns if 'Read-Edit' in p['name']), None)
    assert workflow is not None, "Should find Read-Edit workflow"
    if 'Test' in workflow['name']:
        assert 'Test' in workflow['tools'], "Should include Test in tools"


def test_extract_tool_patterns_write_execute(manager):
    """Test extracting Write->Execute workflow."""
    logs = "Write tool called ... Bash tool called"

    patterns = manager._extract_tool_patterns(logs)

    assert any('Write-Execute' in p['name'] or 'Write' in p['name'] for p in patterns), \
        "Should find Write workflow"


def test_extract_tool_patterns_grep_read(manager):
    """Test extracting Grep->Read workflow."""
    logs = "Grep tool called ... Read tool called"

    patterns = manager._extract_tool_patterns(logs)

    assert any('Search' in p['name'] or 'Grep' in p['name'] for p in patterns), \
        "Should find Search/Grep workflow"


def test_extract_tool_patterns_browser_verification(manager):
    """Test extracting browser verification pattern."""
    logs = "browser_navigate ... browser_screenshot"

    patterns = manager._extract_tool_patterns(logs)

    assert any('browser' in p['name'].lower() for p in patterns), \
        "Should find browser workflow"


def test_extract_tool_patterns_wrong_order(manager):
    """Test tool patterns not extracted when in wrong order."""
    logs = "Edit tool called first ... Read tool called second"

    patterns = manager._extract_tool_patterns(logs)

    # Should not find Read-Edit pattern because Edit came first
    read_edit_patterns = [p for p in patterns if 'Read-Edit' in p['name']]
    assert len(read_edit_patterns) == 0, "Should not find Read-Edit when Edit comes first"


# Line Limit Enforcement Tests

def test_enforce_line_limit_under_limit(manager):
    """Test content under limit is unchanged."""
    small_content = {
        'core_files': ['file1.py', 'file2.py'],
        'patterns': [{'name': 'Test'}],
        'techniques': [],
        'learnings': []
    }

    result = manager._enforce_line_limit(small_content)

    assert result == small_content, "Small content should be unchanged"


def test_enforce_line_limit_removes_old_failures(manager):
    """Test old failures are removed first."""
    old_date = (datetime.now() - timedelta(days=60)).isoformat()
    recent_date = datetime.now().isoformat()

    # Create content large enough to exceed MAX_EXPERTISE_LINES
    large_content = {
        'core_files': [f'file_{i}.py' for i in range(200)],
        'patterns': [
            {
                'name': f'Pattern {i}',
                'description': f'This is a long description for pattern {i}' * 10,
                'when_to_use': 'For testing purposes in various scenarios',
                'language': 'python'
            }
            for i in range(100)
        ],
        'techniques': [
            {
                'name': f'Technique {i}',
                'steps': [f'Step {j} with detailed instructions' for j in range(5)]
            }
            for i in range(50)
        ],
        'learnings': [
            {'type': 'failure', 'lesson': f'Old failure {i}' * 5, 'date': old_date}
            for i in range(20)
        ] + [
            {'type': 'failure', 'lesson': f'Recent failure {i}', 'date': recent_date}
            for i in range(5)
        ]
    }

    # Verify it exceeds limit
    initial_lines = len(json.dumps(large_content, indent=2).split('\n'))
    assert initial_lines > MAX_EXPERTISE_LINES, f"Test setup failed: content not large enough ({initial_lines} <= {MAX_EXPERTISE_LINES})"

    result = manager._enforce_line_limit(large_content)

    # Check old failures removed
    old_failures = [l for l in result.get('learnings', [])
                   if l.get('type') == 'failure' and 'Old failure' in l.get('lesson', '')]
    assert len(old_failures) == 0, "Old failures should be removed"


def test_enforce_line_limit_preserves_successes(manager):
    """Test success learnings are preserved."""
    large_content = {
        'core_files': [f'file_{i}.py' for i in range(200)],
        'patterns': [{'name': f'Pattern {i}'} for i in range(100)],
        'techniques': [],
        'learnings': [
            {'type': 'success', 'lesson': f'Success {i}', 'date': datetime.now().isoformat()}
            for i in range(10)
        ]
    }

    result = manager._enforce_line_limit(large_content)

    # Check successes preserved
    successes = [l for l in result.get('learnings', []) if l.get('type') == 'success']
    assert len(successes) > 0, "Should preserve at least some successes"


def test_enforce_line_limit_trims_patterns(manager):
    """Test patterns are trimmed to 20."""
    # Create content large enough to trigger trimming
    large_content = {
        'core_files': [f'file_{i}.py' for i in range(200)],
        'patterns': [
            {
                'name': f'Pattern {i}',
                'description': f'This is a long description for pattern {i}' * 10,
                'language': 'python'
            }
            for i in range(100)
        ],
        'techniques': [
            {
                'name': f'Tech {i}',
                'steps': [f'Step {j}' for j in range(10)]
            }
            for i in range(50)
        ],
        'learnings': []
    }

    # Verify it exceeds limit
    initial_lines = len(json.dumps(large_content, indent=2).split('\n'))
    assert initial_lines > MAX_EXPERTISE_LINES, f"Test setup failed: content not large enough"

    result = manager._enforce_line_limit(large_content)

    # Should have trimmed patterns
    assert len(result['patterns']) <= 20, f"Should trim patterns to 20, got {len(result['patterns'])}"


def test_enforce_line_limit_trims_core_files(manager):
    """Test core files are trimmed to 30."""
    # Create content large enough to trigger trimming
    large_content = {
        'core_files': [f'file_{i}.py' for i in range(200)],
        'patterns': [
            {
                'name': f'Pattern {i}',
                'description': f'Long description' * 20
            }
            for i in range(100)
        ],
        'techniques': [
            {
                'name': f'Tech {i}',
                'steps': [f'Step {j}' for j in range(10)]
            }
            for i in range(50)
        ],
        'learnings': []
    }

    # Verify it exceeds limit
    initial_lines = len(json.dumps(large_content, indent=2).split('\n'))
    assert initial_lines > MAX_EXPERTISE_LINES, f"Test setup failed: content not large enough"

    result = manager._enforce_line_limit(large_content)

    # Should have trimmed core files
    assert len(result['core_files']) <= 30, f"Should trim files to 30, got {len(result['core_files'])}"


def test_enforce_line_limit_trims_techniques(manager):
    """Test techniques are trimmed to 15."""
    # Create content large enough to trigger trimming with even longer descriptions
    large_content = {
        'core_files': [f'file_{i}.py' for i in range(200)],
        'patterns': [
            {
                'name': f'Pattern {i}',
                'description': f'This is an extremely long and detailed description for pattern number {i}. ' * 30,
                'when_to_use': 'For testing purposes in various scenarios across multiple use cases',
                'language': 'python',
                'code': 'def example():\n    pass\n' * 5
            }
            for i in range(100)
        ],
        'techniques': [
            {
                'name': f'Technique {i}',
                'steps': [f'Step {j} with very detailed comprehensive instructions that explain everything' for j in range(15)]
            }
            for i in range(50)
        ],
        'learnings': [
            {
                'type': 'success',
                'lesson': f'Success learning number {i} with extensive details about what worked' * 10,
                'date': datetime.now().isoformat()
            }
            for i in range(50)
        ]
    }

    # Verify it exceeds limit
    initial_lines = len(json.dumps(large_content, indent=2).split('\n'))
    assert initial_lines > MAX_EXPERTISE_LINES, f"Test setup failed: content not large enough ({initial_lines} <= {MAX_EXPERTISE_LINES})"

    result = manager._enforce_line_limit(large_content)

    # Should have trimmed techniques
    assert len(result['techniques']) <= 15, f"Should trim techniques to 15, got {len(result['techniques'])}"


def test_enforce_line_limit_final_check(manager):
    """Test final line count is under MAX_EXPERTISE_LINES."""
    # Create massive content
    large_content = {
        'core_files': [f'file_{i}.py' for i in range(200)],
        'patterns': [{'name': f'Pattern {i}', 'description': 'x' * 100} for i in range(100)],
        'techniques': [{'name': f'Tech {i}', 'steps': [f'Step {j}' for j in range(10)]} for i in range(50)],
        'learnings': [{'lesson': f'Learning {i}' * 10} for i in range(100)]
    }

    result = manager._enforce_line_limit(large_content)
    line_count = len(json.dumps(result, indent=2).split('\n'))

    assert line_count <= MAX_EXPERTISE_LINES, \
        f"Should be under {MAX_EXPERTISE_LINES} lines, got {line_count}"


# Library Extraction Tests

def test_extract_libraries_python(manager):
    """Test extracting Python libraries."""
    file_content = """
import fastapi
from sqlalchemy import create_engine
import asyncpg
from typing import List
    """
    file_path = "test.py"

    libs = manager._extract_libraries(file_content, file_path)

    assert 'fastapi' in libs, "Should find fastapi"
    assert 'sqlalchemy' in libs, "Should find sqlalchemy"
    assert 'asyncpg' in libs, "Should find asyncpg"
    assert 'typing' not in libs, "Should skip standard library"


def test_extract_libraries_javascript(manager):
    """Test extracting JavaScript libraries."""
    file_content = """
import React from 'react'
import { useState } from 'react'
const axios = require('axios')
import express from 'express'
    """
    file_path = "test.js"

    libs = manager._extract_libraries(file_content, file_path)

    assert 'react' in libs, "Should find react"
    assert 'axios' in libs, "Should find axios"
    assert 'express' in libs, "Should find express"


def test_extract_libraries_typescript_scoped(manager):
    """Test extracting scoped TypeScript packages."""
    file_content = """
import { Component } from '@angular/core'
import styled from '@emotion/styled'
    """
    file_path = "test.ts"

    libs = manager._extract_libraries(file_content, file_path)

    assert '@angular/core' in libs, "Should find scoped package @angular/core"
    assert '@emotion/styled' in libs, "Should find scoped package @emotion/styled"


def test_extract_libraries_skip_relative(manager):
    """Test skipping relative imports."""
    file_content = """
import React from 'react'
import MyComponent from './components/MyComponent'
import utils from '../utils'
    """
    file_path = "test.jsx"

    libs = manager._extract_libraries(file_content, file_path)

    assert 'react' in libs, "Should find react"
    # Should not include relative imports
    relative_imports = [lib for lib in libs if lib.startswith('.')]
    assert len(relative_imports) == 0, "Should not include relative imports"


# Code Pattern Extraction Tests

def test_extract_code_patterns_python_async(manager):
    """Test extracting Python async pattern."""
    file_content = """
async def fetch_user(user_id):
    return await db.get_user(user_id)

async def update_user(user_id, data):
    return await db.update_user(user_id, data)
    """
    file_path = "api.py"
    domain = "api"

    patterns = manager._extract_code_patterns(file_content, file_path, domain)

    assert len(patterns) > 0, "Should find patterns"
    async_pattern = next((p for p in patterns if 'Async' in p['name']), None)
    assert async_pattern is not None, "Should find async pattern"


def test_extract_code_patterns_python_class(manager):
    """Test extracting Python class pattern."""
    file_content = """
class UserManager:
    def __init__(self):
        pass

    def get_user(self, user_id):
        pass
    """
    file_path = "manager.py"
    domain = "api"

    patterns = manager._extract_code_patterns(file_content, file_path, domain)

    assert len(patterns) > 0, "Should find patterns"
    class_pattern = next((p for p in patterns if 'class' in p['name'].lower()), None)
    assert class_pattern is not None, "Should find class pattern"


def test_extract_code_patterns_python_decorator(manager):
    """Test extracting Python decorator pattern."""
    file_content = """
@app.route('/users')
@require_auth
def get_users():
    pass
    """
    file_path = "routes.py"
    domain = "api"

    patterns = manager._extract_code_patterns(file_content, file_path, domain)

    assert len(patterns) > 0, "Should find patterns"
    decorator_pattern = next((p for p in patterns if 'Decorator' in p['name']), None)
    assert decorator_pattern is not None, "Should find decorator pattern"


def test_extract_code_patterns_react_component(manager):
    """Test extracting React component pattern."""
    file_content = """
export default function UserProfile() {
    return <div>Profile</div>
}
    """
    file_path = "UserProfile.tsx"
    domain = "frontend"

    patterns = manager._extract_code_patterns(file_content, file_path, domain)

    assert len(patterns) > 0, "Should find patterns"
    component_pattern = next((p for p in patterns if 'component' in p['name'].lower()), None)
    assert component_pattern is not None, "Should find component pattern"


def test_extract_code_patterns_react_hooks(manager):
    """Test extracting React hooks pattern."""
    file_content = """
export function UserList() {
    const [users, setUsers] = useState([])

    useEffect(() => {
        fetchUsers()
    }, [])

    return <div>{users.length}</div>
}
    """
    file_path = "UserList.tsx"
    domain = "frontend"

    patterns = manager._extract_code_patterns(file_content, file_path, domain)

    assert len(patterns) > 0, "Should find patterns"
    hooks_pattern = next((p for p in patterns if 'Hook' in p['name']), None)
    assert hooks_pattern is not None, "Should find hooks pattern"


def test_extract_code_patterns_sql_ddl(manager):
    """Test extracting SQL DDL pattern."""
    file_content = """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255)
);
    """
    file_path = "schema.sql"
    domain = "database"

    patterns = manager._extract_code_patterns(file_content, file_path, domain)

    assert len(patterns) > 0, "Should find patterns"
    ddl_pattern = next((p for p in patterns if 'DDL' in p['name'] or 'schema' in p['name'].lower()), None)
    assert ddl_pattern is not None, "Should find DDL pattern"


def test_extract_code_patterns_sql_trigger(manager):
    """Test extracting SQL trigger pattern."""
    file_content = """
CREATE TRIGGER update_timestamp
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_modified_time();
    """
    file_path = "triggers.sql"
    domain = "database"

    patterns = manager._extract_code_patterns(file_content, file_path, domain)

    assert len(patterns) > 0, "Should find patterns"
    trigger_pattern = next((p for p in patterns if 'trigger' in p['name'].lower()), None)
    assert trigger_pattern is not None, "Should find trigger pattern"


# Async Tests

@pytest.mark.asyncio
async def test_get_expertise_not_found(manager, mock_db):
    """Test getting expertise that doesn't exist."""
    mock_db.get_expertise.return_value = None

    expertise = await manager.get_expertise('api')

    assert expertise is None, "Should return None for non-existent expertise"


@pytest.mark.asyncio
async def test_get_expertise_success(manager, mock_db, sample_expertise_content):
    """Test getting existing expertise."""
    mock_db.get_expertise.return_value = {
        'domain': 'api',
        'content': sample_expertise_content,
        'version': 1,
        'line_count': 50,
        'validated_at': None
    }

    expertise = await manager.get_expertise('api')

    assert expertise is not None, "Should return expertise"
    assert expertise.domain == 'api', "Should have correct domain"
    assert expertise.version == 1, "Should have correct version"
    assert len(expertise.content['core_files']) == 2, "Should have core files"


@pytest.mark.asyncio
async def test_get_expertise_invalid_domain(manager, mock_db):
    """Test getting expertise with invalid domain defaults to general."""
    mock_db.get_expertise.return_value = None

    expertise = await manager.get_expertise('invalid_domain')

    # Should default to 'general' and try to fetch that
    mock_db.get_expertise.assert_called_once()
    call_args = mock_db.get_expertise.call_args[0]
    assert call_args[1] == 'general', "Should default to 'general' domain"


@pytest.mark.asyncio
async def test_format_for_prompt_empty(manager, mock_db):
    """Test formatting when no expertise exists."""
    mock_db.get_expertise.return_value = None

    formatted = await manager.format_for_prompt('api')

    assert formatted == "", "Should return empty string when no expertise"


@pytest.mark.asyncio
async def test_format_for_prompt_structure(manager, mock_db, sample_expertise_content):
    """Test formatted output has correct markdown structure."""
    mock_db.get_expertise.return_value = {
        'domain': 'api',
        'content': sample_expertise_content,
        'version': 1,
        'line_count': 50,
        'validated_at': None
    }

    formatted = await manager.format_for_prompt('api')

    assert '# Expertise:' in formatted, "Should have header"
    assert '## Core Files' in formatted, "Should have Core Files section"
    assert '## Code Patterns' in formatted, "Should have Patterns section"
    assert '## Successful Techniques' in formatted, "Should have Techniques section"
    assert 'api/routes.py' in formatted, "Should include core files"


@pytest.mark.asyncio
async def test_format_for_prompt_line_limit(manager, mock_db):
    """Test formatted output respects line limit."""
    # Create content that would exceed limit when formatted
    large_content = {
        'core_files': [f'file_{i}.py' for i in range(100)],
        'patterns': [{'name': f'Pattern {i}', 'description': 'x' * 100} for i in range(200)],
        'techniques': [],
        'learnings': []
    }

    mock_db.get_expertise.return_value = {
        'domain': 'api',
        'content': large_content,
        'version': 1,
        'line_count': 2000,
        'validated_at': None
    }

    formatted = await manager.format_for_prompt('api')
    lines = formatted.split('\n')

    assert len(lines) <= MAX_EXPERTISE_LINES, \
        f"Should not exceed {MAX_EXPERTISE_LINES} lines, got {len(lines)}"


# Integration helper to run all tests
if __name__ == "__main__":
    pytest.main([__file__, '-v'])
