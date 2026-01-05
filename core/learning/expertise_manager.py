"""
Expertise Manager
=================

Manages domain-specific expertise accumulated from completed sessions.

Key Features:
- Classifies tasks into domains (database, api, frontend, testing, security, deployment, general)
- Extracts learnings from session logs (failures, patterns, techniques)
- Validates and prunes stale expertise
- Enforces line limits to prevent token bloat
- Self-improves by scanning codebase
- Formats expertise for prompt injection

Expertise Structure (JSONB):
{
    "core_files": ["path/to/file.py", ...],
    "patterns": [{"name": "...", "code": "...", "when_to_use": "..."}],
    "techniques": [{"name": "...", "steps": [...]}],
    "learnings": [{"type": "failure|success", "lesson": "...", "date": "..."}]
}
"""

from typing import Dict, List, Any, Optional
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

# Domain classification constants
DOMAINS = ['database', 'api', 'frontend', 'testing', 'security', 'deployment', 'general']
MAX_EXPERTISE_LINES = 1000

# Keywords for domain classification (lowercase for case-insensitive matching)
DOMAIN_KEYWORDS = {
    'database': ['schema', 'migration', 'query', 'table', 'index', 'sql', 'database', 'postgres',
                 'mysql', 'sqlite', 'column', 'row', 'select', 'insert', 'update', 'delete'],
    'api': ['endpoint', 'route', 'rest', 'request', 'response', 'http', 'api', 'fastapi',
            'flask', 'express', 'handler', 'controller', 'middleware', 'get', 'post', 'put', 'patch'],
    'frontend': ['component', 'react', 'css', 'ui', 'render', 'state', 'frontend', 'html',
                 'jsx', 'tsx', 'vue', 'angular', 'style', 'layout', 'button', 'form', 'input'],
    'testing': ['test', 'assert', 'mock', 'fixture', 'coverage', 'pytest', 'unittest',
                'jest', 'mocha', 'spec', 'testcase', 'expect', 'verify'],
    'security': ['auth', 'token', 'encrypt', 'permission', 'cors', 'security', 'password',
                 'jwt', 'oauth', 'authentication', 'authorization', 'credential', 'hash'],
    'deployment': ['docker', 'deploy', 'ci', 'build', 'environment', 'deployment', 'container',
                   'kubernetes', 'pipeline', 'release', 'production', 'staging', 'config']
}

# File extension patterns for domain classification
DOMAIN_FILE_PATTERNS = {
    'database': ['.sql', 'migration', 'schema'],
    'api': ['route', 'handler', 'controller', 'endpoint', 'api'],
    'frontend': ['.tsx', '.jsx', '.css', '.scss', '.html', 'component'],
    'testing': ['.test.', '.spec.', 'test_', '_test'],
    'security': ['auth', 'security', 'permission'],
    'deployment': ['docker', '.yml', '.yaml', 'deploy', '.sh']
}


@dataclass
class ExpertiseFile:
    """
    Dataclass representing a domain expertise file.

    Attributes:
        domain: Domain name (e.g., 'database', 'api', 'frontend')
        content: JSONB content dict with core_files, patterns, techniques, learnings
        version: Version number (incremented on each save)
        line_count: Approximate line count for token budget management
        validated_at: Timestamp of last validation (None if never validated)
    """
    domain: str
    content: Dict[str, Any]
    version: int
    line_count: int
    validated_at: Optional[datetime] = None


class ExpertiseManager:
    """
    Manages accumulated expertise for self-learning system.

    Expertise is stored per domain with automatic versioning,
    validation, and line limit enforcement.
    """

    def __init__(self, project_id: UUID, db_connection: Any):
        """
        Initialize expertise manager.

        Args:
            project_id: Project UUID
            db_connection: Database connection for persistence
        """
        self.project_id = project_id
        self.db = db_connection
        logger.info(f"ExpertiseManager initialized for project {project_id}")

    async def get_expertise(self, domain: str) -> Optional[ExpertiseFile]:
        """
        Get expertise for a specific domain.

        Args:
            domain: Domain name (database/api/frontend/etc.)

        Returns:
            ExpertiseFile object or None if not found
        """
        if domain not in DOMAINS:
            logger.warning(f"Invalid domain '{domain}', defaulting to 'general'")
            domain = 'general'

        try:
            record = await self.db.get_expertise(self.project_id, domain)
            if not record:
                logger.debug(f"No expertise found for domain '{domain}'")
                return None

            # Parse content from JSONB string if needed
            content = record['content']
            if isinstance(content, str):
                content = json.loads(content)

            return ExpertiseFile(
                domain=record['domain'],
                content=content,
                version=record['version'],
                line_count=record['line_count'],
                validated_at=record.get('validated_at')
            )
        except Exception as e:
            logger.error(f"Failed to get expertise for domain '{domain}': {e}")
            return None

    async def get_all_expertise(self) -> Dict[str, ExpertiseFile]:
        """
        Get expertise for all domains.

        Returns:
            Dict mapping domain -> ExpertiseFile object
        """
        try:
            domains_list = await self.db.list_expertise_domains(self.project_id)
            result = {}

            for domain_record in domains_list:
                domain = domain_record['domain']
                expertise = await self.get_expertise(domain)
                if expertise:
                    result[domain] = expertise

            logger.info(f"Retrieved expertise for {len(result)} domains")
            return result
        except Exception as e:
            logger.error(f"Failed to get all expertise: {e}")
            return {}

    def classify_domain(self, task_description: str, file_paths: List[str]) -> str:
        """
        Classify task into appropriate domain.

        Args:
            task_description: Task description text
            file_paths: List of file paths involved

        Returns:
            Domain name (one of DOMAINS)
        """
        # Initialize scores for each domain
        domain_scores = {domain: 0 for domain in DOMAINS if domain != 'general'}

        # Score based on task description keywords
        description_lower = task_description.lower()
        for domain, keywords in DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword in description_lower:
                    domain_scores[domain] += 1

        # Score based on file path patterns
        for file_path in file_paths:
            file_lower = file_path.lower()
            for domain, patterns in DOMAIN_FILE_PATTERNS.items():
                for pattern in patterns:
                    if pattern in file_lower:
                        # File path matches are weighted more heavily
                        domain_scores[domain] += 2

        # Find domain with highest score
        max_score = max(domain_scores.values()) if domain_scores else 0

        if max_score == 0:
            logger.debug(f"No domain keywords found, classifying as 'general'")
            return 'general'

        # Get domain with highest score (first one if tie)
        best_domain = max(domain_scores.items(), key=lambda x: x[1])[0]

        logger.debug(f"Classified task as '{best_domain}' domain (score: {domain_scores[best_domain]})")
        return best_domain

    async def learn_from_session(
        self,
        session_id: UUID,
        task: Dict[str, Any],
        logs: str
    ) -> None:
        """
        Extract and store learnings from a completed session.

        Args:
            session_id: Session UUID
            task: Task dictionary
            logs: Session log content
        """
        try:
            # Classify domain from task
            task_desc = task.get('description', '') + ' ' + task.get('action', '')
            file_paths = self._extract_file_paths_from_logs(logs)
            domain = self.classify_domain(task_desc, file_paths)

            # Get or create expertise for this domain
            expertise = await self.get_expertise(domain)
            if not expertise:
                # Initialize new expertise
                content = {
                    'core_files': [],
                    'patterns': [],
                    'techniques': [],
                    'learnings': []
                }
            else:
                content = expertise.content

            # Extract learnings from logs
            learnings_added = []

            # Check for errors/failures
            if 'error' in logs.lower() or 'traceback' in logs.lower() or 'failed' in logs.lower():
                failure_learning = self._extract_failure_learning(logs)
                if failure_learning:
                    content['learnings'].append(failure_learning)
                    learnings_added.append(failure_learning['lesson'])

            # Extract successful patterns
            if task.get('status') == 'completed' or task.get('done'):
                success_patterns = self._extract_success_patterns(logs, task_desc)
                for pattern in success_patterns:
                    if pattern not in content['techniques']:
                        content['techniques'].append(pattern)
                        learnings_added.append(f"Technique: {pattern['name']}")

            # Update core files list
            for file_path in file_paths:
                if file_path not in content['core_files'] and len(content['core_files']) < 50:
                    content['core_files'].append(file_path)

            # Save updated expertise if we learned something
            if learnings_added:
                # Calculate approximate line count
                import json
                line_count = len(json.dumps(content, indent=2).split('\n'))

                # Save to database
                saved = await self.db.save_expertise(
                    self.project_id,
                    domain,
                    content,
                    line_count
                )

                # Record update in history
                await self.db.record_expertise_update(
                    expertise_id=saved['id'],
                    session_id=session_id,
                    change_type='learned',
                    summary=f"Learned {len(learnings_added)} insights from session",
                    diff='\n'.join(learnings_added)
                )

                logger.info(f"Learned {len(learnings_added)} insights for '{domain}' domain from session {session_id}")
            else:
                logger.debug(f"No new learnings extracted from session {session_id}")

        except Exception as e:
            logger.error(f"Failed to learn from session {session_id}: {e}")

    def _extract_file_paths_from_logs(self, logs: str) -> List[str]:
        """Extract file paths from log content."""
        import re
        # Look for common file path patterns
        paths = set()

        # Match paths like "core/learning/expertise_manager.py"
        for match in re.finditer(r'[\w/]+\.[\w]+', logs):
            path = match.group(0)
            if '/' in path or '\\' in path:
                paths.add(path)

        return list(paths)[:20]  # Limit to 20 files

    def _extract_failure_learning(self, logs: str) -> Optional[Dict[str, Any]]:
        """Extract learning from failure in logs."""
        import re
        from datetime import datetime

        # Look for error messages
        error_match = re.search(r'(Error|Exception|Failed):\s*(.+)', logs, re.IGNORECASE)
        if error_match:
            error_type = error_match.group(1)
            error_msg = error_match.group(2)[:200]  # Limit length

            return {
                'type': 'failure',
                'lesson': f"{error_type}: {error_msg}",
                'date': datetime.now().isoformat()
            }

        return None

    def _extract_success_patterns(self, logs: str, task_desc: str) -> List[Dict[str, Any]]:
        """Extract successful techniques from logs."""
        patterns = []

        # Look for tool usage patterns
        if 'Edit' in logs and 'Read' in logs:
            patterns.append({
                'name': 'Read-Edit pattern',
                'steps': ['Read file to understand context', 'Edit file with changes']
            })

        if 'test' in logs.lower() and 'pass' in logs.lower():
            patterns.append({
                'name': 'Test-driven approach',
                'steps': ['Write tests', 'Implement functionality', 'Verify tests pass']
            })

        return patterns

    async def validate_expertise(self, domain: str) -> Dict[str, Any]:
        """
        Validate and prune expertise for a domain.

        Args:
            domain: Domain name

        Returns:
            Validation report with changes made
        """
        # Stub - will be implemented in Epic 94
        logger.warning("ExpertiseManager.validate_expertise() not yet implemented")
        return {}

    async def self_improve(self, domain: str) -> None:
        """
        Scan codebase to discover patterns and update expertise.

        Args:
            domain: Domain name
        """
        # Stub - will be implemented in Epic 94
        logger.warning("ExpertiseManager.self_improve() not yet implemented")

    def format_for_prompt(self, domain: str) -> str:
        """
        Format expertise as markdown for prompt injection.

        Args:
            domain: Domain name

        Returns:
            Formatted markdown string (limited to MAX_EXPERTISE_LINES)
        """
        # Stub - will be implemented in Epic 94
        logger.warning("ExpertiseManager.format_for_prompt() not yet implemented")
        return ""
