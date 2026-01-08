"""
Expertise Sync Service
======================

Bidirectional synchronization between file-based and database expertise.

Key Features:
- Import: Read .claude/commands/experts/ files → update database
- Export: Read database → write to files
- Detect conflicts and prefer newer version
- Validate YAML format before import
- Track sync timestamps
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path
from uuid import UUID
from datetime import datetime
import logging
import json

try:
    import yaml
except ImportError:
    yaml = None

from core.learning.expertise_exporter import ExpertiseExporter, ExportResult
from core.learning.skill_generator import SkillGenerator

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of synchronization operation."""
    direction: str  # "import", "export", "bidirectional"
    domains_synced: List[str] = field(default_factory=list)
    skills_generated: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    success: bool = True


class ExpertiseSyncService:
    """
    Bidirectional sync between file and database expertise.

    Handles importing expertise from files (on project load) and
    exporting expertise to files (after sessions with learnings).
    """

    def __init__(
        self,
        project_path: str,
        project_id: UUID,
        db: Any
    ):
        """
        Initialize sync service.

        Args:
            project_path: Path to project root
            project_id: Project UUID
            db: Database connection
        """
        self.project_path = Path(project_path)
        self.project_id = project_id
        self.db = db

        self.experts_dir = self.project_path / ".claude" / "commands" / "experts"
        self.exporter = ExpertiseExporter(project_path, db)
        self.skill_generator = SkillGenerator(project_path)

    async def import_from_files(self) -> SyncResult:
        """
        Import expertise from files to database.

        Reads .claude/commands/experts/{domain}/expertise.yaml files
        and updates the database if file version is newer.

        Returns:
            SyncResult with import status
        """
        result = SyncResult(direction="import")

        if not self.experts_dir.exists():
            logger.debug("No experts directory found, nothing to import")
            return result

        try:
            # Find all domain directories
            for domain_dir in self.experts_dir.iterdir():
                if not domain_dir.is_dir():
                    continue

                domain = domain_dir.name
                yaml_path = domain_dir / "expertise.yaml"

                if not yaml_path.exists():
                    continue

                try:
                    # Parse file
                    file_data = self._parse_expertise_yaml(yaml_path)
                    if not file_data:
                        result.errors.append(f"Invalid YAML in {domain}")
                        continue

                    # Check against database
                    db_expertise = await self._get_db_expertise(domain)

                    if db_expertise:
                        # Check for conflict
                        if self._detect_conflict(file_data, db_expertise):
                            # File is newer, update DB
                            await self._update_db_expertise(domain, file_data)
                            result.domains_synced.append(domain)
                            logger.info(f"Imported newer file expertise for '{domain}'")
                        else:
                            logger.debug(f"DB expertise for '{domain}' is current")
                    else:
                        # No DB expertise, import from file
                        await self._create_db_expertise(domain, file_data)
                        result.domains_synced.append(domain)
                        logger.info(f"Created DB expertise from file for '{domain}'")

                except Exception as e:
                    result.errors.append(f"{domain}: {e}")
                    logger.error(f"Failed to import domain '{domain}': {e}")

            result.success = len(result.errors) == 0

        except Exception as e:
            result.errors.append(str(e))
            result.success = False
            logger.error(f"Import failed: {e}")

        return result

    async def export_to_files(self, generate_skills: bool = True) -> SyncResult:
        """
        Export expertise from database to files.

        Writes to .claude/commands/experts/{domain}/ and optionally
        generates native skills for mature expertise.

        Args:
            generate_skills: Also generate native skills if mature

        Returns:
            SyncResult with export status
        """
        result = SyncResult(direction="export")

        try:
            # Export all domains
            export_results = await self.exporter.export_all(self.project_id)

            for export_result in export_results:
                if export_result.success and export_result.files_written:
                    result.domains_synced.append(export_result.domain)
                elif export_result.error:
                    result.errors.append(f"{export_result.domain}: {export_result.error}")

            # Generate skills for mature expertise
            if generate_skills:
                from core.learning.expertise_manager import ExpertiseManager

                manager = ExpertiseManager(self.project_id, self.db)
                all_expertise = await manager.get_all_expertise()

                for domain, expertise_file in all_expertise.items():
                    skill_result = await self.skill_generator.generate_skill(
                        domain, expertise_file.content
                    )
                    if skill_result.generated:
                        result.skills_generated.append(domain)

            result.success = len(result.errors) == 0

        except Exception as e:
            result.errors.append(str(e))
            result.success = False
            logger.error(f"Export failed: {e}")

        return result

    async def sync(self) -> SyncResult:
        """
        Full bidirectional sync with conflict resolution.

        Process:
        1. Import from files (newer files update DB)
        2. Export to files (DB updates files)
        3. Generate skills for mature expertise

        Returns:
            SyncResult with sync status
        """
        result = SyncResult(direction="bidirectional")

        try:
            # Phase 1: Import from files
            import_result = await self.import_from_files()
            result.domains_synced.extend(import_result.domains_synced)
            result.conflicts.extend(import_result.conflicts)
            result.errors.extend(import_result.errors)

            # Phase 2: Export to files (with skill generation)
            export_result = await self.export_to_files(generate_skills=True)
            # Only add domains that weren't already in import
            for domain in export_result.domains_synced:
                if domain not in result.domains_synced:
                    result.domains_synced.append(domain)
            result.skills_generated.extend(export_result.skills_generated)
            result.errors.extend(export_result.errors)

            result.success = len(result.errors) == 0

            logger.info(
                f"Sync completed: {len(result.domains_synced)} domains, "
                f"{len(result.skills_generated)} skills, "
                f"{len(result.errors)} errors"
            )

        except Exception as e:
            result.errors.append(str(e))
            result.success = False
            logger.error(f"Sync failed: {e}")

        return result

    def _parse_expertise_yaml(self, path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse expertise.yaml file.

        Args:
            path: Path to YAML file

        Returns:
            Parsed data dict or None on error
        """
        try:
            content = path.read_text(encoding='utf-8')

            if yaml:
                data = yaml.safe_load(content)
            else:
                # Fallback: basic parsing
                data = self._basic_yaml_parse(content)

            # Validate required fields
            if not data or not isinstance(data, dict):
                return None

            if 'domain' not in data:
                return None

            return data

        except Exception as e:
            logger.error(f"Failed to parse YAML {path}: {e}")
            return None

    def _basic_yaml_parse(self, content: str) -> Dict[str, Any]:
        """
        Basic YAML parsing fallback when PyYAML not available.

        Only handles simple key: value pairs and lists.
        """
        data = {}
        current_key = None
        current_list = None

        for line in content.split('\n'):
            line = line.rstrip()

            # Skip comments and empty lines
            if not line or line.strip().startswith('#'):
                continue

            # Check for list item
            if line.strip().startswith('- '):
                if current_list is not None:
                    current_list.append(line.strip()[2:])
                continue

            # Check for key: value
            if ':' in line and not line.startswith(' '):
                parts = line.split(':', 1)
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ''

                if value:
                    # Simple value
                    data[key] = value
                    current_key = None
                    current_list = None
                else:
                    # Start of list or nested structure
                    current_key = key
                    current_list = []
                    data[key] = current_list

        return data

    def _detect_conflict(
        self,
        file_data: Dict[str, Any],
        db_data: Dict[str, Any]
    ) -> bool:
        """
        Check if file version is newer than database.

        Returns True if file should update database.
        """
        file_version = file_data.get('version', 0)
        db_version = db_data.get('version', 0)

        # File is newer
        if file_version > db_version:
            return True

        # Same version, check timestamps
        file_date = file_data.get('last_updated', '')
        db_date = db_data.get('last_updated', '')

        if file_date and db_date:
            try:
                file_dt = datetime.fromisoformat(file_date.replace('Z', '+00:00'))
                db_dt = datetime.fromisoformat(db_date.replace('Z', '+00:00'))
                return file_dt > db_dt
            except Exception:
                pass

        return False

    async def _get_db_expertise(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get expertise from database."""
        try:
            from core.learning.expertise_manager import ExpertiseManager

            manager = ExpertiseManager(self.project_id, self.db)
            expertise = await manager.get_expertise(domain)

            if expertise:
                return {
                    'version': expertise.version,
                    'content': expertise.content,
                    'last_updated': expertise.validated_at.isoformat() if expertise.validated_at else None
                }
        except Exception as e:
            logger.error(f"Failed to get DB expertise for '{domain}': {e}")

        return None

    async def _update_db_expertise(self, domain: str, file_data: Dict[str, Any]) -> None:
        """Update database expertise from file data."""
        try:
            from core.learning.expertise_manager import ExpertiseManager

            manager = ExpertiseManager(self.project_id, self.db)

            # Convert file format to DB format
            content = {
                'core_files': file_data.get('files', []),
                'patterns': file_data.get('patterns', []),
                'techniques': file_data.get('techniques', []),
                'learnings': file_data.get('learnings', []),
                'confidence': file_data.get('confidence', 0.5),
                'usage_count': file_data.get('usage_count', 0),
                'version': file_data.get('version', 1)
            }

            await manager.save_expertise(domain, content)
            logger.info(f"Updated DB expertise for '{domain}' from file")

        except Exception as e:
            logger.error(f"Failed to update DB expertise for '{domain}': {e}")
            raise

    async def _create_db_expertise(self, domain: str, file_data: Dict[str, Any]) -> None:
        """Create new database expertise from file data."""
        # Same as update for now
        await self._update_db_expertise(domain, file_data)
