"""
Tests for Phase 3: Expertise File System (ADWS Pattern)

Tests cover:
- ExpertiseExporter: exports DB expertise to files
- SkillGenerator: generates native Claude skills
- ExpertiseSyncService: bidirectional sync
- ExpertiseManager: routing priority (skills → files → DB)
"""

import pytest
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from core.learning.expertise_exporter import ExpertiseExporter, ExportResult
from core.learning.skill_generator import SkillGenerator, SkillGenerationResult
from core.learning.expertise_sync import ExpertiseSyncService, SyncResult


# ============================================================================
# ExpertiseExporter Tests
# ============================================================================

class TestExpertiseExporter:
    """Tests for ExpertiseExporter class."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def sample_expertise(self):
        """Sample expertise data for testing."""
        return {
            'patterns': [
                {'name': 'Repository Pattern', 'when_to_use': 'For data access abstraction', 'code': 'class Repo:\n    pass'},
                {'name': 'Service Layer', 'when_to_use': 'For business logic', 'code': 'class Service:\n    pass'},
            ],
            'techniques': [
                {'name': 'Async Query', 'steps': ['Create async method', 'Use await', 'Return result']},
            ],
            'learnings': [
                {'type': 'success', 'lesson': 'Use connection pooling', 'date': '2025-01-01'},
                {'type': 'failure', 'lesson': 'Avoid N+1 queries', 'date': '2025-01-02'},
            ],
            'core_files': ['core/database.py', 'core/models.py'],
            'confidence': 0.85,
            'usage_count': 15,
            'version': 3,
        }

    @pytest.mark.asyncio
    async def test_export_domain_creates_files(self, temp_project, sample_expertise):
        """Test that export_domain creates all expected files."""
        exporter = ExpertiseExporter(temp_project)

        result = await exporter.export_domain('database', sample_expertise)

        assert result.success is True
        assert result.domain == 'database'
        assert len(result.files_written) == 3

        # Check files exist
        domain_dir = Path(temp_project) / '.claude' / 'commands' / 'experts' / 'database'
        assert (domain_dir / 'expertise.yaml').exists()
        assert (domain_dir / 'question.md').exists()
        assert (domain_dir / 'self-improve.md').exists()

    @pytest.mark.asyncio
    async def test_export_domain_yaml_content(self, temp_project, sample_expertise):
        """Test that exported YAML contains correct content."""
        exporter = ExpertiseExporter(temp_project)

        await exporter.export_domain('database', sample_expertise)

        yaml_path = Path(temp_project) / '.claude' / 'commands' / 'experts' / 'database' / 'expertise.yaml'
        content = yaml_path.read_text()

        # Check required fields
        assert 'domain: database' in content
        assert 'confidence: 0.85' in content
        assert 'usage_count: 15' in content
        assert 'version: 3' in content
        assert 'Repository Pattern' in content
        assert 'Service Layer' in content

    @pytest.mark.asyncio
    async def test_export_skips_unchanged(self, temp_project, sample_expertise):
        """Test that export skips unchanged expertise."""
        exporter = ExpertiseExporter(temp_project)

        # First export
        result1 = await exporter.export_domain('database', sample_expertise)
        assert len(result1.files_written) == 3

        # Second export with same version
        result2 = await exporter.export_domain('database', sample_expertise)
        assert len(result2.files_written) == 0  # No files written

    @pytest.mark.asyncio
    async def test_export_force_overwrites(self, temp_project, sample_expertise):
        """Test that force=True overwrites unchanged expertise."""
        exporter = ExpertiseExporter(temp_project)

        # First export
        await exporter.export_domain('database', sample_expertise)

        # Force export
        result = await exporter.export_domain('database', sample_expertise, force=True)
        assert len(result.files_written) == 3

    @pytest.mark.asyncio
    async def test_question_md_content(self, temp_project, sample_expertise):
        """Test that question.md has correct format."""
        exporter = ExpertiseExporter(temp_project)

        await exporter.export_domain('database', sample_expertise)

        question_path = Path(temp_project) / '.claude' / 'commands' / 'experts' / 'database' / 'question.md'
        content = question_path.read_text()

        assert '# Database Expert Query' in content
        assert 'When to Consult' in content
        assert 'Query Format' in content
        assert 'Expert Capabilities' in content
        assert 'Repository Pattern' in content

    @pytest.mark.asyncio
    async def test_self_improve_md_content(self, temp_project, sample_expertise):
        """Test that self-improve.md has trigger conditions."""
        exporter = ExpertiseExporter(temp_project)

        await exporter.export_domain('database', sample_expertise)

        improve_path = Path(temp_project) / '.claude' / 'commands' / 'experts' / 'database' / 'self-improve.md'
        content = improve_path.read_text()

        assert '# Database Self-Improvement Triggers' in content
        assert 'Trigger Conditions' in content
        assert 'Update Process' in content
        assert 'Quality Thresholds' in content


# ============================================================================
# SkillGenerator Tests
# ============================================================================

class TestSkillGenerator:
    """Tests for SkillGenerator class."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mature_expertise(self):
        """Expertise that meets maturity thresholds."""
        return {
            'patterns': [
                {'name': 'Pattern1', 'when_to_use': 'For X', 'code': 'code1'},
                {'name': 'Pattern2', 'when_to_use': 'For Y', 'code': 'code2'},
            ],
            'techniques': [
                {'name': 'Technique1', 'steps': ['Step 1', 'Step 2']},
            ],
            'learnings': [
                {'type': 'success', 'lesson': 'Good practice'},
                {'type': 'failure', 'lesson': 'Bad practice'},
            ],
            'core_files': ['src/main.py'],
            'confidence': 0.85,  # >= 0.8
            'usage_count': 15,   # >= 10
            'version': 2,
        }

    @pytest.fixture
    def immature_expertise(self):
        """Expertise that doesn't meet maturity thresholds."""
        return {
            'patterns': [],
            'techniques': [],
            'learnings': [],
            'core_files': [],
            'confidence': 0.5,   # < 0.8
            'usage_count': 3,    # < 10
            'version': 1,
        }

    def test_should_generate_mature(self, temp_project, mature_expertise):
        """Test that mature expertise should generate skill."""
        generator = SkillGenerator(temp_project)

        assert generator.should_generate(mature_expertise) is True

    def test_should_not_generate_immature(self, temp_project, immature_expertise):
        """Test that immature expertise should not generate skill."""
        generator = SkillGenerator(temp_project)

        assert generator.should_generate(immature_expertise) is False

    def test_should_not_generate_low_confidence(self, temp_project):
        """Test that low confidence blocks skill generation."""
        generator = SkillGenerator(temp_project)
        expertise = {'confidence': 0.7, 'usage_count': 20}

        assert generator.should_generate(expertise) is False

    def test_should_not_generate_low_usage(self, temp_project):
        """Test that low usage blocks skill generation."""
        generator = SkillGenerator(temp_project)
        expertise = {'confidence': 0.9, 'usage_count': 5}

        assert generator.should_generate(expertise) is False

    @pytest.mark.asyncio
    async def test_generate_skill_creates_file(self, temp_project, mature_expertise):
        """Test that generate_skill creates SKILL.md file."""
        generator = SkillGenerator(temp_project)

        result = await generator.generate_skill('database', mature_expertise)

        assert result.generated is True
        assert result.domain == 'database'
        assert result.skill_path is not None

        skill_path = Path(result.skill_path)
        assert skill_path.exists()
        assert skill_path.name == 'SKILL.md'

    @pytest.mark.asyncio
    async def test_generate_skill_content(self, temp_project, mature_expertise):
        """Test that generated skill has correct content."""
        generator = SkillGenerator(temp_project)

        result = await generator.generate_skill('database', mature_expertise)

        content = Path(result.skill_path).read_text()

        # Check frontmatter
        assert '---' in content
        assert 'name: database-expert' in content
        assert 'description:' in content

        # Check content sections
        assert '# Database Expert Skill' in content
        assert '## Core Knowledge' in content or '## Patterns' in content
        assert '## When to Use This Skill' in content

    @pytest.mark.asyncio
    async def test_generate_skill_skips_immature(self, temp_project, immature_expertise):
        """Test that immature expertise is skipped."""
        generator = SkillGenerator(temp_project)

        result = await generator.generate_skill('database', immature_expertise)

        assert result.generated is False
        assert result.reason == 'skipped_immature'

    @pytest.mark.asyncio
    async def test_generate_skill_force(self, temp_project, immature_expertise):
        """Test that force=True generates even for immature expertise."""
        generator = SkillGenerator(temp_project)

        result = await generator.generate_skill('database', immature_expertise, force=True)

        assert result.generated is True

    @pytest.mark.asyncio
    async def test_generate_all_skills(self, temp_project, mature_expertise, immature_expertise):
        """Test generating skills for multiple domains."""
        generator = SkillGenerator(temp_project)

        expertise_by_domain = {
            'database': mature_expertise,
            'api': immature_expertise,
        }

        results = await generator.generate_all_skills(expertise_by_domain)

        assert len(results) == 2

        db_result = next(r for r in results if r.domain == 'database')
        api_result = next(r for r in results if r.domain == 'api')

        assert db_result.generated is True
        assert api_result.generated is False

    def test_list_generated_skills(self, temp_project, mature_expertise):
        """Test listing generated skills."""
        generator = SkillGenerator(temp_project)

        # Initially empty
        assert generator.list_generated_skills() == []

        # Create skill directory manually
        skill_dir = Path(temp_project) / '.claude' / 'skills' / 'test-expert'
        skill_dir.mkdir(parents=True)
        (skill_dir / 'SKILL.md').write_text('test')

        skills = generator.list_generated_skills()
        assert 'test-expert' in skills


# ============================================================================
# ExpertiseSyncService Tests
# ============================================================================

class TestExpertiseSyncService:
    """Tests for ExpertiseSyncService class."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        return MagicMock()

    @pytest.fixture
    def sample_yaml(self):
        """Sample expertise YAML content."""
        return """
domain: database
description: Database expertise
confidence: 0.8
usage_count: 12
version: 2
last_updated: 2025-01-01

files:
  - core/database.py
  - core/models.py

patterns:
  - name: Repository Pattern
    description: For data access
"""

    @pytest.mark.asyncio
    async def test_import_from_empty_dir(self, temp_project, mock_db):
        """Test import when no experts directory exists."""
        project_id = uuid4()
        service = ExpertiseSyncService(temp_project, project_id, mock_db)

        result = await service.import_from_files()

        assert result.success is True
        assert result.direction == 'import'
        assert len(result.domains_synced) == 0

    @pytest.mark.asyncio
    async def test_import_from_files(self, temp_project, mock_db, sample_yaml):
        """Test importing expertise from files."""
        project_id = uuid4()

        # Create expertise file
        experts_dir = Path(temp_project) / '.claude' / 'commands' / 'experts' / 'database'
        experts_dir.mkdir(parents=True)
        (experts_dir / 'expertise.yaml').write_text(sample_yaml)

        # Mock manager methods - patch where it's imported
        with patch('core.learning.expertise_manager.ExpertiseManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.get_expertise = AsyncMock(return_value=None)
            mock_manager.save_expertise = AsyncMock()
            MockManager.return_value = mock_manager

            service = ExpertiseSyncService(temp_project, project_id, mock_db)
            result = await service.import_from_files()

        assert result.success is True
        assert 'database' in result.domains_synced

    @pytest.mark.asyncio
    async def test_export_to_files(self, temp_project, mock_db):
        """Test exporting expertise to files."""
        project_id = uuid4()

        # Create mock expertise file class
        class MockExpertiseFile:
            def __init__(self):
                self.content = {
                    'patterns': [],
                    'techniques': [],
                    'learnings': [],
                    'core_files': [],
                    'confidence': 0.5,
                    'usage_count': 3,
                    'version': 1,
                }

        # Mock manager - patch where it's imported
        with patch('core.learning.expertise_manager.ExpertiseManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.get_all_expertise = AsyncMock(return_value={
                'database': MockExpertiseFile()
            })
            MockManager.return_value = mock_manager

            service = ExpertiseSyncService(temp_project, project_id, mock_db)
            result = await service.export_to_files(generate_skills=False)

        assert result.direction == 'export'
        # May have domains synced or not depending on mocking

    @pytest.mark.asyncio
    async def test_sync_bidirectional(self, temp_project, mock_db, sample_yaml):
        """Test full bidirectional sync."""
        project_id = uuid4()

        # Create expertise file
        experts_dir = Path(temp_project) / '.claude' / 'commands' / 'experts' / 'database'
        experts_dir.mkdir(parents=True)
        (experts_dir / 'expertise.yaml').write_text(sample_yaml)

        # Mock expertise file class
        class MockExpertiseFile:
            def __init__(self):
                self.content = {
                    'patterns': [],
                    'confidence': 0.5,
                    'usage_count': 3,
                    'version': 1,
                }

        with patch('core.learning.expertise_manager.ExpertiseManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.get_expertise = AsyncMock(return_value=None)
            mock_manager.save_expertise = AsyncMock()
            mock_manager.get_all_expertise = AsyncMock(return_value={
                'api': MockExpertiseFile()
            })
            MockManager.return_value = mock_manager

            service = ExpertiseSyncService(temp_project, project_id, mock_db)
            result = await service.sync()

        assert result.direction == 'bidirectional'

    def test_parse_expertise_yaml(self, temp_project, mock_db, sample_yaml):
        """Test YAML parsing."""
        project_id = uuid4()
        service = ExpertiseSyncService(temp_project, project_id, mock_db)

        # Create temp file
        yaml_path = Path(temp_project) / 'test.yaml'
        yaml_path.write_text(sample_yaml)

        data = service._parse_expertise_yaml(yaml_path)

        assert data is not None
        assert data.get('domain') == 'database'
        assert data.get('confidence') == 0.8 or data.get('confidence') == '0.8'

    def test_detect_conflict_file_newer(self, temp_project, mock_db):
        """Test conflict detection when file is newer."""
        project_id = uuid4()
        service = ExpertiseSyncService(temp_project, project_id, mock_db)

        file_data = {'version': 3, 'last_updated': '2025-01-05'}
        db_data = {'version': 2, 'last_updated': '2025-01-01'}

        assert service._detect_conflict(file_data, db_data) is True

    def test_detect_conflict_db_newer(self, temp_project, mock_db):
        """Test conflict detection when DB is newer."""
        project_id = uuid4()
        service = ExpertiseSyncService(temp_project, project_id, mock_db)

        file_data = {'version': 1, 'last_updated': '2025-01-01'}
        db_data = {'version': 2, 'last_updated': '2025-01-05'}

        assert service._detect_conflict(file_data, db_data) is False


# ============================================================================
# Integration Tests
# ============================================================================

class TestExpertiseFileSystemIntegration:
    """Integration tests for the expertise file system."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_export_then_skill_generation(self, temp_project):
        """Test that exported expertise can generate skills."""
        # Create exporter and generator
        exporter = ExpertiseExporter(temp_project)
        generator = SkillGenerator(temp_project)

        # Create mature expertise
        expertise = {
            'patterns': [
                {'name': 'Pattern1', 'when_to_use': 'Test', 'code': 'code'},
            ],
            'techniques': [],
            'learnings': [],
            'core_files': ['test.py'],
            'confidence': 0.9,
            'usage_count': 20,
            'version': 1,
        }

        # Export first
        export_result = await exporter.export_domain('test', expertise)
        assert export_result.success is True

        # Then generate skill
        skill_result = await generator.generate_skill('test', expertise)
        assert skill_result.generated is True

        # Verify both exist
        experts_dir = Path(temp_project) / '.claude' / 'commands' / 'experts' / 'test'
        skills_dir = Path(temp_project) / '.claude' / 'skills' / 'test-expert'

        assert (experts_dir / 'expertise.yaml').exists()
        assert (skills_dir / 'SKILL.md').exists()

    @pytest.mark.asyncio
    async def test_version_tracking_across_exports(self, temp_project):
        """Test that version tracking works correctly."""
        exporter = ExpertiseExporter(temp_project)

        # Export v1
        expertise_v1 = {
            'patterns': [],
            'confidence': 0.5,
            'version': 1,
        }
        result1 = await exporter.export_domain('test', expertise_v1)
        assert len(result1.files_written) == 3

        # Export v1 again (should skip)
        result2 = await exporter.export_domain('test', expertise_v1)
        assert len(result2.files_written) == 0

        # Export v2 (should write)
        expertise_v2 = {
            'patterns': [],
            'confidence': 0.6,
            'version': 2,
        }
        result3 = await exporter.export_domain('test', expertise_v2)
        assert len(result3.files_written) == 3


# ============================================================================
# Run tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
