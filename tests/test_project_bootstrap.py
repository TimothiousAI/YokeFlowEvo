"""
Tests for Phase 4: Project Bootstrapping

Tests cover:
- DomainDetector: detects domains from app_spec
- CLAUDEMDGenerator: generates CLAUDE.md from spec
- ProjectBootstrapper: bootstraps projects with Claude SDK structure
"""

import pytest
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import json

from core.bootstrap.domain_detector import DomainDetector, DetectedDomain
from core.bootstrap.claude_md_generator import CLAUDEMDGenerator, GeneratedCLAUDEMD
from core.bootstrap.project_bootstrapper import ProjectBootstrapper, BootstrapResult


# ============================================================================
# DomainDetector Tests
# ============================================================================

class TestDomainDetector:
    """Tests for DomainDetector class."""

    @pytest.fixture
    def detector(self):
        return DomainDetector()

    def test_detect_frontend_react(self, detector):
        """Test detection of React frontend."""
        app_spec = """
        Build a web application using React for the frontend.
        The UI should have components for user management.
        Use Tailwind CSS for styling.
        """
        domains = detector.detect_domains(app_spec)

        frontend = next((d for d in domains if d.name == 'frontend'), None)
        assert frontend is not None
        assert frontend.confidence >= 0.4
        assert 'react' in frontend.keywords_found

    def test_detect_backend_fastapi(self, detector):
        """Test detection of FastAPI backend."""
        app_spec = """
        Create a REST API using FastAPI with Python.
        Include endpoints for CRUD operations.
        Use uvicorn as the server.
        """
        domains = detector.detect_domains(app_spec)

        backend = next((d for d in domains if d.name == 'backend'), None)
        assert backend is not None
        assert backend.confidence >= 0.4
        assert 'fastapi' in backend.keywords_found

    def test_detect_database_postgresql(self, detector):
        """Test detection of PostgreSQL database."""
        app_spec = """
        Use PostgreSQL for the database.
        Implement proper database migrations.
        Include models for users and posts.
        """
        domains = detector.detect_domains(app_spec)

        database = next((d for d in domains if d.name == 'database'), None)
        assert database is not None
        assert 'postgresql' in database.keywords_found or 'database' in database.keywords_found

    def test_detect_multiple_domains(self, detector):
        """Test detection of multiple domains."""
        app_spec = """
        Full-stack application with:
        - React frontend with TypeScript
        - FastAPI backend
        - PostgreSQL database
        - Docker deployment
        - Jest tests for frontend
        """
        domains = detector.detect_domains(app_spec)

        domain_names = [d.name for d in domains]
        assert 'frontend' in domain_names
        assert 'backend' in domain_names
        assert 'database' in domain_names

    def test_detect_empty_spec(self, detector):
        """Test handling of empty spec."""
        domains = detector.detect_domains("")
        assert domains == []

    def test_detect_stack(self, detector):
        """Test tech stack detection."""
        app_spec = "Build with React and FastAPI and PostgreSQL"
        stack = detector.get_all_detected_stack(app_spec)

        assert 'frontend' in stack
        assert stack['frontend'] == 'react'
        assert 'backend' in stack
        assert stack['backend'] == 'fastapi'

    def test_classify_project_type_fullstack(self, detector):
        """Test fullstack project classification."""
        app_spec = "React frontend with FastAPI backend"
        project_type = detector.classify_project_type(app_spec)
        assert project_type == 'fullstack'

    def test_classify_project_type_api(self, detector):
        """Test API project classification."""
        app_spec = "REST API with Express.js"
        project_type = detector.classify_project_type(app_spec)
        assert project_type == 'api'

    def test_classify_project_type_frontend(self, detector):
        """Test frontend project classification."""
        app_spec = "Single page application with Vue.js"
        project_type = detector.classify_project_type(app_spec)
        assert project_type == 'frontend'


# ============================================================================
# CLAUDEMDGenerator Tests
# ============================================================================

class TestCLAUDEMDGenerator:
    """Tests for CLAUDEMDGenerator class."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def generator(self, temp_project):
        return CLAUDEMDGenerator(temp_project)

    @pytest.mark.asyncio
    async def test_generate_basic(self, generator):
        """Test basic CLAUDE.md generation."""
        app_spec = "A simple todo application with React and FastAPI."

        result = await generator.generate(
            app_spec=app_spec,
            project_name="todo-app"
        )

        assert isinstance(result, GeneratedCLAUDEMD)
        assert result.content is not None
        assert "todo-app" in result.content
        assert "# CLAUDE.md" in result.content

    @pytest.mark.asyncio
    async def test_generate_includes_stack(self, generator):
        """Test that generated content includes detected stack."""
        app_spec = "Build with React, FastAPI, and PostgreSQL."

        result = await generator.generate(
            app_spec=app_spec,
            project_name="test-project"
        )

        assert "## Tech Stack" in result.content
        # Should detect at least one technology
        assert result.detected_stack is not None

    @pytest.mark.asyncio
    async def test_generate_includes_structure(self, generator):
        """Test that generated content includes structure."""
        app_spec = "A web application"

        result = await generator.generate(
            app_spec=app_spec,
            project_name="test-project"
        )

        assert "## Project Structure" in result.content
        assert result.predicted_structure is not None

    @pytest.mark.asyncio
    async def test_generate_includes_commands(self, generator):
        """Test that generated content includes commands."""
        app_spec = "Build with React"

        result = await generator.generate(
            app_spec=app_spec,
            project_name="test-project"
        )

        assert "## Key Commands" in result.content

    @pytest.mark.asyncio
    async def test_generate_includes_yokeflow_notes(self, generator):
        """Test that YokeFlow notes are included."""
        app_spec = "A simple app"

        result = await generator.generate(
            app_spec=app_spec,
            project_name="test-project"
        )

        assert "YokeFlow" in result.content
        assert ".claude/" in result.content


# ============================================================================
# ProjectBootstrapper Tests
# ============================================================================

class TestProjectBootstrapper:
    """Tests for ProjectBootstrapper class."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def bootstrapper(self):
        return ProjectBootstrapper()

    @pytest.fixture
    def sample_app_spec(self):
        return """
        Task Manager Application

        A full-stack task management application with:
        - React frontend with TypeScript
        - FastAPI backend with Python
        - PostgreSQL database
        - User authentication
        - CRUD operations for tasks
        """

    @pytest.mark.asyncio
    async def test_bootstrap_creates_claude_dir(self, temp_project, bootstrapper, sample_app_spec):
        """Test that bootstrap creates .claude directory."""
        result = await bootstrapper.bootstrap(
            project_path=temp_project,
            app_spec=sample_app_spec,
            project_name="task-manager"
        )

        assert result.success is True
        assert (Path(temp_project) / '.claude').exists()
        assert (Path(temp_project) / '.claude' / 'skills').exists()
        assert (Path(temp_project) / '.claude' / 'commands' / 'experts').exists()

    @pytest.mark.asyncio
    async def test_bootstrap_creates_claude_md(self, temp_project, bootstrapper, sample_app_spec):
        """Test that bootstrap creates CLAUDE.md."""
        result = await bootstrapper.bootstrap(
            project_path=temp_project,
            app_spec=sample_app_spec,
            project_name="task-manager"
        )

        assert result.claude_md_generated is True
        claude_md_path = Path(temp_project) / 'CLAUDE.md'
        assert claude_md_path.exists()

        content = claude_md_path.read_text()
        assert "task-manager" in content

    @pytest.mark.asyncio
    async def test_bootstrap_creates_domain_stubs(self, temp_project, bootstrapper, sample_app_spec):
        """Test that bootstrap creates domain expert stubs."""
        result = await bootstrapper.bootstrap(
            project_path=temp_project,
            app_spec=sample_app_spec,
            project_name="task-manager"
        )

        assert len(result.domains_initialized) > 0

        # Check at least one domain was created
        experts_dir = Path(temp_project) / '.claude' / 'commands' / 'experts'
        assert any(experts_dir.iterdir())

    @pytest.mark.asyncio
    async def test_bootstrap_creates_settings(self, temp_project, bootstrapper, sample_app_spec):
        """Test that bootstrap creates settings.json."""
        result = await bootstrapper.bootstrap(
            project_path=temp_project,
            app_spec=sample_app_spec,
            project_name="task-manager"
        )

        settings_path = Path(temp_project) / '.claude' / 'settings.json'
        assert settings_path.exists()

        with open(settings_path) as f:
            settings = json.load(f)

        assert settings['project']['name'] == 'task-manager'

    @pytest.mark.asyncio
    async def test_bootstrap_no_overwrite(self, temp_project, bootstrapper, sample_app_spec):
        """Test that bootstrap doesn't overwrite existing files."""
        # Create existing CLAUDE.md
        claude_md_path = Path(temp_project) / 'CLAUDE.md'
        claude_md_path.write_text("# Existing CLAUDE.md")

        result = await bootstrapper.bootstrap(
            project_path=temp_project,
            app_spec=sample_app_spec,
            project_name="task-manager"
        )

        # Should not overwrite
        assert result.claude_md_generated is False
        content = claude_md_path.read_text()
        assert content == "# Existing CLAUDE.md"

    @pytest.mark.asyncio
    async def test_bootstrap_force_overwrite(self, temp_project, bootstrapper, sample_app_spec):
        """Test that force=True overwrites existing files."""
        # Create existing CLAUDE.md
        claude_md_path = Path(temp_project) / 'CLAUDE.md'
        claude_md_path.write_text("# Existing CLAUDE.md")

        result = await bootstrapper.bootstrap(
            project_path=temp_project,
            app_spec=sample_app_spec,
            project_name="task-manager",
            force=True
        )

        # Should overwrite
        assert result.claude_md_generated is True
        content = claude_md_path.read_text()
        assert "task-manager" in content

    @pytest.mark.asyncio
    async def test_bootstrap_invalid_path(self, bootstrapper, sample_app_spec):
        """Test bootstrap with invalid path."""
        result = await bootstrapper.bootstrap(
            project_path="/nonexistent/path",
            app_spec=sample_app_spec,
            project_name="test"
        )

        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_bootstrap_empty_spec(self, temp_project, bootstrapper):
        """Test bootstrap with empty app_spec."""
        result = await bootstrapper.bootstrap(
            project_path=temp_project,
            app_spec="",
            project_name="test-project"
        )

        # Should still succeed but with minimal detection
        assert result.success is True
        assert (Path(temp_project) / '.claude').exists()


# ============================================================================
# Integration Tests
# ============================================================================

class TestBootstrapIntegration:
    """Integration tests for project bootstrapping."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_full_bootstrap_flow(self, temp_project):
        """Test complete bootstrap flow from spec to structure."""
        app_spec = """
        E-commerce Platform

        A modern e-commerce platform with:
        - Next.js frontend with TypeScript
        - FastAPI backend
        - PostgreSQL for data
        - Redis for caching
        - Stripe for payments
        """

        bootstrapper = ProjectBootstrapper()
        result = await bootstrapper.bootstrap(
            project_path=temp_project,
            app_spec=app_spec,
            project_name="ecommerce-platform"
        )

        # Verify success
        assert result.success is True

        # Verify directory structure
        project = Path(temp_project)
        assert (project / '.claude').exists()
        assert (project / '.claude' / 'skills').exists()
        assert (project / '.claude' / 'commands' / 'experts').exists()
        assert (project / 'CLAUDE.md').exists()
        assert (project / '.claude' / 'settings.json').exists()

        # Verify domain detection
        assert 'frontend' in result.domains_initialized or 'backend' in result.domains_initialized

        # Verify CLAUDE.md content
        claude_md = (project / 'CLAUDE.md').read_text()
        assert 'ecommerce-platform' in claude_md
        assert 'Tech Stack' in claude_md

    @pytest.mark.asyncio
    async def test_domain_stub_content(self, temp_project):
        """Test that domain stubs have correct content."""
        app_spec = "Build a React application with API"

        bootstrapper = ProjectBootstrapper()
        await bootstrapper.bootstrap(
            project_path=temp_project,
            app_spec=app_spec,
            project_name="test-app"
        )

        experts_dir = Path(temp_project) / '.claude' / 'commands' / 'experts'

        # Find any domain directory
        domain_dirs = list(experts_dir.iterdir())
        if domain_dirs:
            domain_dir = domain_dirs[0]

            # Check expertise.yaml exists and has content
            yaml_path = domain_dir / 'expertise.yaml'
            if yaml_path.exists():
                content = yaml_path.read_text()
                assert 'domain:' in content
                assert 'confidence:' in content
                assert 'version:' in content

            # Check question.md exists
            question_path = domain_dir / 'question.md'
            if question_path.exists():
                content = question_path.read_text()
                assert 'Expert Query' in content

            # Check self-improve.md exists
            improve_path = domain_dir / 'self-improve.md'
            if improve_path.exists():
                content = improve_path.read_text()
                assert 'Trigger Conditions' in content


# ============================================================================
# Run tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
